"""
Gmail SMTP email helpers for the options dashboard.

Settings live in email_config.json (gitignored):
  - main: your sending account (name, email, smtp_username, app_password)
  - contacts: list of recipients (name, email; optional smtp fields per contact)
  - default_receiver: fallback recipient when none is specified

See email_config.example.json for the schema.

Gmail setup:
  1. Enable 2-Step Verification: https://myaccount.google.com/security
  2. Create an App Password: https://myaccount.google.com/apppasswords

Do NOT use your normal Gmail login password.
"""

from __future__ import annotations

import json
import mimetypes
import os
import smtplib
from email import encoders
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Dict, List, Optional

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587

_CONFIG_DIR = Path(__file__).resolve().parents[1]
EMAIL_CONFIG_FILE = _CONFIG_DIR / "email_config.json"
EMAIL_CONFIG_EXAMPLE_FILE = _CONFIG_DIR / "email_config.example.json"

_DEFAULT_SETTINGS: Dict[str, Any] = {
    "smtp_host": SMTP_HOST,
    "smtp_port": SMTP_PORT,
    "main": {
        "name": "",
        "email": "",
        "smtp_username": "",
        "app_password": "",
    },
    "default_receiver": "",
    "contacts": [],
}


def _normalize_password(password: str) -> str:
    return (password or "").replace(" ", "")


def load_email_settings() -> Dict[str, Any]:
    """Load the full email_config.json structure."""
    settings = json.loads(json.dumps(_DEFAULT_SETTINGS))

    if EMAIL_CONFIG_FILE.exists():
        try:
            with open(EMAIL_CONFIG_FILE, encoding="utf-8") as f:
                stored = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            print(f"Warning: Could not read email_config.json: {exc}")
            stored = {}
    else:
        stored = {}

    settings["smtp_host"] = stored.get("smtp_host", settings["smtp_host"])
    settings["smtp_port"] = stored.get("smtp_port", settings["smtp_port"])
    settings["default_receiver"] = stored.get("default_receiver", "")

    main = stored.get("main") or {}
    settings["main"] = {
        "name": main.get("name", ""),
        "email": main.get("email", ""),
        "smtp_username": main.get("smtp_username", main.get("email", "")),
        "app_password": _normalize_password(main.get("app_password", "")),
    }

    contacts: List[Dict[str, str]] = []
    for entry in stored.get("contacts") or []:
        if not isinstance(entry, dict):
            continue
        contacts.append(
            {
                "name": entry.get("name", ""),
                "email": entry.get("email", ""),
                "smtp_username": entry.get("smtp_username", entry.get("email", "")),
                "app_password": _normalize_password(entry.get("app_password", "")),
            }
        )
    settings["contacts"] = contacts

    # Env vars override main account when config file is empty or for password rotation.
    env_password = os.environ.get("GMAIL_APP_PASSWORD", "")
    env_sender = os.environ.get("GMAIL_SENDER", "")
    if env_password and not settings["main"]["app_password"]:
        settings["main"]["app_password"] = _normalize_password(env_password)
    if env_sender:
        if not settings["main"]["email"]:
            settings["main"]["email"] = env_sender
        if not settings["main"]["smtp_username"]:
            settings["main"]["smtp_username"] = env_sender
    env_receiver = os.environ.get("GMAIL_RECEIVER", "")
    if env_receiver and not settings["default_receiver"]:
        settings["default_receiver"] = env_receiver

    return settings


def get_main_account() -> Dict[str, str]:
    """Return the main (sender) account from email_config.json."""
    return dict(load_email_settings()["main"])


def get_contacts() -> List[Dict[str, str]]:
    """Return the contacts list from email_config.json."""
    return list(load_email_settings()["contacts"])


def find_contact(name_or_email: str) -> Optional[Dict[str, str]]:
    """Look up a contact by display name (case-insensitive) or email."""
    needle = (name_or_email or "").strip().lower()
    if not needle:
        return None

    for contact in get_contacts():
        if contact.get("email", "").lower() == needle:
            return contact
        if contact.get("name", "").lower() == needle:
            return contact
    return None


