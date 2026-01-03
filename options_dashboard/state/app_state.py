import json
import os
from options_dashboard.config import STATE_FILE

def load_app_state():
    """Load application state from JSON file"""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                state = json.load(f)
                return state
        except Exception:
            pass
    return {}

def save_app_state(state):
    """Save application state to JSON file"""
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        print(f"Failed to save app state: {e}")

def get_state_value(key, default=None):
    """Get a value from app state"""
    state = load_app_state()
    return state.get(key, default)

def set_state_value(key, value):
    """Set a value in app state"""
    state = load_app_state()
    state[key] = value
    save_app_state(state)

