# data/schwab_auth.py
import subprocess
import sys
import os
import shutil
import schwabdev

from config import APP_KEY, SECRET, CALLBACK_URL

def reset_schwab_tokens():
    token_dir = os.path.expanduser("~/.schwabdev")

    if os.path.exists(token_dir):
        shutil.rmtree(token_dir)
        return True

    return False

def try_create_client_with_tokens():
    """
    Try to create a Schwab client using existing tokens.
    Returns client if successful, or None if auth is required.
    """
    try:
        return schwabdev.Client(APP_KEY, SECRET, CALLBACK_URL)
    except Exception:
        return None

def run_oauth_subprocess(redirect_url: str):
    """
    Runs the OAuth helper and feeds it the redirect URL via stdin.
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

    # Feed the redirect URL exactly once
    stdout, stderr = proc.communicate(redirect_url + "\n", timeout=60)

    if proc.returncode != 0:
        raise RuntimeError(
            f"OAuth helper failed:\n{stderr or stdout}"
        )


def create_authenticated_client():
    """
    Called AFTER OAuth helper succeeds.
    Tokens already exist, so no prompts.
    """
    return schwabdev.Client(APP_KEY, SECRET, CALLBACK_URL)
