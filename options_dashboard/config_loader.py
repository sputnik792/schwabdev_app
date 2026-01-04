"""
Configuration loader that reads API credentials from JSON file.
Falls back to defaults from config.py if JSON file doesn't exist.
"""
import json
from pathlib import Path

# Import defaults from config.py (the tracked file with default settings)
from options_dashboard.config import APP_KEY as _DEFAULT_APP_KEY
from options_dashboard.config import SECRET as _DEFAULT_SECRET
from options_dashboard.config import CALLBACK_URL as _DEFAULT_CALLBACK_URL

# Path to API config JSON file (relative to this file)
# This file is gitignored and contains user-entered credentials
_CONFIG_DIR = Path(__file__).resolve().parent
API_CONFIG_FILE = _CONFIG_DIR / "api_config.json"

def _load_api_config():
    """
    Load API credentials from JSON file, or return defaults from config.py if file doesn't exist.
    The JSON file is generated when user edits credentials via the UI.
    """
    if API_CONFIG_FILE.exists():
        try:
            with open(API_CONFIG_FILE, "r") as f:
                config = json.load(f)
            return {
                "APP_KEY": config.get("APP_KEY", _DEFAULT_APP_KEY),
                "SECRET": config.get("SECRET", _DEFAULT_SECRET),
                "CALLBACK_URL": config.get("CALLBACK_URL", _DEFAULT_CALLBACK_URL),
            }
        except (json.JSONDecodeError, IOError) as e:
            # If file is corrupted, return defaults from config.py
            print(f"Warning: Could not read api_config.json: {e}. Using default values from config.py.")
            return {
                "APP_KEY": _DEFAULT_APP_KEY,
                "SECRET": _DEFAULT_SECRET,
                "CALLBACK_URL": _DEFAULT_CALLBACK_URL,
            }
    else:
        # File doesn't exist, use defaults from config.py
        return {
            "APP_KEY": _DEFAULT_APP_KEY,
            "SECRET": _DEFAULT_SECRET,
            "CALLBACK_URL": _DEFAULT_CALLBACK_URL,
        }

def save_api_config(app_key: str, secret: str, callback_url: str = None):
    """Save API credentials to JSON file (user-entered values, gitignored)."""
    config = {
        "APP_KEY": app_key,
        "SECRET": secret,
    }
    if callback_url:
        config["CALLBACK_URL"] = callback_url
    
    try:
        with open(API_CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)
        return True
    except IOError as e:
        print(f"Error saving api_config.json: {e}")
        return False

# Load config once at module import
# This will use api_config.json if it exists, otherwise use defaults from config.py
_api_config = _load_api_config()
APP_KEY = _api_config["APP_KEY"]
SECRET = _api_config["SECRET"]
CALLBACK_URL = _api_config["CALLBACK_URL"]

