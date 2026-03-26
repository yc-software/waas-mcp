import asyncio
import json
import os
from typing import Any, Optional
from dotenv import load_dotenv
import requests

import mcp.types as types
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
import mcp.server.stdio


class WaasClient:
    """Handles WAAS API operations using OAuth2 Bearer tokens."""

    def __init__(self):
        self.api_host: str = ""
        self.access_token: str = ""
        self.refresh_token: str = ""
        self.client_id: str = ""
        self.client_secret: str = ""
        self.token_host: str = ""

    def connect(self) -> bool:
        try:
            self.api_host = os.getenv("WAAS_API_HOST", "https://api.ycombinator.com")
            self.host_header = os.getenv("WAAS_API_HOST_HEADER", "")
            self.access_token = os.getenv("WAAS_ACCESS_TOKEN", "")
            self.refresh_token = os.getenv("WAAS_REFRESH_TOKEN", "")
            self.client_id = os.getenv("WAAS_CLIENT_ID", "")
            self.client_secret = os.getenv("WAAS_CLIENT_SECRET", "")
            self.token_host = os.getenv("WAAS_TOKEN_HOST", self.api_host.replace("api.", "account."))

            if not self.access_token:
                raise ValueError("WAAS_ACCESS_TOKEN environment variable not set")
            return True
        except Exception as e:
            print(f"WAAS connection failed: {str(e)}", flush=True)
            return False

    def _headers(self) -> dict:
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        if self.host_header:
            headers["Host"] = self.host_header
        return headers

    def _try_refresh(self) -> bool:
        if not self.refresh_token or not self.client_id:
            return False
        try:
            resp = requests.post(
                f"{self.token_host}/oauth/token",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self.refresh_token,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            self.access_token = data["access_token"]
            if data.get("refresh_token"):
                self.refresh_token = data["refresh_token"]
            return True
        except Exception:
            return False

    def get(self, endpoint: str, params: Optional[dict] = None) -> dict:
        url = f"{self.api_host}{endpoint}"
        resp = requests.get(url, headers=self._headers(), params=params)
        if resp.status_code == 401 and self._try_refresh():
            resp = requests.get(url, headers=self._headers(), params=params)
        resp.raise_for_status()
        return resp.json()

    def post(self, endpoint: str, data: Optional[dict] = None) -> dict:
        url = f"{self.api_host}{endpoint}"
        resp = requests.post(url, headers=self._headers(), json=data or {})
        if resp.status_code == 401 and self._try_refresh():
            resp = requests.post(url, headers=self._headers(), json=data or {})
        resp.raise_for_status()
        return resp.json()

    def put(self, endpoint: str, data: Optional[dict] = None) -> dict:
        url = f"{self.api_host}{endpoint}"
        resp = requests.put(url, headers=self._headers(), json=data or {})
        if resp.status_code == 401 and self._try_refresh():
            resp = requests.put(url, headers=self._headers(), json=data or {})
        resp.raise_for_status()
        return resp.json()


# ---------------------------------------------------------------------------
# Server setup
# ---------------------------------------------------------------------------
server = Server("waas-mcp")
load_dotenv()

waas = WaasClient()
if not waas.connect():
    print("Failed to initialize WAAS connection", flush=True)


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------
TOOLS = [
    # ── Applicants (company-scoped) ────────────────────────────────────
    types.Tool(
        name="applicant_list",
        description=(
            "List candidates who applied to your company's jobs on WAAS. "
            "Returns name, email, role, experience, location, work auth, positions, "
            "educations, applied_jobs, state, messaging timestamps. "
            "Ordered by applied_at descending (newest first). "
            "Use compact=true for triage — returns ~60% smaller payloads by trimming "
            "positions to top 2, educations to top 1, truncating looking_for, and "
            "dropping fields not needed for first-pass scanning."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "state": {
                    "type": "string",
                    "enum": ["reviewing", "shortlisted", "screen", "interviewing", "offer", "archived"],
                    "description": "Filter by pipeline state. Default: excludes archived/spam.",
                },
                "needs_response": {
                    "type": "boolean",
                    "description": "Only applicants the company hasn't messaged (company_messaged_at is null).",
                },
                "job_id": {
                    "type": "integer",
                    "description": "Filter to applicants for a specific job. Discover job IDs from the applied_jobs array in results.",
                },
                "since": {
                    "type": "string",
                    "description": "ISO 8601 timestamp — only applicants who applied after this date.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results (default 50, max 500).",
                },
                "offset": {
                    "type": "integer",
                    "description": "Offset for pagination (default 0).",
                },
                "compact": {
                    "type": "boolean",
                    "description": "Return slim payloads for triage. Trims positions to top 2, educations to top 1, truncates looking_for to 200 chars, drops email/remote/github_url/last_active_at/role_type. ~60% smaller.",
                },
            },
        },
    ),

    # ── Candidates (any active profile) ────────────────────────────────
    types.Tool(
        name="candidate_show",
        description="Get a single WAAS candidate profile by short_id. Returns full profile with positions, educations, work auth.",
        inputSchema={
            "type": "object",
            "properties": {
                "short_id": {"type": "string", "description": "Candidate short_id (from profile URL or applicant_list)."},
            },
            "required": ["short_id"],
        },
    ),
    types.Tool(
        name="candidate_batch",
        description="Look up multiple WAAS candidates by short_ids in one call (max 25).",
        inputSchema={
            "type": "object",
            "properties": {
                "short_ids": {"type": "string", "description": "Comma-separated short_ids (max 25)."},
            },
            "required": ["short_ids"],
        },
    ),

    # ── Candidate Status ───────────────────────────────────────────────
    types.Tool(
        name="candidate_status_show",
        description="Get pipeline status for a candidate — state, pipeline_stage, archive_reason, messaging timestamps.",
        inputSchema={
            "type": "object",
            "properties": {
                "short_id": {"type": "string", "description": "Candidate short_id."},
            },
            "required": ["short_id"],
        },
    ),
    types.Tool(
        name="candidate_status_update",
        description=(
            "Update a candidate's pipeline state. This is a WRITE operation. "
            "Valid states: reviewing, shortlisted, screen, interviewing, offer, archived. "
            "When archiving, provide archive_reason."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "short_id": {"type": "string", "description": "Candidate short_id."},
                "state": {
                    "type": "string",
                    "enum": ["reviewing", "shortlisted", "screen", "interviewing", "offer", "archived"],
                    "description": "New state.",
                },
                "archive_reason": {
                    "type": "string",
                    "enum": ["not_qualified", "team_fit", "might_consider_later", "turned_down_offer", "hired", "other"],
                    "description": "Required when state is 'archived'.",
                },
                "archive_comment": {"type": "string", "description": "Optional comment when archiving."},
                "pipeline_stage": {"type": "string", "description": "Pipeline stage name to move to."},
            },
            "required": ["short_id"],
        },
    ),

    # ── Messages ───────────────────────────────────────────────────────
    types.Tool(
        name="candidate_messages_list",
        description="List all messages between the company and a candidate.",
        inputSchema={
            "type": "object",
            "properties": {
                "short_id": {"type": "string", "description": "Candidate short_id."},
            },
            "required": ["short_id"],
        },
    ),
    types.Tool(
        name="candidate_message_send",
        description="Send a message to a candidate via WAAS. This is a WRITE operation.",
        inputSchema={
            "type": "object",
            "properties": {
                "short_id": {"type": "string", "description": "Candidate short_id."},
                "message": {"type": "string", "description": "Message text to send."},
            },
            "required": ["short_id", "message"],
        },
    ),

    # ── Notes ──────────────────────────────────────────────────────────
    types.Tool(
        name="candidate_notes_list",
        description="List all internal notes on a candidate.",
        inputSchema={
            "type": "object",
            "properties": {
                "short_id": {"type": "string", "description": "Candidate short_id."},
            },
            "required": ["short_id"],
        },
    ),
    types.Tool(
        name="candidate_note_create",
        description="Add an internal note to a candidate. This is a WRITE operation.",
        inputSchema={
            "type": "object",
            "properties": {
                "short_id": {"type": "string", "description": "Candidate short_id."},
                "note": {"type": "string", "description": "Note text."},
            },
            "required": ["short_id", "note"],
        },
    ),

    # ── Health Check ───────────────────────────────────────────────────
    types.Tool(
        name="health_check",
        description="Check if the WAAS API connection is healthy. Returns ok/expired/error.",
        inputSchema={
            "type": "object",
            "properties": {},
        },
    ),
]

