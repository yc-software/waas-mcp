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

from .auth import (
    load_credentials,
    save_credentials,
    is_expired,
    refresh_access_token,
)
from .config import get_client_id, get_token_host, get_api_host, get_host_header


class WaasClient:
    """Handles WAAS API operations using OAuth2 Bearer tokens."""

    def __init__(self):
        self.api_host: str = ""
        self.access_token: str = ""
        self.refresh_token: str = ""
        self.client_id: str = ""
        self.client_secret: str = ""
        self.token_host: str = ""
        self.host_header: str = ""
        self.authenticated: bool = False

    def connect(self) -> bool:
        try:
            self.api_host = get_api_host()
            self.host_header = get_host_header()
            self.client_id = get_client_id()
            self.client_secret = os.getenv("WAAS_CLIENT_SECRET", "")
            self.token_host = get_token_host()

            # Priority: env vars > stored credentials
            env_token = os.getenv("WAAS_ACCESS_TOKEN", "")
            env_refresh = os.getenv("WAAS_REFRESH_TOKEN", "")

            if env_token:
                self.access_token = env_token
                self.refresh_token = env_refresh
                self.authenticated = True
                return True

            stored = load_credentials()
            if stored:
                self.access_token = stored.get("access_token", "")
                self.refresh_token = stored.get("refresh_token", "")
                self.client_id = self.client_id or stored.get("client_id", "")

                if is_expired(stored):
                    print("Stored token expired, refreshing...", flush=True)
                    if self._try_refresh():
                        self.authenticated = True
                        return True
                    print("Refresh failed. Run 'waas login' to re-authenticate.", flush=True)
                    return False
                else:
                    self.authenticated = True
                    return True

            print("Not authenticated. Run 'waas login' to get started.", flush=True)
            return False
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
            data = refresh_access_token(
                self.token_host, self.client_id, self.refresh_token, self.client_secret
            )
            self.access_token = data["access_token"]
            if data.get("refresh_token"):
                self.refresh_token = data["refresh_token"]
            # Persist refreshed tokens
            data["client_id"] = self.client_id
            save_credentials(data)
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
        if resp.status_code == 204 or not resp.content:
            return {"status": "ok"}
        return resp.json()

    def post_multipart(self, endpoint: str, fields: dict, files: Optional[dict] = None) -> dict:
        url = f"{self.api_host}{endpoint}"
        headers = {"Authorization": f"Bearer {self.access_token}"}
        if self.host_header:
            headers["Host"] = self.host_header
        resp = requests.post(url, headers=headers, data=fields, files=files or {})
        if resp.status_code == 401 and self._try_refresh():
            headers["Authorization"] = f"Bearer {self.access_token}"
            resp = requests.post(url, headers=headers, data=fields, files=files or {})
        resp.raise_for_status()
        return resp.json()

    def put(self, endpoint: str, data: Optional[dict] = None) -> dict:
        url = f"{self.api_host}{endpoint}"
        resp = requests.put(url, headers=self._headers(), json=data or {})
        if resp.status_code == 401 and self._try_refresh():
            resp = requests.put(url, headers=self._headers(), json=data or {})
        resp.raise_for_status()
        if resp.status_code == 204 or not resp.content:
            return {"status": "ok"}
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

    # ── Pipeline ──────────────────────────────────────────────────────
    types.Tool(
        name="job_list",
        description=(
            "List your company's jobs on WAAS with their pipeline stages. "
            "Returns job id, title, state, and the ordered pipeline stages for each job."
        ),
        inputSchema={
            "type": "object",
            "properties": {},
        },
    ),
    types.Tool(
        name="pipeline_show",
        description=(
            "Show the full pipeline board for a job — all stages with their candidates. "
            "Each stage lists candidates with short_id, name, entered_at, state, and needs_response flag."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "job_id": {"type": "integer", "description": "Job ID (from job_list)"},
            },
            "required": ["job_id"],
        },
    ),
    types.Tool(
        name="pipeline_move",
        description=(
            "Move one or more candidates to a pipeline stage for a job. "
            "This is a WRITE operation. Use job_list to discover valid stage names."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "job_id": {"type": "integer", "description": "Job ID (from job_list)"},
                "short_ids": {"type": "array", "items": {"type": "string"}, "description": "Candidate short_ids to move."},
                "stage_name": {"type": "string", "description": "Target pipeline stage name (e.g. 'Screen', 'Interview'). Use job_list to see valid stage names."},
            },
            "required": ["job_id", "short_ids", "stage_name"],
        },
    ),

    # ── Candidate Upload ──────────────────────────────────────────────
    types.Tool(
        name="candidate_create",
        description=(
            "Add a new candidate to a job's pipeline with an optional resume. "
            "The candidate will only be visible to your company. "
            "This is a WRITE operation."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "first_name": {"type": "string", "description": "Candidate's first name."},
                "last_name": {"type": "string", "description": "Candidate's last name."},
                "email": {"type": "string", "description": "Candidate's email address."},
                "job_id": {"type": "integer", "description": "Job ID to add the candidate to (from job_list)."},
                "linkedin": {"type": "string", "description": "LinkedIn profile URL (optional)."},
                "stage_name": {"type": "string", "description": "Pipeline stage name (optional, defaults to first stage). Use job_list to see valid stage names."},
                "resume_path": {"type": "string", "description": "Local file path to a resume (PDF/DOC/DOCX) to upload (optional)."},
            },
            "required": ["first_name", "last_name", "email", "job_id"],
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
    "job_list":                 ("GET",  "/v1/jobs"),
    "pipeline_show":            ("GET",  "/v1/jobs/{job_id}/pipeline"),
    "pipeline_move":            ("POST", "/v1/jobs/{job_id}/pipeline/move"),
}

