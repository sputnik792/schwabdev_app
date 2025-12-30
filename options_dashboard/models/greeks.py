from math import log, sqrt, exp
from scipy.stats import norm

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
