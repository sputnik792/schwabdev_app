"""
Tape overlays: DEX, volume vs OI, IV smile/skew, expected vs realized move.
"""

from __future__ import annotations

from math import sqrt
from typing import Dict, Optional

import pandas as pd

from config import CONTRACT_MULTIPLIER, DIVIDEND_YIELD, RISK_FREE_RATE
from models.greeks import bs_delta, gamma, normalize_iv, to_float
from utils.time import time_to_expiration

CONTRACT_MULT = CONTRACT_MULTIPLIER


def _num(row, key, default=0.0):
    return to_float(row.get(key, default) if hasattr(row, "get") else getattr(row, key, default), default)


def atm_strike(df: pd.DataFrame, spot: float) -> Optional[float]:
    strikes = [to_float(s) for s in df["Strike"].tolist() if to_float(s) > 0]
    if not strikes or spot <= 0:
        return None
    return min(strikes, key=lambda k: abs(k - spot))


def build_dex_rows(df: pd.DataFrame, spot: float, expiration: str) -> pd.DataFrame:
    T = time_to_expiration(expiration)
    rows = []
    for _, row in df.iterrows():
        k = _num(row, "Strike")
        if k <= 0:
            continue
        for side in ("Call", "Put"):
            oi = _num(row, f"OI_{side}")
            if oi <= 0:
                continue
            chain_delta = _num(row, f"Delta_{side}")
            iv = normalize_iv(_num(row, f"IV_{side}"))
            if abs(chain_delta) < 1e-8 and iv > 0 and spot > 0:
                chain_delta = bs_delta(
                    spot, k, T, RISK_FREE_RATE, DIVIDEND_YIELD, iv, side.upper()
                )
            dex = chain_delta * oi * CONTRACT_MULT * spot
            rows.append({
                "Strike": k,
                "Type": side.upper(),
                "Exposure": dex,
            })
    return pd.DataFrame(rows)


