import numpy as np
from scipy.integrate import quad
from scipy.optimize import minimize
from numpy import exp, log, sqrt, real
from math import pi

# === HESTON PRICER CORE ===
def heston_cf(u, S, T, r, q, v0, kappa, theta, sigma, rho):
    """Characteristic function of log price under Heston."""
    i = complex(0, 1)
    a = kappa * theta
    b = kappa
    d = np.sqrt((rho*sigma*i*u - b)**2 - sigma**2*(2*i*u*u + u**2))
    g = (b - rho*sigma*i*u + d)/(b - rho*sigma*i*u - d)
    C = (r - q)*i*u*T + (a/sigma**2)*((b - rho*sigma*i*u + d)*T - 2*np.log((1-g*np.exp(d*T))/(1-g)))
    D = ((b - rho*sigma*i*u + d)/sigma**2)*((1 - np.exp(d*T))/(1 - g*np.exp(d*T)))
    return np.exp(C + D*v0 + i*u*np.log(S))

def heston_prob(j, S, K, T, r, q, v0, kappa, theta, sigma, rho):
    """P1 and P2 integrals."""
    i = complex(0, 1)
    def integrand(u):
        phi = heston_cf(u - i*(j==1), S, T, r, q, v0, kappa, theta, sigma, rho)
        num = np.exp(-i*u*np.log(K))*phi
        denom = i*u
        return real(num/denom)
    # Increase limit and use better integration settings
    integral = quad(lambda u: integrand(u), 0, 100, limit=200, epsabs=1e-6, epsrel=1e-6)[0]
    return 0.5 + (1/pi)*integral

def heston_call_price(S, K, T, r, q, v0, kappa, theta, sigma, rho):
    """Calculate European call option price using Heston model."""
    P1 = heston_prob(1, S, K, T, r, q, v0, kappa, theta, sigma, rho)
    P2 = heston_prob(2, S, K, T, r, q, v0, kappa, theta, sigma, rho)
    return S*np.exp(-q*T)*P1 - K*np.exp(-r*T)*P2

# === NUMERICAL GREEKS ===
def heston_greeks(S, K, T, r, q, v0, kappa, theta, sigma, rho, greek="gamma", h=1e-4):
    """Finite difference approximation of chosen Greek."""
    if greek.lower() == "gamma":
        C_plus = heston_call_price(S*(1+h), K, T, r, q, v0, kappa, theta, sigma, rho)
        C_0    = heston_call_price(S,       K, T, r, q, v0, kappa, theta, sigma, rho)
        C_minus= heston_call_price(S*(1-h), K, T, r, q, v0, kappa, theta, sigma, rho)
        return (C_plus - 2*C_0 + C_minus)/(S*h)**2
    elif greek.lower() == "vega":
        C_plus = heston_call_price(S, K, T, r, q, v0*(1+h), kappa, theta, sigma, rho)
        C_minus= heston_call_price(S, K, T, r, q, v0*(1-h), kappa, theta, sigma, rho)
        return (C_plus - C_minus)/(2*v0*h)
    elif greek.lower() == "vanna":
        dS = S*h
        dV = v0*h
        C_pp = heston_call_price(S+dS, K, T, r, q, v0+dV, kappa, theta, sigma, rho)
        C_pm = heston_call_price(S+dS, K, T, r, q, v0-dV, kappa, theta, sigma, rho)
        C_mp = heston_call_price(S-dS, K, T, r, q, v0+dV, kappa, theta, sigma, rho)
        C_mm = heston_call_price(S-dS, K, T, r, q, v0-dV, kappa, theta, sigma, rho)
        return (C_pp - C_pm - C_mp + C_mm)/(4*dS*dV)
    elif greek.lower() == "charm":
        C_plus = heston_call_price(S, K, T*(1+h), r, q, v0, kappa, theta, sigma, rho)
        C_minus= heston_call_price(S, K, T*(1-h), r, q, v0, kappa, theta, sigma, rho)
        return (C_plus - C_minus)/(2*T*h)
    else:
        raise ValueError("Unknown greek: choose 'gamma', 'vega', 'vanna', 'charm'")

