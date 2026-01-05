import numpy as np
from scipy.integrate import quad
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
    integral = quad(lambda u: integrand(u), 0, 100)[0]
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

