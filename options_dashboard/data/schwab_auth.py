import os
import sys
import subprocess
import shutil
import tempfile
import schwabdev
from config_loader import APP_KEY, SECRET, CALLBACK_URL

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
    """
    return schwabdev.Client(APP_KEY, SECRET, CALLBACK_URL)

def schwab_tokens_exist():
    token_dir = os.path.expanduser("~/.schwabdev")
    token_db = os.path.join(token_dir, "tokens.db")
    return os.path.exists(token_db)


def create_authenticated_client():
    return schwabdev.Client(APP_KEY, SECRET, CALLBACK_URL)
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