# === CALIBRATION ===
def black_scholes_iv_call(S, K, T, r, q, market_price, sigma_min=0.001, sigma_max=5.0):
    """
    Calculate implied volatility from market price using Black-Scholes.
    Uses Brent's method for root finding.
    """
    from scipy.optimize import brentq
    from scipy.stats import norm
    
    def bs_call_price(sigma):
        """Black-Scholes call price for given volatility"""
        if sigma <= 0:
            return 0
        try:
            d1 = (np.log(S / K) + (r - q + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
            d2 = d1 - sigma * np.sqrt(T)
            return S * np.exp(-q * T) * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
        except:
            return 0
    
    def iv_error(sigma):
        """Error between market price and BS price"""
        return bs_call_price(sigma) - market_price
    
    try:
        iv = brentq(iv_error, sigma_min, sigma_max, maxiter=100)
        return iv
    except:
        return None

def calibrate_heston_parameters(
    S0, strikes, market_prices, T, r, q, v0,
    kappa_init=2.0, theta_init=0.04, sigma_v_init=0.3, rho_init=-0.7,
    kappa_bounds=(0.1, 10.0),
    theta_bounds=(0.001, 0.5),
    sigma_v_bounds=(0.01, 1.0),
    rho_bounds=(-0.99, 0.99),
    method='L-BFGS-B',
    maxiter=200,
    callback=None
):
    """
    Calibrate Heston model parameters to market option prices using bounded optimization.
    
    Parameters:
    -----------
    S0 : float
        Current spot price
    strikes : array-like
        Array of strike prices
    market_prices : array-like
        Array of market option prices (calls or mid prices)
    T : float
        Time to expiration (in years)
    r : float
        Risk-free rate
    q : float
        Dividend yield
    v0 : float
        Initial variance (typically estimated from ATM IV)
    kappa_init : float, optional
        Initial guess for kappa (default: 2.0)
    theta_init : float, optional
        Initial guess for theta (default: 0.04)
    sigma_v_init : float, optional
        Initial guess for sigma_v (default: 0.3)
    rho_init : float, optional
        Initial guess for rho (default: -0.7)
    kappa_bounds : tuple, optional
        Bounds for kappa (default: (0.1, 10.0))
    theta_bounds : tuple, optional
        Bounds for theta (default: (0.001, 0.5))
    sigma_v_bounds : tuple, optional
        Bounds for sigma_v (default: (0.01, 1.0))
    rho_bounds : tuple, optional
        Bounds for rho (default: (-0.99, 0.99))
    method : str, optional
        Optimization method (default: 'L-BFGS-B' for bounded optimization)
    maxiter : int, optional
        Maximum number of iterations (default: 200)
    callback : callable, optional
        Callback function called after each iteration (default: None)
    
    Returns:
    --------
    result : dict
        Dictionary containing:
        - 'kappa': fitted kappa
        - 'theta': fitted theta
        - 'sigma_v': fitted sigma_v
        - 'rho': fitted rho
        - 'success': whether optimization converged
        - 'message': optimization message
        - 'fun': final objective function value
        - 'nit': number of iterations
    """
    # Convert inputs to numpy arrays
    strikes = np.array(strikes, dtype=float)
    market_prices = np.array(market_prices, dtype=float)
    
    # Filter out invalid data
    valid_mask = (strikes > 0) & (market_prices > 0) & np.isfinite(strikes) & np.isfinite(market_prices)
    strikes = strikes[valid_mask]
    market_prices = market_prices[valid_mask]
    
    if len(strikes) < 3:
        raise ValueError("Need at least 3 valid option prices for calibration")
    
    # Objective function: sum of squared errors between market and model prices
    def objective(params):
        """Objective function to minimize"""
        kappa, theta, sigma_v, rho = params
        
        # Ensure Feller condition: 2*kappa*theta > sigma_v^2
        if 2 * kappa * theta <= sigma_v**2:
            return 1e10  # Penalize invalid parameter combinations
        
        # Calculate model prices for all strikes
        model_prices = []
        for K in strikes:
            try:
                price = heston_call_price(S0, K, T, r, q, v0, kappa, theta, sigma_v, rho)
                model_prices.append(price)
            except:
                return 1e10  # Return large penalty if pricing fails
        
        model_prices = np.array(model_prices)
        
        # Calculate squared errors (with weighting by price to normalize)
        errors = (model_prices - market_prices) ** 2
        # Weight by inverse of market price to give equal relative importance
        weights = 1.0 / (market_prices + 1e-6)  # Add small epsilon to avoid division by zero
        weighted_errors = errors * weights
        
        # Return sum of weighted squared errors
        return np.sum(weighted_errors)
    
    # Initial parameter vector: [kappa, theta, sigma_v, rho]
    x0 = np.array([kappa_init, theta_init, sigma_v_init, rho_init])
    
    # Bounds for parameters
    bounds = [kappa_bounds, theta_bounds, sigma_v_bounds, rho_bounds]
    
    # Run optimization
    try:
        result = minimize(
            objective,
            x0,
            method=method,
            bounds=bounds,
            options={'maxiter': maxiter, 'disp': False},
            callback=callback
        )
        
        kappa_fit, theta_fit, sigma_v_fit, rho_fit = result.x
        
        # Validate Feller condition
        if 2 * kappa_fit * theta_fit <= sigma_v_fit**2:
            # Try to adjust sigma_v to satisfy Feller condition
            sigma_v_max = np.sqrt(2 * kappa_fit * theta_fit) * 0.99
            if sigma_v_fit > sigma_v_max:
                sigma_v_fit = sigma_v_max
                result.fun = objective([kappa_fit, theta_fit, sigma_v_fit, rho_fit])
        
        return {
            'kappa': float(kappa_fit),
            'theta': float(theta_fit),
            'sigma_v': float(sigma_v_fit),
            'rho': float(rho_fit),
            'success': result.success,
            'message': result.message,
            'fun': float(result.fun),
            'nit': int(result.nit) if hasattr(result, 'nit') else None
        }
    except Exception as e:
        raise RuntimeError(f"Calibration failed: {str(e)}")