def add_contact(name: str, email: str) -> bool:
    """Append a contact to email_config.json. Raises ValueError on invalid input."""
    name = (name or "").strip()
    email = (email or "").strip()
    if not name:
        raise ValueError("Contact name is required.")
    if not email or "@" not in email:
        raise ValueError("A valid email address is required.")

    settings = load_email_settings()
    email_lower = email.lower()
    for contact in settings["contacts"]:
        if contact.get("email", "").lower() == email_lower:
            raise ValueError(f"A contact with email {email} already exists.")

    settings["contacts"].append(
        {
            "name": name,
            "email": email,
            "smtp_username": email,
            "app_password": "",
        }
    )
    return save_email_settings(settings)


def resolve_receiver(
    receiver_email: Optional[str] = None,
    contact_name: Optional[str] = None,
) -> str:
    """Resolve recipient from explicit email, contact name, or default_receiver."""
    if receiver_email:
        return receiver_email.strip()

    if contact_name:
        contact = find_contact(contact_name)
        if contact and contact.get("email"):
            return contact["email"]
        raise ValueError(f"Contact not found: {contact_name}")

    settings = load_email_settings()
    if settings.get("default_receiver"):
        return settings["default_receiver"]

    contacts = settings.get("contacts") or []
    if contacts and contacts[0].get("email"):
        return contacts[0]["email"]

    return ""


def _load_email_config() -> dict:
    """Flatten settings into the legacy dict shape used by send_email."""
    settings = load_email_settings()
    main = settings["main"]
    return {
        "SMTP_HOST": settings["smtp_host"],
        "SMTP_PORT": settings["smtp_port"],
        "SMTP_USERNAME": main.get("smtp_username") or main.get("email", ""),
        "SMTP_PASSWORD": main.get("app_password", ""),
        "SENDER_EMAIL": main.get("email", ""),
        "RECEIVER_EMAIL": settings.get("default_receiver", ""),
        "MAIN_NAME": main.get("name", ""),
        "CONTACTS": settings.get("contacts", []),
    }


