import os
import sys
import subprocess
import shutil
import tempfile
import schwabdev
from config_loader import APP_KEY, SECRET, CALLBACK_URL, reload_config

# -----------------------------
# OAuth subprocess bridge
# -----------------------------

def run_oauth_subprocess(redirect_url: str):
    """
    Run schwabdev OAuth in a separate process and feed the redirect URL
    to its stdin (this satisfies schwabdev's input()).
    """
    helper_path = os.path.join(
        os.path.dirname(__file__),
        "oauth_helper.py"
    )

    proc = subprocess.Popen(
        [sys.executable, helper_path],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    stdout, stderr = proc.communicate(
        redirect_url.strip() + "\n",
        timeout=60
    )

    if proc.returncode != 0:
        raise RuntimeError(
            "OAuth helper failed:\n"
            f"{stderr or stdout}"
        )

def create_authenticated_client():
    """
    Create a Schwab client assuming valid tokens already exist.
    Reloads config to ensure we have the latest credentials.
    """
    reload_config()
    from config_loader import APP_KEY, SECRET, CALLBACK_URL
    if not APP_KEY or not APP_KEY.strip():
        raise ValueError("APP_KEY cannot be None or empty. Please add API credentials first.")
    if not SECRET or not SECRET.strip():
        raise ValueError("SECRET cannot be None or empty. Please add API credentials first.")
    return schwabdev.Client(APP_KEY, SECRET, CALLBACK_URL)

def schwab_tokens_exist():
    token_dir = os.path.expanduser("~/.schwabdev")
    token_db = os.path.join(token_dir, "tokens.db")
    return os.path.exists(token_db)

def is_refresh_token_valid():
    """
    Check if the refresh token is valid by attempting to create a client
    and make a simple API call. Returns True if valid, False if expired/invalid.
    """
    if not schwab_tokens_exist():
        return False
    
    try:
        client = create_authenticated_client()
        # Try a simple API call to validate the token
        # Using a lightweight endpoint to check authentication
        from data.schwab_api import safe_call
        # Try fetching a quote for a common symbol (SPY) to validate token
        # This is a lightweight call that requires authentication
        try:
            safe_call(client.quotes, "SPY")
            return True
        except RuntimeError as e:
            if str(e) == "AUTH_REQUIRED":
                return False
            # If it's not an auth error, assume token is valid (might be network issue, etc.)
            return True
        except Exception:
            # If we can't determine (network error, etc.), assume valid
            # (better to let user try than block them)
            return True
    except Exception:
        # If we can't create a client, assume invalid
        return False
# -----------------------------
# Token reset (Windows-safe)
# -----------------------------

RESET_FLAG = os.path.join(
    tempfile.gettempdir(),
    "schwab_reset.flag"
)


def mark_schwab_reset():
    with open(RESET_FLAG, "w") as f:
        f.write("reset")


def perform_pending_reset():
    """
    Delete Schwab tokens on app startup before any client is created.
    """
    if not os.path.exists(RESET_FLAG):
        return

    token_dir = os.path.expanduser("~/.schwabdev")

    try:
        if os.path.exists(token_dir):
            shutil.rmtree(token_dir)
    finally:
        os.remove(RESET_FLAG)
