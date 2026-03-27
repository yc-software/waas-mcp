import sys


def main():
    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "login":
            from .auth import perform_auth_flow, load_credentials, is_expired
            from .config import get_client_id, get_token_host

            client_id = get_client_id()
            token_host = get_token_host()

            existing = load_credentials()
            if existing and not is_expired(existing):
                print("Already authenticated. Use 'waas logout' to clear credentials.")
                return

            tokens = perform_auth_flow(token_host, client_id)
            tokens["client_id"] = client_id
            from .auth import save_credentials
            save_credentials(tokens)
            return

        if command == "logout":
            from .auth import clear_credentials, load_credentials
            if load_credentials():
                clear_credentials()
                print("Credentials cleared.")
            else:
                print("No stored credentials found.")
            return

        if command == "status":
            from .auth import load_credentials, is_expired
            creds = load_credentials()
            if not creds:
                print("Not authenticated. Run 'waas login' to get started.")
                return
            if is_expired(creds):
                print("Token expired. Run 'waas login' to re-authenticate.")
            else:
                import time
                expires_at = (creds["created_at"] + creds["expires_in"])
                remaining = expires_at - time.time()
                hours = int(remaining // 3600)
                minutes = int((remaining % 3600) // 60)
                print(f"Authenticated. Token expires in {hours}h {minutes}m.")
            return

        print(f"Unknown command: {command}")
        print("Usage: waas [login|logout|status]")
        sys.exit(1)

    import asyncio
    from .server import run
    asyncio.run(run())
