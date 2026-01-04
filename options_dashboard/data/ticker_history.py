"""
Ticker Search History

Tracks tickers that users have searched in single view.
Stores count and date for prioritizing autocomplete suggestions.
"""

import json
import os
import datetime
from typing import Dict, Tuple

# Path to the ticker history file (in project root, same as app_state.json)
HISTORY_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "ticker_history.json"
)


def load_ticker_history() -> Dict[str, Dict[str, any]]:
    """Load ticker search history from JSON file"""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                history = json.load(f)
                return history
        except Exception as e:
            print(f"Error loading ticker history: {e}")
            return {}
    return {}


def save_ticker_history(history: Dict[str, Dict[str, any]]):
    """Save ticker search history to JSON file"""
    try:
        with open(HISTORY_FILE, "w") as f:
            json.dump(history, f, indent=2)
    except Exception as e:
        print(f"Failed to save ticker history: {e}")


def record_ticker_search(ticker: str):
    """
    Record a ticker search in the history.
    Increments count and updates date to current date.
    
    Args:
        ticker: The ticker symbol (will be converted to uppercase)
    """
    ticker = ticker.strip().upper()
    if not ticker:
        return
    
    history = load_ticker_history()
    
    # Get current date in YYYY-MM-DD format
    current_date = datetime.date.today().strftime("%Y-%m-%d")
    
    if ticker in history:
        # Increment count and update date
        history[ticker]["count"] = history[ticker].get("count", 0) + 1
        history[ticker]["date"] = current_date
    else:
        # Create new entry
        history[ticker] = {
            "count": 1,
            "date": current_date
        }
    
    save_ticker_history(history)


def get_ticker_priority(ticker: str) -> Tuple[int, str, str]:
    """
    Get priority tuple for a ticker for sorting.
    Returns (negative_count, negative_date, ticker) for descending sort.
    
    Args:
        ticker: The ticker symbol
        
    Returns:
        Tuple of (negative_count, negative_date, ticker) for sorting
        Higher count = higher priority, more recent date = higher priority
    """
    history = load_ticker_history()
    ticker_upper = ticker.upper()
    
    if ticker_upper in history:
        entry = history[ticker_upper]
        count = entry.get("count", 0)
        date = entry.get("date", "1970-01-01")
    else:
        count = 0
        date = "1970-01-01"  # Old date for unsearched tickers
    
    # Return negative values for descending sort
    # More recent dates are "greater" in string comparison (YYYY-MM-DD format)
    # So we negate the date string comparison by using a very old date as baseline
    # Actually, for dates, we want more recent = higher priority
    # We'll use the date string directly (YYYY-MM-DD sorts correctly)
    # But we need to negate it for descending sort, so we'll use a trick:
    # Convert to sortable format where newer dates are "larger"
    # For simplicity, we'll use negative count and reverse date string
    
    # For date: newer dates should be higher priority
    # YYYY-MM-DD format: "2024-01-01" > "2023-12-31" (string comparison works)
    # To make newer dates sort first, we can use a large number minus days since epoch
    # Or simpler: use negative of date string comparison
    # Actually, let's use a simpler approach: convert date to sortable number
    
    try:
        # Convert date to days since epoch for numeric sorting
        date_obj = datetime.datetime.strptime(date, "%Y-%m-%d").date()
        epoch = datetime.date(1970, 1, 1)
        days_since_epoch = (date_obj - epoch).days
    except:
        days_since_epoch = 0
    
    # Return tuple for sorting: (negative_count, negative_days, ticker)
    # This way: higher count = higher priority, more recent = higher priority
    # We negate so that sort(reverse=True) gives us the right order
    return (-count, -days_since_epoch, ticker.upper())

