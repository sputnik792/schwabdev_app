# data/oauth_helper.py
import sys, os
import schwabdev

# Add project root to Python path
PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")
)
sys.path.insert(0, PROJECT_ROOT)

from config import APP_KEY, SECRET, CALLBACK_URL

def main():
    # Create client (this triggers schwabdev OAuth flow)
    client = schwabdev.Client(APP_KEY, SECRET, CALLBACK_URL)

    # schwabdev will call input() internally.
    # We feed stdin from the parent process.
    # If OAuth succeeds, tokens are written and process exits.

if __name__ == "__main__":
    main()