# Route tool calls to endpoints
TOOL_ROUTES = {
    "applicant_list":           ("GET",  "/v1/applicants"),
    "candidate_show":           ("GET",  "/v1/candidates/{short_id}"),
    "candidate_batch":          ("GET",  "/v1/candidates"),
    "candidate_status_show":    ("GET",  "/v1/candidates/{short_id}/status"),
    "candidate_status_update":  ("PUT",  "/v1/candidates/{short_id}/status"),
    "candidate_messages_list":  ("GET",  "/v1/candidates/{short_id}/messages"),
    "candidate_message_send":   ("POST", "/v1/candidates/{short_id}/messages"),
    "candidate_notes_list":     ("GET",  "/v1/candidates/{short_id}/notes"),
    "candidate_note_create":    ("POST", "/v1/candidates/{short_id}/notes"),
}

WRITE_TOOLS = {
    "candidate_status_update", "candidate_message_send", "candidate_note_create",
}


def _compact_applicant(item: dict) -> dict:
    """Trim an applicant item to triage-relevant fields only."""
    c = item.get("candidate", {})
    positions = c.get("positions", [])
    educations = c.get("educations", [])
    looking_for = c.get("looking_for") or ""
    if len(looking_for) > 200:
        looking_for = looking_for[:200] + "..."

    return {
        "candidate": {
            "short_id": c.get("short_id"),
            "name": c.get("name"),
            "location": c.get("location"),
            "role": c.get("role"),
            "experience": c.get("experience"),
            "us_authorized": c.get("us_authorized"),
            "us_visa_sponsorship": c.get("us_visa_sponsorship"),
            "short_phrase": c.get("short_phrase"),
            "looking_for": looking_for,
            "linkedin_url": c.get("linkedin_url"),
            "profile_url": c.get("profile_url"),
            "positions": [
                {"title": p.get("title"), "company": p.get("company"), "current": p.get("is_current", False)}
                for p in positions[:2]
            ],
            "educations": [
                {"school": e.get("school"), "degree": e.get("degree"), "field": e.get("field_of_study")}
                for e in educations[:1]
            ],
        },
        "state": item.get("state"),
        "applied_at": item.get("applied_at"),
        "applied_jobs": item.get("applied_jobs"),
        "company_messaged_at": item.get("company_messaged_at"),
    }


