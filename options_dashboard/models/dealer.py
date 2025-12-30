import numpy as np
from models.greeks import gamma
from models.exposure import gamma_exposure

def total_gamma_at_spot(df, spot, T, r, q):
    total = 0.0
    for _, row in df.iterrows():
        K = float(row["Strike"])
        for side in ("Call", "Put"):
            iv = float(row.get(f"{side}IV", 0) or 0)
            oi = float(row.get(f"{side}OI", 0) or 0)
            sign = 1 if side == "Call" else -1
            g = gamma(spot, K, T, r, q, iv)
            total += sign * gamma_exposure(g, spot, oi)
    return total

def find_zero_gamma(df, spot_range, T, r, q):
    for i in range(len(spot_range)-1):
        g1 = total_gamma_at_spot(df, spot_range[i], T, r, q)
        g2 = total_gamma_at_spot(df, spot_range[i+1], T, r, q)
        if g1 == 0 or g1 * g2 < 0:
            return spot_range[i]
    return None
