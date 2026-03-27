"""WAAS MCP configuration. Client ID is public (PKCE flow, no secret needed)."""

import os

PRODUCTION_CLIENT_ID = "qYeKhquxknIMH5RrSr7cVFNrsG3GHFagW_QBFjesDQU"
DEFAULT_API_HOST = "https://api.ycombinator.com"


def get_client_id() -> str:
    return os.getenv("WAAS_CLIENT_ID", PRODUCTION_CLIENT_ID)


def get_token_host() -> str:
    api_host = os.getenv("WAAS_API_HOST", DEFAULT_API_HOST)
    return os.getenv("WAAS_TOKEN_HOST", api_host.replace("api.", "account."))


def get_api_host() -> str:
    return os.getenv("WAAS_API_HOST", DEFAULT_API_HOST)


def get_host_header() -> str:
    return os.getenv("WAAS_API_HOST_HEADER", "")