def _compact_response(response: dict) -> dict:
    """Apply compact transformation to an applicant_list response."""
    items = response.get("items", [])
    return {
        "items": [_compact_applicant(item) for item in items],
        "next_cursor": response.get("next_cursor"),
    }


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return TOOLS


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
    # Health check
    if name == "health_check":
        try:
            waas.get("/v1/applicants", params={"limit": "1"})
            host = waas.api_host.replace("https://", "").replace("http://", "")
            return [types.TextContent(type="text", text=f"WAAS_API: ok ({host})")]
        except requests.exceptions.HTTPError as e:
            host = waas.api_host.replace("https://", "").replace("http://", "")
            if e.response is not None and e.response.status_code == 401:
                return [types.TextContent(type="text", text=f"WAAS_API: expired — re-authorize ({host})")]
            return [types.TextContent(type="text", text=f"WAAS_API: error ({e}) ({host})")]
        except Exception as e:
            return [types.TextContent(type="text", text=f"WAAS_API: error ({e})")]

    route = TOOL_ROUTES.get(name)
    if not route:
        return [types.TextContent(type="text", text=f"Unknown tool: {name}")]

    method, endpoint_template = route

    try:
        # Extract path params (short_id)
        args = dict(arguments) if arguments else {}
        short_id = args.pop("short_id", None)
        endpoint = endpoint_template.format(short_id=short_id) if short_id else endpoint_template

        # Extract client-side params before sending to API
        compact = args.pop("compact", False)

        # For batch lookup, short_ids goes as query param
        if name == "candidate_batch":
            short_ids = args.pop("short_ids", "")
            args["short_ids"] = short_ids

        if method == "GET":
            response = waas.get(endpoint, params=args if args else None)
        elif method == "POST":
            response = waas.post(endpoint, data=args if args else None)
        elif method == "PUT":
            response = waas.put(endpoint, data=args if args else None)
        else:
            return [types.TextContent(type="text", text=f"Unsupported method: {method}")]

        # Apply compact transformation for applicant_list
        if compact and name == "applicant_list":
            response = _compact_response(response)

        result = json.dumps(response, indent=2)

        if name in WRITE_TOOLS:
            result += "\n\n⚠️ This was a WRITE operation — data has been modified."

        return [types.TextContent(type="text", text=result)]

    except requests.exceptions.HTTPError as e:
        error_body = ""
        if e.response is not None:
            try:
                error_body = e.response.text
            except Exception:
                pass
        return [types.TextContent(type="text", text=f"WAAS API error on {endpoint}: {e}\n{error_body}")]
    except Exception as e:
        return [types.TextContent(type="text", text=f"Error calling {endpoint}: {e}")]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
async def run():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="waas",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(run())
