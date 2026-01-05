"""
Test file to fetch and display options data for a single stock.
This allows for modular testing of options data fetching functionality.
"""

import numpy as np
import pandas as pd
from scipy.stats import norm

from data.schwab_auth import (
    create_authenticated_client,
    schwab_tokens_exist
)
from data.schwab_api import (
    fetch_stock_price,
    fetch_option_chain
)
from utils.time import time_to_expiration
from config import RISK_FREE_RATE


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
            d2 = (np.log(S / K) + (r - 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
            
            # For calls: Prob ITM = N(d2)
            # Lower strikes (K < S) should have higher Prob ITM
            df.loc[idx, 'Prob_ITM_Call'] = norm.cdf(d2)
            
            # For puts: Prob ITM = N(-d2)
            # Higher strikes (K > S) should have higher Prob ITM
            df.loc[idx, 'Prob_ITM_Put'] = norm.cdf(-d2)
        except (ValueError, ZeroDivisionError):
            pass
    
    return df


def print_options_data(symbol):
    """Fetch and print options data for a given symbol."""
    
    # Check if authentication tokens exist
    if not schwab_tokens_exist():
        print(f"Error: Schwab authentication tokens not found.")
        print("Please authenticate through the main app first.")
        return
    
    # Create authenticated client
    print(f"Creating authenticated client...")
    client = create_authenticated_client()
    
    # Fetch stock price
    print(f"\nFetching stock price for {symbol}...")
    try:
        price = fetch_stock_price(client, symbol)
        print(f"Current {symbol} Price: ${price:.2f}")
    except Exception as e:
        print(f"Error fetching stock price: {e}")
        return
    
    # Fetch options chain
    print(f"\nFetching options chain for {symbol}...")
    try:
        exp_data_map, expirations = fetch_option_chain(client, symbol)
        print(f"Found {len(expirations)} expiration dates")
        print(f"Expiration dates: {', '.join(expirations[:5])}{'...' if len(expirations) > 5 else ''}")
    except Exception as e:
        print(f"Error fetching options chain: {e}")
        return
    
    # Calculate Prob ITM for each expiration
    for exp_date in expirations:
        df = exp_data_map[exp_date]
        if df.empty:
            continue
        
        # Calculate time to expiration
        T = time_to_expiration(exp_date)
        
        # Calculate Prob ITM and update the DataFrame in the map
        exp_data_map[exp_date] = calculate_prob_itm(df, price, T, RISK_FREE_RATE)
    
    # Print Prob ITM results for first expiration only
    if not expirations:
        print("\nNo expiration dates found.")
        return
    
    exp_date = expirations[1]
    df = exp_data_map[exp_date]
    
    if df.empty:
        print(f"\nNo options data available for {exp_date}.")
        return
    
    print("\n" + "="*100)
    print(f"PROBABILITY ITM FOR {symbol} - {exp_date}")
    print("="*100)
    
    print("\nProb ITM for puts:")
    # Sort by strike for better readability
    df_sorted = df.sort_values('Strike')
    for idx in df_sorted.index:
        strike = df_sorted.loc[idx, 'Strike']
        prob_put = df_sorted.loc[idx, 'Prob_ITM_Put']
        
        if pd.notna(prob_put):
            prob_str = f"{prob_put * 100:.2f}%"
            print(f"  - {strike}: {prob_str}")
    
    print("\nProb ITM for calls:")
    for idx in df_sorted.index:
        strike = df_sorted.loc[idx, 'Strike']
        prob_call = df_sorted.loc[idx, 'Prob_ITM_Call']
        
        if pd.notna(prob_call):
            prob_str = f"{prob_call * 100:.2f}%"
            print(f"  - {strike}: {prob_str}")
    
    print("\n" + "="*100)
    


if __name__ == "__main__":
    symbol = "SPY"
    print(f"Testing options data fetch for {symbol}")
    print_options_data(symbol)

