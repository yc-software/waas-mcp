# waas-mcp

> **Superseded by Bookface MCP. This repository will no longer be maintained.** Use YC's hosted Bookface MCP server for Work at a Startup and the rest of Bookface.

Bookface MCP supports every recruiting workflow from this standalone server, including job authoring, applicant triage, pipeline management, messaging, notes, and candidate creation with resumes. It also adds semantic candidate sourcing, contact reveal, and tools for fundraising, company launches, scheduling, and more.

Connect by URL and sign in with your YC account. The hosted server requires no local Python package or `waas login`.

## Connect to Bookface MCP

Add this URL in an MCP client that supports Streamable HTTP and OAuth:

```text
https://api.ycombinator.com/v1/mcp
```

MCP access must be enabled for your account. Available tools depend on your Bookface role, company access, and connected services; hiring tools require Work at a Startup access.

### Claude Code

```bash
claude mcp add --transport http --scope user bookface https://api.ycombinator.com/v1/mcp
```

Open `/mcp` in Claude Code, select `bookface`, and authenticate with your YC account. Then ask:

> Check my WAAS hiring readiness and show my company's jobs.

The agent can use `hiring.status` to check readiness and current sourcing budgets, then `hiring.list_jobs` to list your jobs.

If you previously registered this standalone server as `waas`, remove that entry after connecting:

```bash
claude mcp remove waas
```

### Codex

Register the hosted server and authenticate from your terminal:

```bash
codex mcp add bookface --url https://api.ycombinator.com/v1/mcp
codex mcp login bookface
```

Follow the browser authentication flow and sign in with your YC account. Start a new Codex session and use `/mcp` to check that Bookface is connected. Then ask:

> Check my WAAS hiring readiness and show my company's jobs.

If you previously registered this standalone server in Codex as `waas`, remove that entry after connecting:

```bash
codex mcp remove waas
```

See the [official Codex MCP documentation](https://learn.chatgpt.com/docs/extend/mcp?surface=cli) for additional configuration options.

## Work at a Startup

Bookface MCP offers 22 hiring actions covering recruiting from sourcing through pipeline management.

### Everything from this server

| Workflow | Bookface MCP tools |
|---|---|
| List applicants across your company, filter by job, state, date, or response needed, and use compact triage views | `hiring.list_applicants` |
| Read a candidate's profile, company status, and internal notes together | `hiring.get_candidate` |
| Read up to 25 candidates in one call | `hiring.get_candidates` |
| Update candidate state, archive reason, or pipeline stage | `hiring.update_candidate` |
| Read message threads and send candidate messages | `hiring.get_candidate_messages`, `hiring.send_candidate_message` |
| Add internal candidate notes | `hiring.add_candidate_note` |
| List jobs, inspect all editable fields, create drafts, edit postings, publish, and unpublish | `hiring.list_jobs`, `hiring.get_job`, `hiring.create_job`, `hiring.update_job` |
| Read complete pipelines, including the virtual Applied stage, and move candidates between stages | `hiring.get_pipeline`, `hiring.move_candidates` |
| Create private candidates with optional PDF, DOC, or DOCX resumes | `hiring.prepare_resume_upload`, `hiring.create_candidate` |
| Check authenticated hiring readiness | `hiring.status` |

### Additional hiring capabilities

| Capability | What you can do |
|---|---|
| **Semantic candidate sourcing** | Describe the experience and skills you need, combine semantic and keyword search with structured filters, and find candidates beyond your existing applicants using `hiring.search_candidates`. |
| **Search beyond the first page** | Read stored matches with `hiring.get_search_results`, request another retrieval batch with `hiring.extend_search_results`, and poll for results without starting the search over. |
| **Location-based sourcing** | Use `hiring.geocode` to resolve locations into coordinates and geographic bounds for candidate searches. |
| **Explicit contact reveal** | Unlock sourced candidates' email addresses with `hiring.reveal_candidate_contact`. General candidate browsing keeps sourced email private. |
| **Contact and outreach budgets** | See your company's current contact-reveal and cold-outreach usage, caps, and remaining allowance with `hiring.status`. |
| **Richer application details** | Read application messages, custom answers, contact details, and resume links for a job with `hiring.get_job_applicants`. |
| **More predictable batch operations** | Candidate batches identify unavailable IDs. Pipeline moves validate the entire batch before moving anyone and return the IDs moved. |

For eligible candidate accounts, Bookface also provides tools to search jobs, manage a candidate profile, and apply to YC startups.

## Beyond hiring

The same connection gives your agent access to other Bookface workflows, subject to your account's permissions:

| Area | Capabilities |
|---|---|
| **YC network and knowledge** | Search companies, founders, investors, forum posts, launches, startup-library content, and jobs; export supported search results to CSV. |
| **Fundraising** | Manage investor prospects and rounds, create investor decks, manage tracked pitch-deck links, inspect viewing analytics, and request or read pitch feedback. |
| **Demo Day** | Gather presentation materials, draft or revise slides, review presentations, and check readiness. |
| **Company and founder profiles** | Read and update profiles, inspect company goals, post company news, and read sales-call feedback. |
| **Launching your company** | Track launch progress, draft and publish Launch Bookface posts, and manage YC directory and Launch YC steps. |
| **Scheduling and events** | Browse, request, and book partner office hours; view batch events; create community events; and manage YCal scheduling links. |
| **Runway planning** | Read and edit cash runway scenarios and explore revenue, spending, and fundraising assumptions. |
| **Community and resources** | Find and redeem YC deals, recommend founders to YC, and read accessible YC Slack channel transcripts. |
| **Documents and meeting context** | Find company batch documents and retrieve accessible office-hour, Circleback, and Granola transcripts. |
| **Research and prospecting** | Search the web, read pages, find similar companies, and research prospective customers or partners outside the YC network. |

Try asking:

- "Find backend engineers with distributed-systems experience who were active in the last 30 days."
- "Review applicants who need a response and summarize the strongest matches for this job."
- "Create a hidden draft of a product designer job posting."
- "Show my investor pipeline and which prospects need a follow-up."
- "Find YC companies that match our ideal customer profile and export the results."
- "Show upcoming partner office hours and our batch events."

## Migrating existing workflows

The hosted tools preserve the workflows with updated names and arguments. Use the schemas advertised by your MCP client when adapting saved prompts or scripts.

- **Candidate reads:** `hiring.get_candidate` includes the profile, status, and notes that previously required separate tools. Batch reads take an array of `short_ids`.
- **Job authoring:** Put creation fields inside `job_attributes` and partial updates inside `job_updates`. All 23 editable fields from this server are supported.
- **Pagination:** Follow `next_cursor` for applicant and pipeline listings. Pipelines are returned in bounded pages, including empty stages and Applied.
- **Resume uploads:** Call `hiring.prepare_resume_upload`, upload the file using its returned HTTP instructions, then pass `resume_upload_token` to `hiring.create_candidate`. Resumes may be up to 5 MiB; your agent needs the ability to upload a file over HTTP.
- **Tool names:** Hiring actions use names such as `hiring.list_jobs`; some clients display those names with underscores.

The previous standalone setup instructions and changelog remain available in this repository's Git history.
