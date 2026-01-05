from math import log, sqrt, exp
from scipy.stats import norm
import numpy as np
import pandas as pd

def d1(S, K, T, r, q, sigma):
    return (log(S / K) + (r - q + 0.5 * sigma**2) * T) / (sigma * sqrt(T))

def d2(S, K, T, r, q, sigma):
    return d1(S, K, T, r, q, sigma) - sigma * sqrt(T)

def gamma(S, K, T, r, q, sigma):
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return 0.0
    return exp(-q * T) * norm.pdf(d1(S, K, T, r, q, sigma)) / (S * sigma * sqrt(T))

def vega(S, K, T, r, q, sigma):
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return 0.0
    return S * exp(-q * T) * norm.pdf(d1(S, K, T, r, q, sigma)) * sqrt(T)

def vanna(S, K, T, r, q, sigma):
    if T <= 0 or sigma <= 0:
        return 0.0
    return exp(-q * T) * norm.pdf(d1(S, K, T, r, q, sigma)) * d2(S, K, T, r, q, sigma) / sigma

def volga(S, K, T, r, q, sigma):
    if T <= 0 or sigma <= 0:
        return 0.0
    v = vega(S, K, T, r, q, sigma)
    return v * d1(S, K, T, r, q, sigma) * d2(S, K, T, r, q, sigma) / sigma

def charm(S, K, T, r, q, sigma):
    if T <= 0 or sigma <= 0:
        return 0.0
    d1v = d1(S, K, T, r, q, sigma)
    d2v = d2(S, K, T, r, q, sigma)
    return (
        q * exp(-q * T) * norm.cdf(d1v)
        - exp(-q * T) * norm.pdf(d1v)
        * ((2 * (r - q) * T - d2v * sigma * sqrt(T)) / (2 * T * sigma * sqrt(T)))
    )

def calculate_prob_itm(df, S, T, r):
    """
    Calculate Probability ITM for calls and puts.
    
    For calls: Prob ITM = N(d2)
    For puts: Prob ITM = N(-d2)
    
    Where: d2 = (ln(S/K) + (r - 0.5 * σ^2) * T) / (σ * sqrt(T))
    
    Args:
        df: DataFrame with Strike, IV_Call, IV_Put columns
        S: Current stock price
        T: Time to expiration in years
        r: Risk-free rate
    
    Returns:
        DataFrame with Prob_ITM_Call and Prob_ITM_Put columns added
    """
    df = df.copy()
    
    # Ensure numeric types
    df['IV_Call'] = pd.to_numeric(df['IV_Call'], errors='coerce')
    df['IV_Put'] = pd.to_numeric(df['IV_Put'], errors='coerce')
    df['Strike'] = pd.to_numeric(df['Strike'], errors='coerce')
    
    # Initialize Prob ITM columns
    df['Prob_ITM_Call'] = np.nan
    df['Prob_ITM_Put'] = np.nan
    
    # Calculate d2 and Prob ITM for each row
    for idx in df.index:
        K = df.loc[idx, 'Strike']
        iv_call = df.loc[idx, 'IV_Call']
        iv_put = df.loc[idx, 'IV_Put']
        
        # Skip if invalid data
        if pd.isna(K) or K <= 0 or T <= 0 or S <= 0:
            continue
        
        # Convert IV from percentage to decimal if needed (if IV > 1, assume it's percentage)
        if not pd.isna(iv_call) and iv_call > 0:
            if iv_call > 1:
                iv_call = iv_call / 100.0
        else:
            iv_call = None
            
        if not pd.isna(iv_put) and iv_put > 0:
            if iv_put > 1:
                iv_put = iv_put / 100.0
        else:
            iv_put = None
        
        # Use the same volatility for both call and put at the same strike
        # Prefer IV_Call, fallback to IV_Put, or use average if both available
        if iv_call is not None and iv_put is not None:
            sigma = (iv_call + iv_put) / 2.0
        elif iv_call is not None:
            sigma = iv_call
        elif iv_put is not None:
            sigma = iv_put
        else:
            continue  # Skip if no valid IV
        
        # Calculate d2 (same for both calls and puts at same strike)
        try:
            d2_val = (np.log(S / K) + (r - 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
            
            # For calls: Prob ITM = N(d2)
            # Lower strikes (K < S) should have higher Prob ITM
            df.loc[idx, 'Prob_ITM_Call'] = norm.cdf(d2_val)
            
            # For puts: Prob ITM = N(-d2)
            # Higher strikes (K > S) should have higher Prob ITM
            df.loc[idx, 'Prob_ITM_Put'] = norm.cdf(-d2_val)
        except (ValueError, ZeroDivisionError):
            pass
    
    return df
