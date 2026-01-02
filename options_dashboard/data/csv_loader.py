import pandas as pd
import numpy as np
import json
import os
import datetime
from options_dashboard.utils.expiration import normalize_expiration

def load_csv_index(
    symbol,
    filename,
    max_expirations=None
):
    """
    Returns:
        exp_data_map: dict[str, pd.DataFrame]
        expirations: list[str]
        spot_price: float
        display_symbol: str
    """

    with open(filename, "r") as f:
        lines = f.readlines()

    # Spot price (CBOE format: line 2)
    try:
        spot_line = lines[1]
        spot_price = float(spot_line.split("Last:")[1].split(",")[0])
    except Exception:
        spot_price = 0.0

    # Parse options table
    df = pd.read_csv(
        filename,
        sep=",",
        header=None,
        comment="#",
        skip_blank_lines=True
    )

    df.columns = [
        "ExpirationDate",
        "Calls","CallLastSale","CallNet","CallBid","CallAsk","CallVol",
        "CallIV","CallDelta","CallGamma","CallOpenInt",
        "Strike",
        "Puts","PutLastSale","PutNet","PutBid","PutAsk","PutVol",
        "PutIV","PutDelta","PutGamma","PutOpenInt"
    ]

    for col in [
        "Strike","CallIV","PutIV","CallDelta","PutDelta",
        "CallGamma","PutGamma","CallOpenInt","PutOpenInt"
    ]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df["ExpirationDate"] = pd.to_datetime(df["ExpirationDate"], errors="coerce")

    exp_data_map = {}
    expirations = []

    for exp_date, group in df.groupby("ExpirationDate"):
        if pd.isna(exp_date):
            continue

        exp_key = normalize_expiration(exp_date)
        expirations.append(exp_key)

        clean_df = pd.DataFrame({
            "Strike": group["Strike"],

            "Bid_Call": group["CallBid"].replace(0, ""),
            "Ask_Call": group["CallAsk"].replace(0, ""),
            "Delta_Call": group["CallDelta"],
            "Theta_Call": np.zeros(len(group)),
            "Gamma_Call": group["CallGamma"],
            "IV_Call": group["CallIV"],
            "OI_Call": group["CallOpenInt"],

            "Bid_Put": group["PutBid"].replace(0, ""),
            "Ask_Put": group["PutAsk"].replace(0, ""),
            "Delta_Put": group["PutDelta"],
            "Theta_Put": np.zeros(len(group)),
            "Gamma_Put": group["PutGamma"],
            "IV_Put": group["PutIV"],
            "OI_Put": group["PutOpenInt"],
        }).sort_values("Strike")

        exp_data_map[exp_key] = clean_df

    if max_expirations:
        expirations = expirations[:max_expirations]

    return (
        exp_data_map,
        expirations,
        spot_price,
        f"{symbol} (CSV)"
    )
