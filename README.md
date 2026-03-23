# mcp-yc-waas

MCP server for the YC Work at a Startup (WAAS) API. Lets Claude Code list applicants, view candidate profiles, send messages, update pipeline state, and manage notes — all from the command line.

## Setup

### Step 1: Create an OAuth Application

Go to [account.ycombinator.com/oauth/applications/new](https://account.ycombinator.com/oauth/applications/new) and fill in:

| Field | Value |
|-------|-------|
| **Name** | Whatever you want (e.g. `My Recruiting Bot`) |
| **Redirect URI** | `urn:ietf:wg:oauth:2.0:oob` |
| **Confidential** | **Unchecked** (important — non-confidential clients work with the token exchange; confidential ones don't due to secret hashing) |
| **Scopes** | `candidates:read candidates:manage` |
| **Grant flows** | `Authorization code` (check `Client credentials` too if you want) |

Submit. Copy the **UID** from the confirmation page.

### Step 2: Authorize

Open this URL in your browser (replace `CLIENT_ID` with your UID):

```
https://account.ycombinator.com/oauth/authorize?client_id=CLIENT_ID&redirect_uri=urn:ietf:wg:oauth:2.0:oob&response_type=code&scope=candidates:read%20candidates:manage
```

Click **Authorize**. Copy the authorization code shown on screen.

### Step 3: Exchange for Token

```bash
curl -X POST https://account.ycombinator.com/oauth/token \
  -d "grant_type=authorization_code" \
  -d "code=AUTH_CODE" \
  -d "client_id=CLIENT_ID" \
  -d "redirect_uri=urn:ietf:wg:oauth:2.0:oob"
```

No `client_secret` needed (non-confidential client). Returns:

```json
{
  "access_token": "...",
  "token_type": "Bearer",
  "expires_in": 86400,
  "refresh_token": "...",
  "scope": "candidates:read candidates:manage"
}
```

### Step 4: Install & Register

```bash
# Install the MCP server
uv tool install --from /path/to/mcp-yc-waas mcp-yc-waas

# Register with Claude Code
claude mcp add waas \
  -e WAAS_ACCESS_TOKEN=your_access_token \
  -e WAAS_REFRESH_TOKEN=your_refresh_token \
  -e WAAS_CLIENT_ID=your_client_id \
  -- uvx --from /path/to/mcp-yc-waas waas
```

Restart Claude Code. The MCP server auto-refreshes expired tokens using the refresh token.

### Local Development

For testing against local bookface (`http://bookface.yclocal.com`), the API routes require a specific Host header. Use the shell script helper instead:

```bash
# Create the OAuth app at http://account.yclocal.com/oauth/applications/new
# (same settings as above — non-confidential, candidates:read candidates:manage)

# Authorize
# http://account.yclocal.com/oauth/authorize?client_id=CLIENT_ID&redirect_uri=urn:ietf:wg:oauth:2.0:oob&response_type=code&scope=candidates:read%20candidates:manage

# Exchange
curl -X POST http://account.yclocal.com/oauth/token \
  -d "grant_type=authorization_code" \
  -d "code=AUTH_CODE" \
  -d "client_id=CLIENT_ID" \
  -d "redirect_uri=urn:ietf:wg:oauth:2.0:oob"

# Test
WAAS_API_HOST="http://bookface.yclocal.com" \
WAAS_API_HOST_HEADER="public-api.yclocal.com:3002" \
.claude/skills/waas-api/waas-api.sh /v1/applicants "needs_response=true&limit=3"
```

## Configuration

| Env var | Required | Default | Description |
|---------|----------|---------|-------------|
| `WAAS_ACCESS_TOKEN` | Yes | — | OAuth2 access token |
| `WAAS_REFRESH_TOKEN` | No | — | OAuth2 refresh token (for auto-refresh) |
| `WAAS_CLIENT_ID` | No | — | OAuth2 client ID (needed for refresh) |
| `WAAS_API_HOST` | No | `https://api.ycombinator.com` | API host |
| `WAAS_TOKEN_HOST` | No | derived from API host | Token endpoint host (for refresh) |

## Tools

### Applicants (company-scoped)

| Tool | Description |
|------|-------------|
| `applicant_list` | List candidates who applied to your jobs. Filter by state, needs_response, job_id, since. Ordered newest first. Returns full profiles with positions, educations, work auth. |

### Candidates

| Tool | Description |
|------|-------------|
| `candidate_show` | Get a single candidate profile by short_id. |
| `candidate_batch` | Batch lookup up to 25 candidates by comma-separated short_ids. |

### Pipeline Status

| Tool | Description |
|------|-------------|
| `candidate_status_show` | Get pipeline state — stage, archive reason, messaging timestamps. |
| `candidate_status_update` | Update state (reviewing, shortlisted, screen, interviewing, offer, archived). |

**States:** `reviewing` · `shortlisted` · `screen` · `interviewing` · `offer` · `archived`

**Archive reasons:** `not_qualified` · `team_fit` · `might_consider_later` · `turned_down_offer` · `hired` · `other`

### Messages

| Tool | Description |
|------|-------------|
| `candidate_messages_list` | List all messages between you and a candidate. |
| `candidate_message_send` | Send a message to a candidate via WAAS. |

### Notes

| Tool | Description |
|------|-------------|
| `candidate_notes_list` | List internal notes on a candidate. |
| `candidate_note_create` | Add an internal note. |

### Health

| Tool | Description |
|------|-------------|
| `health_check` | Validate the API connection. Returns ok, expired, or error. |

## Example Usage

Once registered, you can use natural language in Claude Code:

- "Show me applicants who need a response" → `applicant_list(needs_response: true)`
- "Just PE applicants" → `applicant_list(job_id: 41302)`
- "Who applied this week?" → `applicant_list(since: "2026-03-17T00:00:00Z")`
- "Tell me about this candidate" → `candidate_show(short_id: "KhNCmzEZ")`
- "Archive candidates 1-5" → loops `candidate_status_update(short_id, state: "archived", archive_reason: "not_qualified")`
- "Message this candidate" → `candidate_message_send(short_id: "KhNCmzEZ", message: "Hi! Thanks for applying...")`
- "Check if WAAS is connected" → `health_check()`

## Development

```bash
# Clone
git clone git@github.com:ryankicks/mcp-yc-waas.git
cd mcp-yc-waas

# Install locally
uv tool install --from . mcp-yc-waas

# After making changes, reinstall
uv tool install --force --from . mcp-yc-waas
# Then restart Claude Code
```

## Troubleshooting

**"Client authentication failed"** — Make sure the OAuth app is set to **non-confidential**. Confidential apps hash secrets, making the token exchange fail.

**Token expired** — Access tokens expire after 24 hours. If you have a refresh token and client ID configured, the server auto-refreshes. Otherwise, re-run steps 2-3.

**Local dev 404** — The API routes require `Host: public-api.yclocal.com:3002`. Use the `waas-api.sh` shell script with `WAAS_API_HOST_HEADER` for local testing.
