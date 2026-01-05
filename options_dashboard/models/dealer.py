import numpy as np
from models.greeks import gamma
from models.exposure import gamma_exposure

def total_gamma_at_spot(df, spot, T, r, q):
    total = 0.0

    # Use itertuples() instead of iterrows() for better performance
    for row in df.itertuples(index=False):
        strike = float(row.Strike) if hasattr(row, 'Strike') else 0
        if strike <= 0:
            continue
        call_iv = float(getattr(row, 'IV_Call', 0) or 0)
        put_iv  = float(getattr(row, 'IV_Put', 0) or 0)
        call_oi = float(getattr(row, 'OI_Call', 0) or 0)
        put_oi  = float(getattr(row, 'OI_Put', 0) or 0)
        if call_iv > 0 and call_oi > 0:
            g_call = gamma(spot, strike, T, r, q, call_iv)
            total += gamma_exposure(g_call, spot, call_oi)

        if put_iv > 0 and put_oi > 0:
            g_put = gamma(spot, strike, T, r, q, put_iv)
            total -= gamma_exposure(g_put, spot, put_oi)

    return total


def find_zero_gamma(df, spot_min, spot_max, steps, T, r, q):
    spots = np.linspace(spot_min, spot_max, steps)
    prev_val = None
    prev_spot = None
    for s in spots:
        g = total_gamma_at_spot(df, s, T, r, q)
        if prev_val is not None and g * prev_val < 0:
            return (s + prev_spot) / 2.0
        prev_val = g
        prev_spot = s

    return None
