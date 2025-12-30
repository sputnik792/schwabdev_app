from config import CONTRACT_MULTIPLIER

def gamma_exposure(gamma, S, oi):
    return gamma * oi * CONTRACT_MULTIPLIER * (S**2) * 0.01

def vanna_exposure(vanna, S, sigma, oi):
    return vanna * oi * CONTRACT_MULTIPLIER * S * sigma

def volga_exposure(volga, vega, oi):
    return volga * oi * vega

def charm_exposure(charm, S, oi):
    return charm * oi * CONTRACT_MULTIPLIER * S
