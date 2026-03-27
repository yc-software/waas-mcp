# mcp-yc-waas

MCP server for the YC Work at a Startup (WAAS) API. Lets Claude Code list applicants, view candidate profiles, send messages, update pipeline state, and manage notes — all from the command line.

## Setup (Production)

### Step 1: Create an OAuth Application

Go to [account.ycombinator.com/oauth/applications/new](https://account.ycombinator.com/oauth/applications/new) and fill in:

| Field | Value |
|-------|-------|
| **Name** | Whatever you want (e.g. `My Recruiting Bot`) |
| **Redirect URI** | `http://localhost:19877/callback` |
| **Confidential** | **Unchecked** (important — non-confidential clients work with the token exchange; confidential ones don't due to secret hashing) |
| **Scopes** | `candidates:read candidates:manage` |
| **Grant flows** | `Authorization code` |

Submit. Copy the **UID** from the confirmation page.

### Step 2: Install & Register

```bash
# Register with Claude Code — just the client ID
claude mcp add waas \
  -e WAAS_CLIENT_ID=your_client_id \
  -- uvx --from /path/to/mcp-yc-waas waas
```

### Step 3: Authenticate

Restart Claude Code. On first launch, the MCP server will:

1. Open your browser to the YC authorization page
2. You click **Authorize**
3. Tokens are saved to `~/.yc/waas-credentials.json` (auto-refreshed on expiry)

That's it. No manual token copying.

### Step 5: Verify

After restart, run `health_check` in Claude Code. You should see:

```
WAAS_API: ok (api.ycombinator.com)
```

## Configuration

| Env var | Required | Default | Description |
|---------|----------|---------|-------------|
| `WAAS_CLIENT_ID` | Yes | — | OAuth2 client ID (from your OAuth app's UID) |
| `WAAS_ACCESS_TOKEN` | No | — | OAuth2 access token (overrides stored credentials) |
| `WAAS_REFRESH_TOKEN` | No | — | OAuth2 refresh token (overrides stored credentials) |
| `WAAS_CLIENT_SECRET` | No | — | OAuth2 client secret (only for confidential apps) |
| `WAAS_API_HOST` | No | `https://api.ycombinator.com` | API host |
| `WAAS_API_HOST_HEADER` | No | — | Custom Host header (for local dev routing) |
| `WAAS_TOKEN_HOST` | No | derived from API host | Token endpoint host (for refresh) |

Credentials are stored in `~/.yc/waas-credentials.json` and auto-refreshed. Env vars take priority over stored credentials.

### Switching environments

**Production** (default — no host env vars needed):
```bash
WAAS_ACCESS_TOKEN=...
WAAS_REFRESH_TOKEN=...
WAAS_CLIENT_ID=...
# WAAS_API_HOST defaults to https://api.ycombinator.com
```

**Local dev** (requires host overrides):
```bash
WAAS_API_HOST=http://bookface.yclocal.com
WAAS_API_HOST_HEADER=public-api.yclocal.com:3002
WAAS_TOKEN_HOST=http://account.yclocal.com
```

**How to tell which environment you're on:** Run `health_check` — it shows the host: `WAAS_API: ok (api.ycombinator.com)` vs `WAAS_API: ok (bookface.yclocal.com)`.

### Where config lives

`claude mcp add` stores config in `~/.claude.json` under `projects.<working-dir>.mcpServers.waas`. If you previously registered the MCP for a different environment (e.g. local dev), `claude mcp add` may create a duplicate entry at a different scope instead of overriding the project-scoped one. **Always check `~/.claude.json` directly** if the MCP seems to be hitting the wrong environment.

## Tools

### Applicants (company-scoped)

| Tool | Description |
|------|-------------|
| `applicant_list` | List candidates who applied to your jobs. Filter by state, needs_response, job_id, since. Supports `compact=true` for triage (see below). |

#### Compact mode

`applicant_list(compact: true)` returns ~60% smaller payloads optimized for first-pass scanning. Use this for triage, pipeline views, and applicant review. Use full mode (no compact) only when you need email addresses, full work history, or complete looking_for text.

What compact trims:
- Positions: top 2 only (full mode returns up to 12)
- Educations: top 1 only (full mode returns up to 6)
- `looking_for`: truncated to 200 chars (full mode can be 1.2KB+)
- Dropped fields: `email`, `remote`, `github_url`, `last_active_at`, `role_type`, `applicant_messaged_at`, `last_messaged_at`
- Kept: `short_id`, `name`, `location`, `role`, `experience`, `us_authorized`, `us_visa_sponsorship`, `short_phrase`, `linkedin_url`, `profile_url`, `positions` (top 2), `educations` (top 1), `state`, `applied_at`, `applied_jobs`, `company_messaged_at`

The compact transformation is client-side only — the WAAS API returns the same data, and the MCP server trims it before passing to Claude.

### Candidates

| Tool | Description |
|------|-------------|
| `candidate_show` | Get a single candidate profile by short_id. Full profile with all positions, educations, work auth. |
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
| `candidate_message_send` | Send a message to a candidate via WAAS. Messages appear as emails to the candidate. |

### Notes

| Tool | Description |
|------|-------------|
| `candidate_notes_list` | List internal notes on a candidate. |
| `candidate_note_create` | Add an internal note. |

### Health

| Tool | Description |
|------|-------------|
| `health_check` | Validate the API connection. Returns ok/expired/error with the host. |

## Example Usage

Once registered, you can use natural language in Claude Code:

- "Show me applicants who need a response" → `applicant_list(needs_response: true, compact: true)`
- "Just PE applicants" → `applicant_list(job_id: 41302, compact: true)`
- "Who applied this week?" → `applicant_list(since: "2026-03-17T00:00:00Z", compact: true)`
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

### Local dev setup

For testing against local bookface (`http://bookface.yclocal.com`):

1. Create the OAuth app at `http://account.yclocal.com/oauth/applications/new` (same settings as production — non-confidential, `candidates:read candidates:manage`)
2. Authorize at `http://account.yclocal.com/oauth/authorize?client_id=CLIENT_ID&redirect_uri=urn:ietf:wg:oauth:2.0:oob&response_type=code&scope=candidates:read%20candidates:manage`
3. Exchange for token: `curl -X POST http://account.yclocal.com/oauth/token -d "grant_type=authorization_code" -d "code=AUTH_CODE" -d "client_id=CLIENT_ID" -d "redirect_uri=urn:ietf:wg:oauth:2.0:oob"`
4. Register with host overrides:
```bash
claude mcp add waas \
  -e WAAS_ACCESS_TOKEN=your_local_token \
  -e WAAS_REFRESH_TOKEN=your_local_refresh_token \
  -e WAAS_CLIENT_ID=your_local_client_id \
  -e WAAS_API_HOST=http://bookface.yclocal.com \
  -e WAAS_API_HOST_HEADER=public-api.yclocal.com:3002 \
  -e WAAS_TOKEN_HOST=http://account.yclocal.com \
  -- uvx --from /path/to/mcp-yc-waas waas
```

## Troubleshooting

**"Client authentication failed"** — Make sure the OAuth app is set to **non-confidential**. Confidential apps hash secrets, making the token exchange fail.

**Token expired** — Access tokens expire after 24 hours. If you have a refresh token and client ID configured, the server auto-refreshes. Otherwise, re-run steps 2-3.

**Wrong environment** — Run `health_check` to see which host you're hitting. Check `~/.claude.json` for duplicate MCP entries if it's pointing to the wrong environment.

**Local dev 404** — The API routes require `Host: public-api.yclocal.com:3002`. Set `WAAS_API_HOST_HEADER` in your env config.

**Rate limiting** — The WAAS API rate-limits write operations. When batch-archiving candidates, space out calls or retry on 429 responses.