def build_volume_oi_rows(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in df.iterrows():
        k = _num(row, "Strike")
        if k <= 0:
            continue
        for side in ("Call", "Put"):
            rows.append({
                "Strike": k,
                "Type": side.upper(),
                "OpenInterest": _num(row, f"OI_{side}"),
                "Volume": _num(row, f"Volume_{side}"),
            })
    return pd.DataFrame(rows)


def build_iv_smile_rows(df: pd.DataFrame, spot: float) -> pd.DataFrame:
    rows = []
    for _, row in df.iterrows():
        k = _num(row, "Strike")
        if k <= 0:
            continue
        for side in ("Call", "Put"):
            iv = normalize_iv(_num(row, f"IV_{side}"))
            if iv <= 0:
                continue
            rows.append({
                "Strike": k,
                "Type": side.upper(),
                "IV": iv * 100.0,
            })
    return pd.DataFrame(rows)


def build_gamma_compare_rows(df: pd.DataFrame, spot: float, expiration: str) -> pd.DataFrame:
    T = time_to_expiration(expiration)
    rows = []
    for _, row in df.iterrows():
        k = _num(row, "Strike")
        if k <= 0:
            continue
        for side in ("Call", "Put"):
            oi = _num(row, f"OI_{side}")
            if oi <= 0:
                continue
            iv = normalize_iv(_num(row, f"IV_{side}"))
            chain_g = abs(_num(row, f"Gamma_{side}"))
            bs_g = abs(gamma(spot, k, T, RISK_FREE_RATE, DIVIDEND_YIELD, iv)) if iv > 0 else 0.0
            rows.append({
                "Strike": k,
                "Type": side.upper(),
                "ChainGamma": chain_g,
                "BSGamma": bs_g,
            })
    return pd.DataFrame(rows)


def expected_moves(df: pd.DataFrame, spot: float, expiration: str) -> Dict[str, float]:
    """ATM straddle expected move to expiry, plus a 1-session estimate."""
    k = atm_strike(df, spot)
    result = {
        "atm_strike": k or 0.0,
        "straddle": 0.0,
        "exp_move": 0.0,
        "exp_move_pct": 0.0,
        "day_move": 0.0,
        "day_move_pct": 0.0,
        "atm_iv": 0.0,
        "dte_years": time_to_expiration(expiration),
    }
    if not k or spot <= 0:
        return result

    row = df.loc[df["Strike"].apply(to_float) == k]
    if row.empty:
        return result
    row = row.iloc[0]
    call_mid = _num(row, "Mark_Call")
    put_mid = _num(row, "Mark_Put")
    if call_mid <= 0:
        bid, ask = _num(row, "Bid_Call"), _num(row, "Ask_Call")
        call_mid = (bid + ask) / 2.0 if bid > 0 and ask > 0 else bid
    if put_mid <= 0:
        bid, ask = _num(row, "Bid_Put"), _num(row, "Ask_Put")
        put_mid = (bid + ask) / 2.0 if bid > 0 and ask > 0 else bid
    straddle = call_mid + put_mid
    atm_iv = (normalize_iv(_num(row, "IV_Call")) + normalize_iv(_num(row, "IV_Put"))) / 2.0
    T = max(result["dte_years"], 1 / 365.0)
    iv_move = spot * atm_iv * sqrt(T) if atm_iv > 0 else straddle
    exp_move = straddle if straddle > 0 else iv_move
    day_move = spot * atm_iv * sqrt(1 / 365.0) if atm_iv > 0 else exp_move * sqrt(min(1.0, (1 / 365.0) / T))

    result.update({
        "straddle": straddle,
        "exp_move": exp_move,
        "exp_move_pct": (exp_move / spot) * 100.0 if spot else 0.0,
        "day_move": day_move,
        "day_move_pct": (day_move / spot) * 100.0 if spot else 0.0,
        "atm_iv": atm_iv * 100.0,
    })
    return result


def realized_day_move(quote: Dict, spot: float) -> Dict[str, float]:
    quote = quote or {}
    close = to_float(quote.get("close"))
    high = to_float(quote.get("high"))
    low = to_float(quote.get("low"))
    change = to_float(quote.get("change"))
    if change == 0.0 and close > 0:
        change = spot - close
    rng = high - low if high > 0 and low > 0 else abs(change)
    return {
        "close": close,
        "open": to_float(quote.get("open")),
        "high": high,
        "low": low,
        "change": change,
        "change_pct": to_float(quote.get("change_pct")) if quote.get("change_pct") else (
            (change / close) * 100.0 if close else 0.0
        ),
        "range": rng,
        "range_pct": (rng / close) * 100.0 if close else 0.0,
    }


def skew_metrics(df: pd.DataFrame, spot: float) -> Dict[str, float]:
    """Approximate 25-delta skew using listed deltas, plus put/call IV at ~5% OTM."""
    metrics = {
        "put_25d_iv": 0.0,
        "call_25d_iv": 0.0,
        "skew_25d": 0.0,
        "otm_put_iv": 0.0,
        "otm_call_iv": 0.0,
        "risk_reversal": 0.0,
        "call_oi": 0.0,
        "put_oi": 0.0,
        "call_volume": 0.0,
        "put_volume": 0.0,
        "pc_oi": 0.0,
        "pc_volume": 0.0,
    }
    if df is None or df.empty or spot <= 0:
        return metrics

    metrics["call_oi"] = sum(_num(row, "OI_Call") for _, row in df.iterrows())
    metrics["put_oi"] = sum(_num(row, "OI_Put") for _, row in df.iterrows())
    metrics["call_volume"] = sum(_num(row, "Volume_Call") for _, row in df.iterrows())
    metrics["put_volume"] = sum(_num(row, "Volume_Put") for _, row in df.iterrows())
    metrics["pc_oi"] = metrics["put_oi"] / metrics["call_oi"] if metrics["call_oi"] else 0.0
    metrics["pc_volume"] = (
        metrics["put_volume"] / metrics["call_volume"] if metrics["call_volume"] else 0.0
    )

    put_candidates = []
    call_candidates = []
    for _, row in df.iterrows():
        put_d = abs(_num(row, "Delta_Put"))
        call_d = abs(_num(row, "Delta_Call"))
        if 0.15 <= put_d <= 0.35:
            put_candidates.append((abs(put_d - 0.25), normalize_iv(_num(row, "IV_Put"))))
        if 0.15 <= call_d <= 0.35:
            call_candidates.append((abs(call_d - 0.25), normalize_iv(_num(row, "IV_Call"))))

    if put_candidates:
        metrics["put_25d_iv"] = min(put_candidates)[1] * 100.0
    if call_candidates:
        metrics["call_25d_iv"] = min(call_candidates)[1] * 100.0
    metrics["skew_25d"] = metrics["put_25d_iv"] - metrics["call_25d_iv"]

    put_k = spot * 0.95
    call_k = spot * 1.05
    def _nearest_iv(target, col):
        best = None
        best_iv = 0.0
        for _, row in df.iterrows():
            k = _num(row, "Strike")
            iv = normalize_iv(_num(row, col))
            if k <= 0 or iv <= 0:
                continue
            dist = abs(k - target)
            if best is None or dist < best:
                best = dist
                best_iv = iv
        return best_iv * 100.0

    metrics["otm_put_iv"] = _nearest_iv(put_k, "IV_Put")
    metrics["otm_call_iv"] = _nearest_iv(call_k, "IV_Call")
    metrics["risk_reversal"] = metrics["otm_put_iv"] - metrics["otm_call_iv"]
    return metrics


SEMI_BOOK_TICKERS = ("SOXL", "SOXX", "NVDA")


def nearest_expiration(state, preferred_date: Optional[str] = None) -> Optional[str]:
    keys = list((state.exp_data_map or {}).keys())
    if not keys:
        return None

    def _date(key: str) -> str:
        return key.split(":")[0] if ":" in key else key

    if preferred_date:
        exact = [k for k in keys if _date(k) == preferred_date]
        if exact:
            return sorted(exact)[0]
    return sorted(keys, key=_date)[0]


def summarize_tape(state, expiration: str) -> Dict:
    df = state.exp_data_map.get(expiration) if state else None
    spot = float(getattr(state, "price", 0) or 0)
    quote = getattr(state, "quote", None) or {}
    empty = {
        "symbol": getattr(state, "symbol", ""),
        "spot": spot,
        "expiration": expiration or "",
        "error": "no chain" if df is None or getattr(df, "empty", True) else "",
    }
    if df is None or df.empty or spot <= 0:
        empty.update({
            "expect": expected_moves(df if df is not None else pd.DataFrame(columns=["Strike"]), spot, expiration or ""),
            "realized": realized_day_move(quote, spot),
            "skew": skew_metrics(df if df is not None else pd.DataFrame(), spot),
            "net_dex": 0.0,
        })
        return empty

    dex = build_dex_rows(df, spot, expiration)
    net_dex = float(dex["Exposure"].sum()) if dex is not None and not dex.empty else 0.0
    return {
        "symbol": getattr(state, "symbol", ""),
        "spot": spot,
        "expiration": expiration,
        "error": "",
        "expect": expected_moves(df, spot, expiration),
        "realized": realized_day_move(quote, spot),
        "skew": skew_metrics(df, spot),
        "dex": dex,
        "net_dex": net_dex,
        "last_updated": getattr(state, "last_updated", None),
    }
