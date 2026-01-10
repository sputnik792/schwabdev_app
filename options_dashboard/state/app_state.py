import json
import os
from pathlib import Path
from config import STATE_FILE

def get_state_file_path():
    """Get the absolute path to the state file"""
    # If STATE_FILE is already absolute, use it
    if os.path.isabs(STATE_FILE):
        return STATE_FILE
    # Otherwise, resolve relative to project root (where app.py is)
    project_root = Path(__file__).resolve().parent.parent.parent
    return project_root / STATE_FILE

def load_app_state():
    """Load application state from JSON file"""
    state_path = get_state_file_path()
    if os.path.exists(state_path):
        try:
            with open(state_path, "r") as f:
                state = json.load(f)
                return state
        except Exception as e:
            print(f"Failed to load app state: {e}")
    return {}

def save_app_state(state):
    """Save application state to JSON file"""
    try:
        state_path = get_state_file_path()
        with open(state_path, "w") as f:
            json.dump(state, f, indent=2)
        print(f"[APP STATE] Saved to: {state_path}")  # Debug print
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

