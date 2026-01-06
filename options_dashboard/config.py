# Default API credentials (user can override these in api_config.json via the UI)
# These are default values that come with the app (tracked in git)
APP_KEY = ""
SECRET = ""
CALLBACK_URL = "https://127.0.0.1"

# Application configuration constants (defaults that come with the app)
RISK_FREE_RATE = 0.05
DIVIDEND_YIELD = 0.015
CONTRACT_MULTIPLIER = 100

MAX_TICKERS = 24
PRESET_FILE = "preset_tickers.json"
STATE_FILE = "app_state.json"

# After defining defaults, load user overrides from config_loader if they exist
# This allows api_config.json to override the defaults
try:
    from options_dashboard.config_loader import APP_KEY, SECRET, CALLBACK_URL
except ImportError:
    # If config_loader doesn't exist or fails, use defaults above
    pass
