# waas-mcp

MCP server for the YC Work at a Startup (WAAS) API. Lets Claude Code list applicants, view candidate profiles, manage pipeline stages, upload candidates with resumes, send messages, and manage notes — all from the command line.

## Setup

### Step 1: Install & Register

```bash
claude mcp add waas -- uvx --from git+https://github.com/yc-software/waas-mcp waas
```

Or install locally with uv:

```bash
uv tool install git+https://github.com/yc-software/waas-mcp
claude mcp add waas -- waas
```

### Step 2: Authenticate

```bash
waas login
```

Your browser opens to the YC authorization page. Click **Authorize** and you're done. Tokens are saved to `~/.yc/waas-credentials.json` and auto-refresh on expiry.

### Step 3: Verify

Restart Claude Code, then run `health_check`. You should see:

```
WAAS_API: ok (api.ycombinator.com)
```

### CLI Commands

```bash
waas login    # Authenticate (opens browser)
waas logout   # Clear stored credentials
waas status   # Check token status
```

## Configuration

All env vars are optional — the default setup requires no configuration beyond `waas login`.

| Env var | Default | Description |
|---------|---------|-------------|
| `WAAS_CLIENT_ID` | built-in | Override the OAuth2 client ID |
| `WAAS_ACCESS_TOKEN` | — | OAuth2 access token (overrides stored credentials) |
| `WAAS_REFRESH_TOKEN` | — | OAuth2 refresh token (overrides stored credentials) |
| `WAAS_CLIENT_SECRET` | — | OAuth2 client secret (only for confidential apps) |
| `WAAS_API_HOST` | `https://api.ycombinator.com` | API host |
| `WAAS_API_HOST_HEADER` | — | Custom Host header (for local dev routing) |
| `WAAS_TOKEN_HOST` | derived from API host | Token endpoint host (for refresh) |

Credentials are stored in `~/.yc/waas-credentials.json` and auto-refreshed. Env vars take priority over stored credentials.

## Tools

### Applicants (company-scoped)

| Tool | Description |
|------|-------------|
| `applicant_list` | List candidates who applied to your jobs. Filter by state, needs_response, job_id, since. Paginate with `cursor` (see below). Supports `compact=true` for triage (see below). |

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

### Pipeline

| Tool | Description |
|------|-------------|
| `job_list` | List your company's jobs with their pipeline stages (id, title, state, stage names). |
| `pipeline_show` | Full pipeline board for a job — all stages with candidates (short_id, name, entered_at, state, needs_response). Includes an "Applied" virtual stage for candidates who applied but haven't been placed in a stage yet. |
| `pipeline_move` | Move one or more candidates to a pipeline stage. Works for all candidates. |

### Job postings (create / edit)

| Tool | Description |
|------|-------------|
| `job_show` | Full editable detail for one job posting by id (role, subtypes, comp, equity, skills, locations, …). Read before editing. |
| `job_create` | Create a job posting. Requires `waas:jobs:manage`. Defaults to `state: hidden` (draft); set `state: visible` to publish. |
| `job_update` | Edit a posting — partial update, send only the fields you want to change. Requires `waas:jobs:manage`. |

**Required to save a posting** (enforced by the API): `title`, `description`, `role`, the role's subtype, `job_type`, `remote`, `us_work_authorization_required`, seniority, and a location unless remote.

**Field vocabularies** — send the key; these enums are also encoded in the tool input schemas:

- **`role`**: `eng` · `design` · `product` · `science` · `sales` · `marketing` · `support` · `operations` · `recruiting` · `finance` · `legal`
- **Subtype (array, required ≥1) — only for these four roles**; the other seven take none:
  - `role: eng` → **`eng_type`**: android, be, data_sci, devops, embedded, eng_mgmt, fe, fs, ios, ml, qa, robotics, hw, electrical, mechanical, bio, chemical
  - `role: design` → **`design_type`**: web, mobile, product, ui_ux, user_research, brand_graphic, illustration, animation, hardware, ar_vr, design_mgmt
  - `role: science` → **`science_type`**: bio, biotech, chem, genetics, health, immuno, lab, onc, pharma, process, research
  - `role: recruiting` → **`recruiting_type`**: sourcer, recruiter, coordinator, lead, operations, fullcycle, manager
- **`job_type`**: `fulltime` · `cofounder` · `intern` · `contract`
- **Seniority**: `min_experience` (integer years) for non-interns, OR `min_school_year` (`any`/`freshman`/`sophomore`/`junior`/`senior`) for `job_type: intern`
- **`remote`**: `yes` remote ok · `no` in-person (**requires `locations`**) · `only` remote only
- **`us_work_authorization_required`**: boolean — `true` = must already be US-authorized (no sponsorship), `false` = sponsorship OK
- **`pay_period`**: `year` · `month` · `hour` — **`currency`**: `USD` · `CAD` · `INR` · `EUR` · `GBP`
- **`state`**: `hidden` draft · `visible` published — **`skills`**: free-text names, resolved per-role, unmatched dropped — **`equity_min`/`equity_max`**: percent 0–100 — **`time_to_hire`**: days

