import schwabdev
from config import APP_KEY, SECRET, CALLBACK_URL

def create_client():
    return schwabdev.Client(
        APP_KEY,
        SECRET,
        CALLBACK_URL
    )

def get_auth_url(client):
    return client.get_authorization_url()

def complete_auth_from_redirect(client, redirect_url):
    if "code=" not in redirect_url:
        raise ValueError("Invalid redirect URL (missing code=)")

    client.get_token_from_redirect_url(redirect_url)
    return client
