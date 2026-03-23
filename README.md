# mcp-yc-waas

MCP server for the YC Work at a Startup (WAAS) API. Lets Claude Code list applicants, view candidate profiles, send messages, update pipeline state, and manage notes — all from the command line.

## Install

```bash
# Install the MCP server
uv tool install --from /path/to/mcp-yc-waas mcp-yc-waas

# Register with Claude Code
claude mcp add waas \
  -e WAAS_ACCESS_TOKEN=your_access_token \
  -e WAAS_REFRESH_TOKEN=your_refresh_token \
  -e WAAS_CLIENT_ID=your_client_id \
  -e WAAS_CLIENT_SECRET=your_client_secret \
  -- uvx --from /path/to/mcp-yc-waas waas
```

**Getting your OAuth token:**
1. Create an OAuth application at `account.ycombinator.com/oauth/applications` with scopes `candidates:read candidates:manage` and grant flow `authorization_code`
2. Authorize at: `https://account.ycombinator.com/oauth/authorize?client_id=CLIENT_ID&redirect_uri=urn:ietf:wg:oauth:2.0:oob&response_type=code&scope=candidates:read%20candidates:manage`
3. Exchange the code for tokens:
   ```bash
   curl -X POST https://account.ycombinator.com/oauth/token \
     -d "grant_type=authorization_code&code=AUTH_CODE&client_id=CLIENT_ID&client_secret=CLIENT_SECRET&redirect_uri=urn:ietf:wg:oauth:2.0:oob"
   ```
4. Use `access_token` and `refresh_token` from the response

The server auto-refreshes expired access tokens using the refresh token.

## Configuration

| Env var | Required | Default | Description |
|---------|----------|---------|-------------|
| `WAAS_ACCESS_TOKEN` | Yes | — | OAuth2 access token |
| `WAAS_REFRESH_TOKEN` | No | — | OAuth2 refresh token (for auto-refresh) |
| `WAAS_CLIENT_ID` | No | — | OAuth2 client ID (needed for refresh) |
| `WAAS_CLIENT_SECRET` | No | — | OAuth2 client secret (needed for refresh) |
| `WAAS_API_HOST` | No | `https://api.ycombinator.com` | API host (for local dev) |
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