**Note:** `job_create`/`job_update` require the `waas:jobs:manage` scope. If you get a 403, run `waas login` to re-authenticate and pick up the scope.

### Adding Candidates

| Tool | Description |
|------|-------------|
| `candidate_create` | Add a new candidate to a job's pipeline with an optional resume (PDF/DOC/DOCX from a local file path). The candidate will only be visible to your company. Must specify a real pipeline stage (e.g. "In Review") — "Applied" is a virtual view, not a stage. |

**Note:** `candidate_create` requires the `waas:candidates:manage` scope. If you get a 403, re-authenticate with `waas login` or update your token to include this scope.

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
- "Show me the pipeline" → `job_list()` then `pipeline_show(job_id: 41302)`
- "Move Jane to Screen" → `pipeline_move(job_id: 41302, short_ids: ["abc123"], stage_name: "Screen")`
- "Add this person to In Review" → `candidate_create(first_name: "Jane", last_name: "Doe", email: "jane@example.com", job_id: 41302, resume_path: "/tmp/jane.pdf")`
- "Archive candidates 1-5" → loops `candidate_status_update(short_id, state: "archived", archive_reason: "not_qualified")`
- "Message this candidate" → `candidate_message_send(short_id: "KhNCmzEZ", message: "Hi! Thanks for applying...")`
- "Check if WAAS is connected" → `health_check()`

## Development

```bash
# Clone
git clone git@github.com:yc-software/waas-mcp.git
cd waas-mcp

# Install locally
uv tool install --from . waas-mcp

# After making changes, reinstall
uv tool install --force --from . waas-mcp
# Then restart Claude Code
```

### Local dev setup

For testing against local bookface (`http://bookface.yclocal.com`):

1. Create an OAuth app at `http://account.yclocal.com/oauth/applications/new` (non-confidential, redirect URI `http://localhost:19877/callback`, scopes `candidates:read candidates:manage`)
2. Register with host overrides:
```bash
claude mcp add waas \
  -e WAAS_CLIENT_ID=your_local_client_id \
  -e WAAS_API_HOST=http://bookface.yclocal.com \
  -e WAAS_API_HOST_HEADER=public-api.yclocal.com:3002 \
  -e WAAS_TOKEN_HOST=http://account.yclocal.com \
  -- uvx --from /path/to/waas-mcp waas
```
3. Run `waas login` — browser opens to local auth page

## Troubleshooting

**"Not authenticated"** — Run `waas login` to authenticate via browser.

**"Client authentication failed"** — The OAuth app must be **non-confidential**. Confidential apps hash secrets, making the PKCE token exchange fail.

**Token expired** — Tokens auto-refresh. If refresh fails, run `waas login` to re-authenticate.

**Wrong environment** — Run `health_check` to see which host you're hitting. Check `~/.claude.json` for duplicate MCP entries if it's pointing to the wrong environment.

**Local dev 404** — The API routes require `Host: public-api.yclocal.com:3002`. Set `WAAS_API_HOST_HEADER` in your env config.

**Rate limiting** — The WAAS API rate-limits write operations. When batch-archiving candidates, space out calls or retry on 429 responses.

## Changelog

### v0.4.0

**New tools:** `job_show`, `job_create`, `job_update` — read, create, and edit WAAS job postings.

**New OAuth scope required:** `waas:jobs:manage` — needed for `job_create`/`job_update`. Run `waas login` to re-authenticate and pick up the new scope.

Every field's valid values (role, subtypes, job_type, remote, pay_period, currency, state, …) are encoded as enums in the tool input schemas; the conditional rules (subtype-depends-on-role, min_experience vs min_school_year, remote='no' requires a location) are in the tool descriptions. See "Job postings (create / edit)" above.

### v0.3.0

**Breaking: cursor-based pagination for `applicant_list`**

The `limit` and `offset` parameters have been removed. The API now uses cursor-based pagination, consistent with all other collection endpoints in the YC API.

```
# First page — omit cursor
applicant_list()

# Next page — pass next_cursor from previous response
applicant_list(cursor: "abc123-uuid:50")
```

The response shape is `{ items: [...], next_cursor: "..." }`. When `next_cursor` is `null`, you've reached the last page. The API returns HTTP 400 with `error: "deprecated_pagination"` if `limit` or `offset` are sent.

### v0.2.0

**New tools:**

- `job_list` — list your company's jobs with pipeline stages
- `pipeline_show` — full pipeline board view for a job, including a virtual "Applied" stage for candidates not yet placed in a stage
- `pipeline_move` — move candidates between pipeline stages (works for all candidates)
- `candidate_create` — add a new candidate to a job's pipeline with optional resume upload. Candidates added this way are only visible to your company.

**New OAuth scope required:** `waas:candidates:manage` — needed for `candidate_create`. Run `waas login` to re-authenticate and pick up the new scope, or add it to your existing token.

**Fixes:**

- API responses with empty bodies (204 No Content) no longer cause JSON parse errors
