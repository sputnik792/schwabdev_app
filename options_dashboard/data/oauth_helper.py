# data/oauth_helper.py
import sys, os
import schwabdev

# Add project root to Python path
PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")
)
sys.path.insert(0, PROJECT_ROOT)

from config_loader import APP_KEY, SECRET, CALLBACK_URL, reload_config

def main():
    # Reload config to get latest credentials
    reload_config()
    from config_loader import APP_KEY, SECRET, CALLBACK_URL
    
    redirect_url = sys.stdin.readline().strip()
    if not redirect_url:
        raise SystemExit("No redirect URL provided on stdin")

    # Use the already-obtained redirect URL instead of opening a browser
    schwabdev.Client(
        APP_KEY,
        SECRET,
        CALLBACK_URL,
        call_on_auth=lambda auth_url: redirect_url
    )

if __name__ == "__main__":
    main()
