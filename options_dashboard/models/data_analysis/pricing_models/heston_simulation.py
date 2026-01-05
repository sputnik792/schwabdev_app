import numpy as np
from scipy.stats import norm


def simulate_heston_paths(S0, v0, T, r, q, kappa, theta, sigma_v, rho, n_steps, n_paths=1):
    """
    Simulate Heston model paths using Euler-Maruyama discretization.
    
    Parameters:
    - S0: Initial stock price
    - v0: Initial variance
    - T: Time to expiration (in years)
    - r: Risk-free rate
    - q: Dividend yield
    - kappa: Mean reversion speed
    - theta: Long-run variance
    - sigma_v: Volatility of volatility
    - rho: Correlation between price and variance
    - n_steps: Number of time steps
    - n_paths: Number of paths to simulate
    
    Returns:
    - times: Array of time points
    - S_paths: Stock price paths (n_paths x n_steps+1)
    - v_paths: Variance paths (n_paths x n_steps+1)
    """
    dt = T / n_steps
    times = np.linspace(0, T, n_steps + 1)
    
    # Initialize arrays
    S_paths = np.zeros((n_paths, n_steps + 1))
    v_paths = np.zeros((n_paths, n_steps + 1))
    
    S_paths[:, 0] = S0
    v_paths[:, 0] = v0
    
    # Generate correlated random numbers
    for i in range(n_steps):
        # Generate correlated Brownian motions
        Z1 = norm.rvs(size=n_paths)
        Z2 = norm.rvs(size=n_paths)
        W1 = np.sqrt(dt) * Z1
        W2 = np.sqrt(dt) * (rho * Z1 + np.sqrt(1 - rho**2) * Z2)
        
        # Update variance (with Feller condition check)
        v_prev = np.maximum(v_paths[:, i], 0)  # Ensure non-negative
        v_new = v_prev + kappa * (theta - v_prev) * dt + sigma_v * np.sqrt(v_prev) * W2
        v_paths[:, i+1] = np.maximum(v_new, 0)  # Ensure non-negative
        
        # Update stock price
        S_prev = S_paths[:, i]
        S_new = S_prev * np.exp((r - q - 0.5 * v_prev) * dt + np.sqrt(v_prev) * W1)
        S_paths[:, i+1] = S_new
    
    return times, S_paths, v_paths


def calculate_implied_volatility_smile(S, K_list, T, r, q, v0, kappa, theta, sigma_v, rho, heston_call_price):
    """
    Calculate implied volatility smile for a range of strikes.
    
    Parameters:
    - S: Current stock price
    - K_list: List of strike prices
    - T: Time to expiration
    - r: Risk-free rate
    - q: Dividend yield
    - v0: Initial variance
    - kappa, theta, sigma_v, rho: Heston parameters
    - heston_call_price: Function to calculate Heston call price
    
    Returns:
    - strikes: Array of strikes
    - implied_vols: Array of implied volatilities
    """
    from scipy.optimize import brentq
    from models.greeks import d1, d2
    from scipy.stats import norm
    
    implied_vols = []
    valid_strikes = []
    
    for K in K_list:
        try:
            # Calculate Heston call price
            heston_price = heston_call_price(S, K, T, r, q, v0, kappa, theta, sigma_v, rho)
            
            # Invert Black-Scholes to get implied volatility
            def bs_iv_error(sigma):
                if sigma <= 0:
                    return 1e10
                try:
                    d1_val = d1(S, K, T, r, q, sigma)
                    d2_val = d2(S, K, T, r, q, sigma)
                    bs_price = S * np.exp(-q * T) * norm.cdf(d1_val) - K * np.exp(-r * T) * norm.cdf(d2_val)
                    return bs_price - heston_price
                except:
                    return 1e10
            
            # Find implied volatility using Brent's method
            try:
                iv = brentq(bs_iv_error, 0.001, 2.0, maxiter=100)
                implied_vols.append(iv)
                valid_strikes.append(K)
            except:
                # If inversion fails, skip this strike
                continue
        except:
            continue
    
    return np.array(valid_strikes), np.array(implied_vols)