def save_email_settings(settings: Dict[str, Any]) -> bool:
    """Persist the full email_config.json structure."""
    payload = {
        "smtp_host": settings.get("smtp_host", SMTP_HOST),
        "smtp_port": settings.get("smtp_port", SMTP_PORT),
        "default_receiver": settings.get("default_receiver", ""),
        "main": {
            "name": settings.get("main", {}).get("name", ""),
            "email": settings.get("main", {}).get("email", ""),
            "smtp_username": settings.get("main", {}).get(
                "smtp_username",
                settings.get("main", {}).get("email", ""),
            ),
            "app_password": _normalize_password(
                settings.get("main", {}).get("app_password", "")
            ),
        },
        "contacts": [],
    }

    for contact in settings.get("contacts") or []:
        payload["contacts"].append(
            {
                "name": contact.get("name", ""),
                "email": contact.get("email", ""),
                "smtp_username": contact.get(
                    "smtp_username", contact.get("email", "")
                ),
                "app_password": _normalize_password(contact.get("app_password", "")),
            }
        )

    try:
        with open(EMAIL_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        return True
    except OSError as exc:
        print(f"Error saving email_config.json: {exc}")
        return False


def save_email_config(
    *,
    smtp_username: str,
    smtp_password: str,
    sender_email: Optional[str] = None,
    receiver_email: Optional[str] = None,
    smtp_host: str = SMTP_HOST,
    smtp_port: int = SMTP_PORT,
    main_name: str = "",
    contacts: Optional[List[Dict[str, str]]] = None,
) -> bool:
    """Update email_config.json while preserving existing contacts unless overridden."""
    current = load_email_settings()
    current["smtp_host"] = smtp_host
    current["smtp_port"] = smtp_port
    current["main"] = {
        "name": main_name or current["main"].get("name", ""),
        "email": sender_email or smtp_username,
        "smtp_username": smtp_username,
        "app_password": _normalize_password(smtp_password),
    }
    if receiver_email is not None:
        current["default_receiver"] = receiver_email
    if contacts is not None:
        current["contacts"] = contacts
    return save_email_settings(current)


def _attach_file(message: MIMEMultipart, file_path: str) -> None:
    mime_type, _ = mimetypes.guess_type(file_path)
    if mime_type is None:
        mime_type = "application/octet-stream"

    main_type, sub_type = mime_type.split("/", 1)

    with open(file_path, "rb") as attachment_file:
        if main_type == "image":
            attachment = MIMEImage(attachment_file.read(), _subtype=sub_type)
        else:
            attachment = MIMEBase(main_type, sub_type)
            attachment.set_payload(attachment_file.read())
            encoders.encode_base64(attachment)

    attachment.add_header(
        "Content-Disposition",
        "attachment",
        filename=os.path.basename(file_path),
    )
    message.attach(attachment)


def build_message(
    subject: str,
    body: str,
    sender_email: str,
    receiver_email: str,
    image_path: Optional[str] = None,
    attachment_paths: Optional[List[str]] = None,
    embed_image_in_body: bool = False,
) -> MIMEMultipart:
    paths = [p for p in (attachment_paths or []) if p]
    if image_path:
        paths.append(image_path)

    if image_path and embed_image_in_body and len(paths) <= 1:
        message = MIMEMultipart("related")
        html_body = (
            body
            if "<img" in body.lower()
            else f"{body}<br><img src='cid:embedded-image'>"
        )
        message.attach(MIMEText(html_body, "html"))

        with open(image_path, "rb") as image_file:
            image_data = image_file.read()

        mime_type, _ = mimetypes.guess_type(image_path)
        if mime_type and mime_type.startswith("image/"):
            image_part = MIMEImage(image_data, _subtype=mime_type.split("/")[1])
        else:
            image_part = MIMEImage(image_data)

        image_part.add_header("Content-ID", "<embedded-image>")
        image_part.add_header(
            "Content-Disposition",
            "inline",
            filename=os.path.basename(image_path),
        )
        message.attach(image_part)
    else:
        message = MIMEMultipart()
        message.attach(MIMEText(body, "plain"))

        for path in paths:
            _attach_file(message, path)

    message["Subject"] = subject
    message["From"] = sender_email
    message["To"] = receiver_email
    return message


def _connect_starttls(smtp_host: str, smtp_port: int):
    server = smtplib.SMTP(smtp_host, smtp_port or 587, timeout=15)
    server.starttls()
    return server


def _format_auth_error(exc: smtplib.SMTPAuthenticationError, smtp_username: str):
    return smtplib.SMTPAuthenticationError(
        exc.smtp_code,
        f"Gmail rejected login for {smtp_username}. "
        "Create a NEW app password at https://myaccount.google.com/apppasswords "
        "(Mail → Other). Use that 16-char code in email_config.json or GMAIL_APP_PASSWORD. "
        "Your normal Gmail password will not work.",
    )


def connect_smtp(
    smtp_host: str,
    smtp_port: int,
    smtp_username: str,
    smtp_password: str,
):
    """Try STARTTLS (587) first, then SSL (465). Returns a logged-in SMTP connection."""
    attempts = []

    if smtp_port == 465:
        methods = [("SSL", lambda: smtplib.SMTP_SSL(smtp_host, 465, timeout=15))]
    else:
        methods = [
            ("STARTTLS", _connect_starttls),
            ("SSL", lambda: smtplib.SMTP_SSL(smtp_host, 465, timeout=15)),
        ]

    last_error = None
    for method_name, connect_fn in methods:
        server = None
        try:
            server = connect_fn(smtp_host, smtp_port)
            server.login(smtp_username, smtp_password)
            return server, method_name
        except smtplib.SMTPAuthenticationError as exc:
            if server:
                server.quit()
            raise _format_auth_error(exc, smtp_username) from exc
        except OSError as exc:
            attempts.append(f"{method_name}: {exc}")
            last_error = exc
            if server:
                try:
                    server.quit()
                except OSError:
                    pass

    raise ConnectionError(
        "Could not connect to Gmail SMTP. Tried: "
        + "; ".join(attempts or ["unknown error"])
        + (f". Last error: {last_error}" if last_error else "")
    )


def test_auth(
    smtp_username: Optional[str] = None,
    smtp_password: Optional[str] = None,
    smtp_host: Optional[str] = None,
    smtp_port: Optional[int] = None,
) -> str:
    config = _load_email_config()
    smtp_username = smtp_username or config["SMTP_USERNAME"]
    smtp_password = smtp_password or config["SMTP_PASSWORD"]
    smtp_host = smtp_host or config["SMTP_HOST"]
    smtp_port = smtp_port if smtp_port is not None else config["SMTP_PORT"]

    if not smtp_password:
        raise ValueError(
            "No password provided. Set main.app_password in email_config.json "
            "or GMAIL_APP_PASSWORD."
        )
    if not smtp_username:
        raise ValueError(
            "No sender username provided. Set main.smtp_username in email_config.json."
        )

    smtp_password = _normalize_password(smtp_password)

    server, method_name = connect_smtp(
        smtp_host, smtp_port, smtp_username, smtp_password
    )
    server.quit()
    return method_name


def send_email(
    subject: str,
    body: str,
    image_path: Optional[str] = None,
    attachment_paths: Optional[List[str]] = None,
    sender_email: Optional[str] = None,
    receiver_email: Optional[str] = None,
    contact_name: Optional[str] = None,
    smtp_host: Optional[str] = None,
    smtp_port: Optional[int] = None,
    smtp_username: Optional[str] = None,
    smtp_password: Optional[str] = None,
    embed_image_in_body: bool = False,
) -> None:
    config = _load_email_config()
    sender_email = sender_email or config["SENDER_EMAIL"]
    receiver_email = resolve_receiver(receiver_email, contact_name) or config["RECEIVER_EMAIL"]
    smtp_host = smtp_host or config["SMTP_HOST"]
    smtp_port = smtp_port if smtp_port is not None else config["SMTP_PORT"]
    smtp_username = smtp_username or config["SMTP_USERNAME"] or sender_email
    smtp_password = smtp_password or config["SMTP_PASSWORD"]

    if image_path and not os.path.isfile(image_path):
        raise FileNotFoundError(f"Image not found: {image_path}")

    all_paths = [p for p in (attachment_paths or []) if p]
    if image_path:
        all_paths.append(image_path)
    for path in all_paths:
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Attachment not found: {path}")

    if not smtp_password:
        raise ValueError(
            "No Gmail app password found. Set main.app_password in email_config.json "
            "or pass smtp_password / GMAIL_APP_PASSWORD."
        )
    if not sender_email:
        raise ValueError("No sender email configured in email_config.json main section.")
    if not receiver_email:
        raise ValueError(
            "No receiver configured. Pass receiver_email, contact_name, "
            "or set default_receiver in email_config.json."
        )

    smtp_password = _normalize_password(smtp_password)

    combined_attachments = [p for p in (attachment_paths or []) if p]
    if image_path and not embed_image_in_body and image_path not in combined_attachments:
        combined_attachments.append(image_path)

    message = build_message(
        subject=subject,
        body=body,
        sender_email=sender_email,
        receiver_email=receiver_email,
        image_path=image_path if embed_image_in_body else None,
        attachment_paths=combined_attachments if not embed_image_in_body else None,
        embed_image_in_body=embed_image_in_body,
    )

    server, _method = connect_smtp(
        smtp_host, smtp_port, smtp_username, smtp_password
    )
    try:
        server.send_message(message)
    finally:
        server.quit()
