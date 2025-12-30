import http.server
import ssl
import socketserver
import threading
import time
import schwabdev
from config import APP_KEY, SECRET, CALLBACK_URL

_redirect_url = None

class OAuthHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        global _redirect_url
        if "code=" in self.path:
            _redirect_url = CALLBACK_URL + self.path
            self.send_response(200)
            self.end_headers()
            self.wfile.write(
                b"Authentication complete. You may close this window."
            )

def start_https_redirect_listener(certfile, keyfile):
    httpd = socketserver.TCPServer(("127.0.0.1", 8182), OAuthHandler)

    httpd.socket = ssl.wrap_socket(
        httpd.socket,
        certfile=certfile,
        keyfile=keyfile,
        server_side=True
    )

    threading.Thread(
        target=httpd.serve_forever,
        daemon=True
    ).start()

def wait_for_redirect(timeout=120):
    start = time.time()
    while time.time() - start < timeout:
        if _redirect_url:
            return _redirect_url
        time.sleep(0.2)
    raise TimeoutError("OAuth timed out")

def create_client():
    start_https_redirect_listener(
        certfile="cert.pem",
        keyfile="key.pem"
    )

    return schwabdev.Client(
        APP_KEY,
        SECRET,
        CALLBACK_URL,
        redirect_uri_response=wait_for_redirect
    )
