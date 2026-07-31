"""
Test script for Gmail email sending.

Run from the options_dashboard folder:
    python utils/test_email.py --test-auth --password "your-app-password"
    python utils/test_email.py --subject "Test" --body "Hello from dashboard" --receiver you@example.com

Or from the repo root:
    python options_dashboard/utils/test_email.py --test-auth

Unit tests (no network):
    python utils/test_email.py --unit-tests
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

_OPTIONS_DASHBOARD = Path(__file__).resolve().parents[1]
for path in (_OPTIONS_DASHBOARD, _OPTIONS_DASHBOARD.parent):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from utils.email_sender import (  # noqa: E402
    _load_email_config,
    build_message,
    find_contact,
    get_contacts,
    get_main_account,
    load_email_settings,
    resolve_receiver,
    send_email,
    test_auth,
)


class ConfigTests(unittest.TestCase):
    def test_load_email_settings(self):
        sample = {
            "smtp_host": "smtp.gmail.com",
            "smtp_port": 587,
            "main": {
                "name": "Kevin",
                "email": "kevin@test.com",
                "smtp_username": "kevin@test.com",
                "app_password": "abcd efgh ijkl mnop",
            },
            "default_receiver": "jean@test.com",
            "contacts": [
                {"name": "Jean", "email": "jean@test.com"},
            ],
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "email_config.json"
            config_path.write_text(json.dumps(sample), encoding="utf-8")
            with patch("utils.email_sender.EMAIL_CONFIG_FILE", config_path):
                settings = load_email_settings()
                self.assertEqual(settings["main"]["name"], "Kevin")
                self.assertEqual(settings["main"]["app_password"], "abcdefghijklmnop")
                self.assertEqual(len(settings["contacts"]), 1)
                self.assertEqual(find_contact("Jean")["email"], "jean@test.com")
                self.assertEqual(resolve_receiver(contact_name="Jean"), "jean@test.com")


class BuildMessageTests(unittest.TestCase):
    def test_plain_text_message(self):
        msg = build_message(
            subject="Hello",
            body="Plain body",
            sender_email="sender@test.com",
            receiver_email="receiver@test.com",
        )
        self.assertEqual(msg["Subject"], "Hello")
        self.assertEqual(msg["From"], "sender@test.com")
        self.assertEqual(msg["To"], "receiver@test.com")
        payload = msg.get_payload()
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0].get_payload(decode=True).decode(), "Plain body")

    def test_attachment_message(self):
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp.write(b"\x89PNG\r\n\x1a\n")
            image_path = tmp.name

        try:
            msg = build_message(
                subject="Chart",
                body="See attached",
                sender_email="sender@test.com",
                receiver_email="receiver@test.com",
                image_path=image_path,
            )
            parts = msg.get_payload()
            self.assertEqual(len(parts), 2)
            self.assertEqual(parts[0].get_payload(decode=True).decode(), "See attached")
            self.assertEqual(
                parts[1]["Content-Disposition"],
                f'attachment; filename="{os.path.basename(image_path)}"',
            )
        finally:
            os.unlink(image_path)

    def test_embedded_image_message(self):
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp.write(b"\xff\xd8\xff")
            image_path = tmp.name

        try:
            msg = build_message(
                subject="Inline",
                body="Body text",
                sender_email="sender@test.com",
                receiver_email="receiver@test.com",
                image_path=image_path,
                embed_image_in_body=True,
            )
            parsed = msg.as_bytes().decode("utf-8", errors="replace")
            self.assertIn("embedded-image", parsed)
            self.assertIn("text/html", parsed)
        finally:
            os.unlink(image_path)


class SendEmailTests(unittest.TestCase):
    @patch("utils.email_sender.connect_smtp")
    @patch("utils.email_sender._load_email_config")
    def test_send_email_calls_smtp(self, mock_config, mock_connect):
        mock_config.return_value = {
            "SMTP_HOST": "smtp.gmail.com",
            "SMTP_PORT": 587,
            "SMTP_USERNAME": "sender@test.com",
            "SMTP_PASSWORD": "abcdefghijklmnop",
            "SENDER_EMAIL": "sender@test.com",
            "RECEIVER_EMAIL": "receiver@test.com",
        }
        mock_server = MagicMock()
        mock_connect.return_value = (mock_server, "STARTTLS")

        send_email(
            subject="Test",
            body="Body",
            smtp_password="abcdefghijklmnop",
            sender_email="sender@test.com",
            receiver_email="receiver@test.com",
        )

        mock_connect.assert_called_once()
        mock_server.send_message.assert_called_once()
        mock_server.quit.assert_called_once()


def parse_args():
    parser = argparse.ArgumentParser(
        description="Test Gmail email sending for the options dashboard."
    )
    parser.add_argument("--subject", help="Email subject line")
    parser.add_argument("--body", help="Email body text")
    parser.add_argument(
        "--password",
        help="Gmail app password (or set GMAIL_APP_PASSWORD env var)",
    )
    parser.add_argument(
        "--test-auth",
        action="store_true",
        help="Only test Gmail login, do not send an email",
    )
    parser.add_argument(
        "--unit-tests",
        action="store_true",
        help="Run offline unit tests (no SMTP connection)",
    )
    parser.add_argument(
        "--image",
        help="Path to an image file to attach or embed in the email",
    )
    parser.add_argument(
        "--embed-image",
        action="store_true",
        help="Embed the image in the HTML body instead of attaching it",
    )
    parser.add_argument("--sender", help="Sender email address")
    parser.add_argument("--receiver", help="Receiver email address")
    parser.add_argument(
        "--contact",
        help="Send to a named contact from email_config.json contacts list",
    )
    parser.add_argument(
        "--list-contacts",
        action="store_true",
        help="Print main account and contacts from email_config.json",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if args.unit_tests:
        suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        raise SystemExit(0 if result.wasSuccessful() else 1)

    config = _load_email_config()
    password = (args.password or config["SMTP_PASSWORD"] or "").strip()
    sender = args.sender or config["SENDER_EMAIL"]
    receiver = args.receiver or config["RECEIVER_EMAIL"]

    if args.list_contacts:
        main = get_main_account()
        print("Main account:")
        print(f"  Name:  {main.get('name') or '(not set)'}")
        print(f"  Email: {main.get('email') or '(not set)'}")
        print(f"  SMTP:  {main.get('smtp_username') or '(not set)'}")
        print(f"  Password configured: {'yes' if main.get('app_password') else 'no'}")
        print()
        print("Contacts:")
        contacts = get_contacts()
        if not contacts:
            print("  (none)")
        for contact in contacts:
            creds = " (has SMTP creds)" if contact.get("app_password") else ""
            print(f"  - {contact.get('name')}: {contact.get('email')}{creds}")
        print()
        print(f"Default receiver: {config['RECEIVER_EMAIL'] or '(not set)'}")
        return

    if args.test_auth:
        if not password:
            raise SystemExit(
                "Provide --password or set GMAIL_APP_PASSWORD / email_config.json."
            )
        print(f"Testing login for: {sender or config['SMTP_USERNAME']}")
        print(f"Password length: {len(password.replace(' ', ''))} chars (expect 16)")
        method = test_auth(
            smtp_username=sender or config["SMTP_USERNAME"],
            smtp_password=password,
        )
        print(f"Connected via {method}.")
        print("Authentication successful.")
        return

    if not args.subject or not args.body:
        raise SystemExit(
            "Sending email requires --subject and --body "
            "(or use --test-auth / --unit-tests)."
        )

    if args.contact:
        receiver = resolve_receiver(contact_name=args.contact)
    elif args.receiver:
        receiver = args.receiver

    send_email(
        subject=args.subject,
        body=args.body,
        image_path=args.image,
        sender_email=sender or None,
        receiver_email=receiver or None,
        smtp_password=password or None,
        embed_image_in_body=args.embed_image,
    )
    print(f"Email sent from {sender} to {receiver}.")


if __name__ == "__main__":
    main()
