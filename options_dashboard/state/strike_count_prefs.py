from options_dashboard.data.schwab_api import DEFAULT_STRIKE_COUNT_LABEL
from options_dashboard.state.app_state import get_state_value, set_state_value


def get_per_ticker_strike_counts():
    return get_state_value("option_strike_counts", {}) or {}


def save_strike_count_label(symbol, strike_label):
    symbol = symbol.upper()
    set_state_value("option_strike_count", strike_label)
    per_ticker = dict(get_per_ticker_strike_counts())
    per_ticker[symbol] = strike_label
    set_state_value("option_strike_counts", per_ticker)


def initial_strike_count_label(symbol):
    symbol = symbol.upper()
    per_ticker = get_per_ticker_strike_counts()
    if symbol in per_ticker:
        return per_ticker[symbol]
    return get_state_value("option_strike_count", DEFAULT_STRIKE_COUNT_LABEL)


def persisted_strike_count_label(symbol):
    symbol = symbol.upper()
    per_ticker = get_per_ticker_strike_counts()
    if symbol in per_ticker:
        return per_ticker[symbol]
    return get_state_value("option_strike_count", DEFAULT_STRIKE_COUNT_LABEL)
