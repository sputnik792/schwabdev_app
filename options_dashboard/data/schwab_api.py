import pandas as pd
from typing import Optional

from models.greeks import normalize_iv, to_float

STRIKE_COUNT_OPTIONS = ["10", "20", "40", "60", "80", "All"]
DEFAULT_STRIKE_COUNT_LABEL = "40"


def strike_count_label_to_api(label: str) -> Optional[int]:
    if label == "All":
        return None
    return int(label)

def safe_call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        msg = str(e).lower()
        if "unauthorized" in msg or "401" in msg or "authentication" in msg:
            raise RuntimeError("AUTH_REQUIRED")
        raise


def _empty_quote(price=0.0):
    return {
        "price": float(price or 0.0),
        "close": 0.0,
        "open": 0.0,
        "high": 0.0,
        "low": 0.0,
        "change": 0.0,
        "change_pct": 0.0,
        "volume": 0.0,
        "mark": 0.0,
    }


def fetch_stock_quote(client, symbol):
    """Full quote snapshot used by Tape Tools and price refresh."""
    try:
        resp = safe_call(client.quotes, symbol)
        data = resp.json()
        sym = data.get(symbol.upper(), {}) or {}
        q = sym.get("quote") or {}
        regular = sym.get("regular") or {}
        extended = sym.get("extended") or {}

        price = to_float(
            q.get("lastPrice")
            or regular.get("regularMarketLastPrice")
            or extended.get("lastPrice")
            or q.get("mark")
        )
        close = to_float(
            q.get("closePrice")
            or regular.get("regularMarketPreviousClose")
            or q.get("previousClose")
        )
        open_px = to_float(q.get("openPrice") or regular.get("regularMarketOpen"))
        high = to_float(q.get("highPrice") or regular.get("regularMarketDayHigh"))
        low = to_float(q.get("lowPrice") or regular.get("regularMarketDayLow"))
        volume = to_float(q.get("totalVolume") or regular.get("regularMarketVolume"))
        mark = to_float(q.get("mark") or price)
        change = to_float(q.get("netChange"))
        if change == 0.0 and close > 0 and price > 0:
            change = price - close
        change_pct = to_float(
            q.get("netPercentChange")
            or q.get("netPercentChangeInDouble")
        )
        if change_pct == 0.0 and close > 0:
            change_pct = (change / close) * 100.0

        return {
            "price": price,
            "close": close,
            "open": open_px,
            "high": high,
            "low": low,
            "change": change,
            "change_pct": change_pct,
            "volume": volume,
            "mark": mark,
        }
    except RuntimeError:
        raise
    except Exception:
        return _empty_quote()


def fetch_stock_price(client, symbol):
    try:
        return float(fetch_stock_quote(client, symbol).get("price") or 0.0)
    except RuntimeError:
        raise
    except Exception:
        return 0.0


def _option_fields(opt, side):
    bid = to_float(opt.get("bid"))
    ask = to_float(opt.get("ask"))
    mark = to_float(opt.get("mark"))
    if mark <= 0 and bid > 0 and ask > 0:
        mark = (bid + ask) / 2.0
    suffix = "Call" if side == "CALL" else "Put"
    return {
        "Strike": None,
        f"Bid_{suffix}": bid,
        f"Ask_{suffix}": ask,
        f"Mark_{suffix}": mark,
        f"Delta_{suffix}": to_float(opt.get("delta")),
        f"Theta_{suffix}": to_float(opt.get("theta")),
        f"Gamma_{suffix}": to_float(opt.get("gamma")),
        f"IV_{suffix}": normalize_iv(opt.get("volatility", 0.0)),
        f"OI_{suffix}": to_float(opt.get("openInterest")),
        f"Volume_{suffix}": to_float(opt.get("totalVolume")),
    }


def fetch_option_chain(client, symbol, strike_count: Optional[int] = 40):
    try:
        kwargs = dict(
            symbol=symbol.upper(),
            contractType="ALL",
            includeUnderlyingQuote=True,
        )
        if strike_count is not None:
            kwargs["strikeCount"] = strike_count

        resp = safe_call(client.option_chains, **kwargs)

        data = resp.json()

        calls = data.get("callExpDateMap", {})
        puts  = data.get("putExpDateMap", {})

        expirations = sorted(set(calls.keys()) | set(puts.keys()))
        exp_data_map = {}

        for exp in expirations:
            call_rows = []
            put_rows  = []

            if exp in calls:
                for strike, opts in calls[exp].items():
                    opt = opts[0]
                    row = _option_fields(opt, "CALL")
                    row["Strike"] = float(strike)
                    call_rows.append(row)

            if exp in puts:
                for strike, opts in puts[exp].items():
                    opt = opts[0]
                    row = _option_fields(opt, "PUT")
                    row["Strike"] = float(strike)
                    put_rows.append(row)

            df_calls = pd.DataFrame(call_rows)
            df_puts  = pd.DataFrame(put_rows)

            if not df_calls.empty:
                df_calls = df_calls.sort_values("Strike")
            if not df_puts.empty:
                df_puts = df_puts.sort_values("Strike")

            df = pd.merge(df_calls, df_puts, on="Strike", how="outer").fillna("")
            exp_data_map[exp] = df

        return exp_data_map, expirations

    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"FETCH_FAILED: {e}")