WRITE_TOOLS = {
    "candidate_status_update", "candidate_message_send", "candidate_note_create",
    "pipeline_move", "candidate_create",
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
    NOT_AUTHENTICATED_MSG = "Not authenticated. Run 'waas login' in your terminal to get started."

    # Health check
    if name == "health_check":
        if not waas.authenticated:
            return [types.TextContent(type="text", text=f"WAAS_API: {NOT_AUTHENTICATED_MSG}")]
        try:
            waas.get("/v1/applicants", params={"limit": "1"})
            host = waas.api_host.replace("https://", "").replace("http://", "")
            return [types.TextContent(type="text", text=f"WAAS_API: ok ({host})")]
        except requests.exceptions.HTTPError as e:
            host = waas.api_host.replace("https://", "").replace("http://", "")
            if e.response is not None and e.response.status_code == 401:
                return [types.TextContent(type="text", text=f"WAAS_API: expired — run 'waas login' to re-authenticate ({host})")]
            return [types.TextContent(type="text", text=f"WAAS_API: error ({e}) ({host})")]
        except Exception as e:
            return [types.TextContent(type="text", text=f"WAAS_API: error ({e})")]

    if not waas.authenticated:
        return [types.TextContent(type="text", text=NOT_AUTHENTICATED_MSG)]

    # candidate_create — custom handler for multipart file upload
    if name == "candidate_create":
        try:
            args = dict(arguments) if arguments else {}
            fields = {
                "first_name": args["first_name"],
                "last_name": args["last_name"],
                "email": args["email"],
                "job_id": str(args["job_id"]),
            }
            if args.get("linkedin"):
                fields["linkedin"] = args["linkedin"]
            if args.get("stage_name"):
                fields["stage_name"] = args["stage_name"]

            files = None
            resume_path = args.get("resume_path")
            if resume_path:
                import mimetypes
                from pathlib import Path
                path = Path(resume_path).expanduser()
                if not path.exists():
                    return [types.TextContent(type="text", text=f"Resume file not found: {resume_path}")]
                content_type = mimetypes.guess_type(str(path))[0] or "application/pdf"
                files = {"resume": (path.name, open(path, "rb"), content_type)}

            response = waas.post_multipart("/v1/prospects", fields=fields, files=files)
            result = json.dumps(response, indent=2)
            result += "\n\n⚠️ This was a WRITE operation — candidate has been created."
            return [types.TextContent(type="text", text=result)]
        except requests.exceptions.HTTPError as e:
            error_body = ""
            if e.response is not None:
                try:
                    error_body = e.response.text
                except Exception:
                    pass
            return [types.TextContent(type="text", text=f"WAAS API error: {e}\n{error_body}")]
        except Exception as e:
            return [types.TextContent(type="text", text=f"Error creating candidate: {e}")]

    route = TOOL_ROUTES.get(name)
    if not route:
        return [types.TextContent(type="text", text=f"Unknown tool: {name}")]

    method, endpoint_template = route

    try:
        # Extract path params (short_id, job_id)
        args = dict(arguments) if arguments else {}
        short_id = args.pop("short_id", None)
        job_id = args.pop("job_id", None)
        format_kwargs = {}
        if short_id:
            format_kwargs["short_id"] = short_id
        if job_id:
            format_kwargs["job_id"] = job_id
        endpoint = endpoint_template.format(**format_kwargs) if format_kwargs else endpoint_template

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
