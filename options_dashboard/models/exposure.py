from config import CONTRACT_MULTIPLIER

def gamma_exposure(gamma, spot, oi):
    return gamma * oi * CONTRACT_MULTIPLIER * (spot ** 2) * 0.01

def vanna_exposure(vanna, spot, iv, oi):
    return vanna * oi * CONTRACT_MULTIPLIER * spot * iv

def volga_exposure(volga, vega, oi):
    return volga * oi * vega

def charm_exposure(charm, spot, oi):
    return charm * oi * CONTRACT_MULTIPLIER * spot
