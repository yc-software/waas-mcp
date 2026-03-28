"""Browser-based OAuth2 PKCE auth flow and persistent token storage for WAAS MCP."""

import hashlib
import http.server
import json
import os
import secrets
import stat
import threading
import webbrowser
from pathlib import Path
from typing import Optional


CREDENTIALS_DIR = ".yc"
CREDENTIALS_FILE = "waas-credentials.json"
CALLBACK_PORT = 19877
OAUTH_SCOPES = [
    "waas:candidates:read",
    "waas:candidates:manage",
    "waas:applications:read",
    "waas:applications:manage",
    "waas:messages:read",
    "waas:messages:manage",
    "waas:stages:read",
    "waas:stages:manage",
    "waas:notes:read",
    "waas:notes:manage",
]


def _credentials_path() -> Path:
    return Path.home() / CREDENTIALS_DIR / CREDENTIALS_FILE


def save_credentials(creds: dict) -> None:
    path = _credentials_path()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_text(json.dumps(creds, indent=2))
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def load_credentials() -> Optional[dict]:
    path = _credentials_path()
    if not path.exists():
        return None
    return json.loads(path.read_text())


def clear_credentials() -> None:
    path = _credentials_path()
    if path.exists():
        path.unlink()


def is_expired(creds: dict) -> bool:
    expires_at = (creds["created_at"] + creds["expires_in"]) * 1000
    # Refresh 5 minutes before expiry
    return _now_ms() > expires_at - 5 * 60 * 1000


def _now_ms() -> int:
    import time
    return int(time.time() * 1000)


def _generate_code_verifier() -> str:
    return secrets.token_urlsafe(32)


def _generate_code_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    import base64
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def _wait_for_auth_code(port: int) -> str:
    """Start a local HTTP server and wait for the OAuth callback."""
    result: dict = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(self.path)

            if parsed.path != "/callback":
                self.send_response(404)
                self.end_headers()
                return

            params = parse_qs(parsed.query)

            if "error" in params:
                desc = params.get("error_description", params["error"])[0]
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(f"<html><body><h1>Authorization failed</h1><p>{desc}</p></body></html>".encode())
                result["error"] = desc
                return

            code = params.get("code", [None])[0]
            if not code:
                self.send_response(400)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(b"<html><body><h1>Missing authorization code</h1></body></html>")
                result["error"] = "No authorization code received"
                return

            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<html><body><h1>Logged in!</h1><p>You can close this tab.</p></body></html>")
            result["code"] = code

        def log_message(self, format, *args):
            pass  # Suppress request logs

    server = http.server.HTTPServer(("127.0.0.1", port), Handler)
    server.handle_request()
    server.server_close()

    if "error" in result:
        raise RuntimeError(f"Authorization denied: {result['error']}")
    if "code" not in result:
        raise RuntimeError("No authorization code received")
    return result["code"]


def exchange_code_for_tokens(token_host: str, client_id: str, code: str, code_verifier: str, redirect_uri: str) -> dict:
    import requests
    resp = requests.post(
        f"{token_host}/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": client_id,
            "code_verifier": code_verifier,
        },
    )
    resp.raise_for_status()
    return resp.json()


def refresh_access_token(token_host: str, client_id: str, refresh_token: str, client_secret: str = "") -> dict:
    import requests
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
    }
    if client_secret:
        data["client_secret"] = client_secret
    resp = requests.post(f"{token_host}/oauth/token", data=data)
    resp.raise_for_status()
    return resp.json()


def perform_auth_flow(token_host: str, client_id: str) -> dict:
    """Run the full browser-based PKCE OAuth flow. Returns token response dict."""
    code_verifier = _generate_code_verifier()
    code_challenge = _generate_code_challenge(code_verifier)

    redirect_uri = f"http://localhost:{CALLBACK_PORT}/callback"
    auth_url = (
        f"{token_host}/oauth/authorize"
        f"?client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&response_type=code"
        f"&scope={'+'.join(OAUTH_SCOPES)}"
        f"&code_challenge={code_challenge}"
        f"&code_challenge_method=S256"
    )

    # Start the callback server in a thread so we can open the browser
    code_result: dict = {}
    error_result: dict = {}

    def listen():
        try:
            code_result["code"] = _wait_for_auth_code(CALLBACK_PORT)
        except Exception as e:
            error_result["error"] = str(e)

    listener = threading.Thread(target=listen, daemon=True)
    listener.start()

    print(f"Opening browser for authentication...", flush=True)
    print(f"If the browser doesn't open, visit: {auth_url}", flush=True)
    webbrowser.open(auth_url)

    listener.join(timeout=120)

    if error_result:
        raise RuntimeError(error_result["error"])
    if "code" not in code_result:
        raise RuntimeError("Authentication timed out")

    print("Exchanging authorization code for tokens...", flush=True)
    tokens = exchange_code_for_tokens(token_host, client_id, code_result["code"], code_verifier, redirect_uri)
    save_credentials(tokens)
    print("Authenticated successfully. Credentials saved.", flush=True)
    return tokens
