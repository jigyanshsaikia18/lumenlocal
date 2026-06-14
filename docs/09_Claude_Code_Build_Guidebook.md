# Claude Code Build Guidebook (Beginner Edition)
## Building LumenLocal step by step — even if you've never shipped software

| | |
|---|---|
| **Audience** | Beginners. Assumes near-zero coding experience but willingness to read and run commands. |
| **You will build** | The GBP platform specified in `/docs` (PRD, architecture, schema, API, backlog). |
| **Companion docs** | All of `/docs`, especially `06_Backlog_Epics_and_Stories.md` and `07_CLAUDE.md`. |

> **Mental model:** Claude Code is a skilled junior engineer that lives in your terminal. It can read your whole project, write and edit files, run commands, and test. **Your job is to be the manager:** give it one clear task at a time, review its work, and keep it on the rails. This guide gives you the exact words to say.

---

## Part 1 — What Claude Code is (60-second version)

Claude Code is Anthropic's agentic coding tool. It runs in your **terminal** (also VS Code, JetBrains, a desktop app, and the web at `claude.ai/code`). Unlike a chatbot, it can actually **read your files, edit them, run commands, and test code** — with your approval at each risky step.

Key safety idea: it asks permission before doing dangerous things (you'll see prompts). You stay in control.

---

## Part 2 — Setup (do this once)

### 2.1 Install the prerequisites
You need three things installed on your computer:

1. **Node.js (v18 or newer)** — runs Claude Code and the frontend.
2. **Python (3.11 or newer)** — runs the backend.
3. **Docker Desktop** — runs the database (Postgres) and queue (Redis) without you installing them manually.
4. **Git** — version control (so you can undo anything).

> If you don't have these, search "install Node.js", "install Python 3.11", "install Docker Desktop", "install Git" for your operating system. Install, then restart your terminal.

### 2.2 Install Claude Code
Open your terminal and run:
```bash
npm install -g @anthropic-ai/claude-code
```
Then start it and sign in:
```bash
claude              # starts Claude Code; follow the browser sign-in
```
Once it's running, type `/doctor` inside the session to confirm the install is healthy (`/doctor` is a slash command you run *inside* Claude Code, not a shell command).
You'll need a Claude subscription or an Anthropic Console account (a paid plan is required for real work).

> Tip: VS Code users can install the "Claude Code" extension from the Marketplace and run it in a side panel instead of the terminal — same engine, friendlier for beginners.

### 2.3 Create your project folder
```bash
mkdir lumenlocal && cd lumenlocal
git init
mkdir docs
# copy all the /docs markdown files (this whole set) into ./docs
# copy 07_CLAUDE.md to the repo root and RENAME it to CLAUDE.md
cp docs/07_CLAUDE.md CLAUDE.md
```
This is the single most important setup step: **`CLAUDE.md` in your repo root is the rulebook Claude Code reads every session.**

### 2.4 Start Claude Code in the project
```bash
claude
```
First thing, let it learn the project:
```
> Read CLAUDE.md and everything in /docs. Summarize in 5 bullet points what we're building, the stack, and the most important rules. Do not write any code yet.
```
If the summary is right, you're ready.

---

## Part 3 — The 7 controls you'll use constantly

| Control | What it does | When you use it |
|---|---|---|
| **Plain prompt** | Tell Claude what to do | Always |
| **Plan Mode** (`Shift+Tab` twice) | Read-only "think first" mode — it proposes a plan, edits nothing | Before any non-trivial task |
| **`/model`** | Switch the AI model | Match model to task (see Part 5) |
| **`/clear`** | Wipe the conversation, fresh start | Starting a new ticket |
| **`/compact`** | Summarize a long session to save memory | When a session gets long |
| **`/cost`** | See token usage / spend | To watch your budget |
| **`@filename`** | Point Claude at a specific file | "Look at `@docs/04_Database_Schema.md`" |

Two more you'll like: type `!` to run a shell command yourself without the AI, and `#` to save a note to memory.

**Permission modes** (cycle with `Shift+Tab`): *Default* (asks before each action) → *Auto-Accept Edits* (applies file edits without asking; still asks for shell) → *Plan* (read-only). Beginners: stay in **Default** until you trust a task, then use Auto-Accept for repetitive edits.

---

## Part 4 — The universal workflow (use for EVERY ticket)

This is the loop you repeat for each ticket in `06_Backlog_Epics_and_Stories.md`. Memorize it.

```
1. /clear                          (start fresh)
2. Tell Claude which ticket + which docs to read
3. Plan Mode (Shift+Tab twice): ask for a plan
4. Review the plan → approve or correct
5. Let it implement in small steps
6. Ask it to write & run tests
7. Review the diff → commit on a branch
```

### The reusable ticket prompt (fill in the blanks)
```
We are working on ticket [P1A-1]. 
First read: CLAUDE.md, /docs/04_Database_Schema.md, and the ticket text in /docs/06_Backlog_Epics_and_Stories.md.
Then enter plan mode and propose how you'll implement ONLY this ticket. 
List the files you'll create/change and the tests you'll write. 
Do not write code until I approve the plan.
```
After you approve:
```
Looks good. Implement step 1 only, then pause so I can review before continuing.
```

> Why "step 1 only, then pause"? It keeps changes small and reviewable. Big-bang prompts are how beginners get into messes.

---

## Part 5 — Which model for which job

Switch anytime with `/model`. Rough guide:

| Model | Strength | Use it for |
|---|---|---|
| **Claude Opus 4.8** | Most powerful reasoning | Architecture decisions, the entitlement resolver, the **Policy Compliance Engine**, tricky async/queue logic, hard bugs, Plan Mode on complex tickets |
| **Claude Sonnet 4.6** | Balanced workhorse (your default) | Most coding: CRUD endpoints, models, UI components, routine tickets |
| **Claude Haiku 4.5** | Fast + cheap | Boilerplate, simple edits, scaffolding tests, quick file lookups |
| **Claude Fable 5** | Newest top-tier (if on your plan) | The most demanding reasoning when Opus isn't enough |

Beginner rule of thumb: **plan and tough logic in Opus, build in Sonnet, grunt-work in Haiku.** Cheaper models for simple work saves money (watch `/cost`).

---

## Part 6 — Skills, Plugins, Subagents, Hooks & MCP (what they are, when to bother)

You don't need these on day one. Add them as the project grows.

### 6.1 Skills — reusable "how we do X here" bundles
A **skill** is a folder (`.claude/skills/<name>/SKILL.md`) with instructions (and optional scripts) Claude loads when relevant. Great for repeated domain logic so you don't re-explain it.
**Build these project skills as you go:**
- `gbp-api-adapter` — how to call the GBP APIs safely (rate limits, reply-only reviews).
- `compliance-rule` — how to express a Policy Center rule and test it.
- `new-endpoint` — the standard recipe (model → schema → route → entitlement → test).

Prompt to create one:
```
Create a Claude Code skill at .claude/skills/new-endpoint/SKILL.md that documents our standard recipe for adding a FastAPI endpoint: define the Pydantic schema, add the route under app/api/v1, enforce tenant+RBAC+entitlement+quota middleware in the order from /docs/05_API_Specification.md §12, and write a pytest contract test. Keep it concise.
```
List skills with `/skills`.

### 6.2 Plugins — shareable bundles
A **plugin** packages skills + subagents + commands + hooks + MCP servers as one installable unit. Browse/install with `/plugin`. Early on, you mostly *consume* community plugins (e.g. a Python testing helper). Later you can bundle your own team conventions into a plugin so every developer gets the same setup with one command.

### 6.3 Subagents — parallel helpers with their own context
A **subagent** is a separate Claude session for a scoped job (e.g. "explore the codebase and report where tenant scoping is enforced") without cluttering your main conversation. Use the built-in `Explore` and `Plan` subagents for research. **Keep subagents read-only** (they can't ask you for permission). List with `/agents`.
```
Use the Explore subagent to find every place we query the database without a tenant_id filter, and report a list. Don't change anything.
```

### 6.4 Hooks — automatic guardrails (highly recommended for this project)
**Hooks** are scripts that run at fixed moments. They *enforce* rules `CLAUDE.md` only *requests*. Set these up early (ask Claude to write them):
- **PreToolUse on `Bash`** — block dangerous commands (`rm -rf`, `DROP TABLE`, `git push --force`).
- **PostToolUse on `Write|Edit`** — auto-run the formatter (`black`/`prettier`) and lint.
- **PreToolUse on `Write`** — scan for secrets so no API key gets committed.
Prompt:
```
Set up Claude Code hooks in .claude/settings.json: 
1) PreToolUse on Bash that denies (exit 2) commands matching rm -rf, DROP TABLE, or force push. 
2) PostToolUse on Write|Edit that runs black on .py and prettier on .ts/.tsx. 
Put the hook scripts in .claude/hooks/. Explain how to test them.
```

### 6.5 MCP — connect Claude Code to external tools
**MCP servers** give Claude Code extra tools. Two useful ones here:
- A **Postgres MCP** so Claude can inspect your dev database directly.
- A **GitHub MCP/App** for PR reviews (`/install-github-app`).
Manage with `/mcp`. (Separately, *our product itself* exposes an MCP server — that's ticket P5C-2, different thing.)

---

## Part 7 — The build, phase by phase (with exact prompts)

Work in this order. Each phase = several tickets. After each ticket: test, then commit. Re-`/clear` between tickets.

### PHASE 0 — Scaffold
**Ticket P0-1** (start in Opus or Sonnet, Plan Mode):
```
Ticket P0-1. Read CLAUDE.md and /docs/02_Technical_Architecture.md §10. 
In plan mode, propose a monorepo: backend/ (FastAPI + Poetry), frontend/ (Next.js App Router + TypeScript + Tailwind), root docker-compose.yml with Postgres 15 and Redis. 
List files you'll create. No code until I approve.
```
Then:
```
Implement the scaffold. After creating files, give me the exact commands to verify it: starting docker, installing deps, and running each app's dev server.
```
Verify yourself:
```bash
docker compose up -d          # database + redis start
# follow Claude's instructions to run backend and frontend
```
Commit:
```
Create a branch phase0/p0-1-scaffold and commit everything with a conventional commit message.
```

**P0-2 / P0-3** — same loop (CI skeleton, env/secrets). Prompt pattern identical: "Ticket Px, read these docs, plan, implement step 1, pause."

### PHASE 1 — Agency spine
**Database first (P1A-1)** — switch to **Sonnet**:
```
Ticket P1A-1. Read /docs/04_Database_Schema.md sections 2–3. 
Plan, then create SQLAlchemy models + an Alembic migration for: tenants, clients, users, user_roles, role_permissions, plans. 
Match the schema exactly — do not invent columns. Then write a test that imports all models without error and run it.
```
**Tenant isolation (P1A-2)** — **Opus** (security-critical):
```
Ticket P1A-2. Implement tenant isolation so no query can read another tenant's rows. Prefer Postgres row-level security if practical. Write a pytest that proves a Tenant A user cannot read Tenant B data, and run it. Show me the test first.
```
**Auth + RBAC (P1B-1, P1B-2)** — Sonnet for auth, **Opus for RBAC**:
```
Ticket P1B-2. Read /docs/05_API_Specification.md §1–3 and CLAUDE.md. 
Implement capability-based RBAC middleware (e.g. reviews.reply). Out-of-scope returns 403. 
Write tests covering each role: super_admin, agency_admin, account_manager, client_owner, analyst. Run them.
```
**Entitlement engine (P1C-1)** — **Opus** (this is the differentiator, get it right):
```
Ticket P1C-1. Read /docs/01_PRD.md §5 and /docs/04_Database_Schema.md §3. 
In plan mode, design the feature-flag resolver with precedence location > client > plan > default, plus dependency validation. 
Then implement it and write thorough pytest unit tests covering ALL four precedence levels and the dependency rule. Mock the DB. Show tests before implementing logic.
```
Continue P1C-2…P1E-3 with the same loop. For UI tickets, mention the design skill:
```
Ticket P1E-1. Read /docs/01_PRD.md Module 1, then read .claude/skills/ for our frontend conventions if present. Build the dashboard health-score + performance widgets as Next.js components with Tailwind. Make it feel premium and white-label themeable. Add a vitest component test that the widget hides when its feature flag is off.
```

### PHASE 2 — GEO + classic rank (this completes your MVP)
**Queue first (P2A-1)** — Opus:
```
Ticket P2A-1. Set up Celery + Redis: a task framework with retries, idempotency, a dead-letter queue, and per-tenant fairness so one big agency can't starve others. Add a trivial example task and a test that it enqueues and runs.
```
**Geo-grid math (P2B-1)** — Opus (math correctness matters):
```
Ticket P2B-1. Read ticket P2B-1 in /docs/06_Backlog_Epics_and_Stories.md. Implement: given center lat/long, radius in miles, and grid dimensions, compute the coordinate of every node. Then a Celery worker that (mock the Google query for now) records a result per node into geogrid_scans with a SoLV value. Unit-test the coordinate math against hand-computed golden values. Show me the math approach in plan mode first.
```
**GEO flagship (P2C-1…P2C-5)** — Opus for the abstraction, Sonnet for UI:
```
Ticket P2C-1. Read /docs/01_PRD.md Module 3. Build a provider-abstraction interface for AI-search visibility that normalizes responses from multiple providers (AI Overviews, AI Mode, Gemini, ChatGPT, Perplexity, Grok) into a common record of {provider, mentioned, prominence, cited_sources}. Implement ONE mock provider plus the interface. Write tests that feed a sample provider response and assert correct normalization. Real provider calls come later.
```
> Keep real provider access behind config; in tests always use mocks (see `08_Test_Strategy.md` §3).

### PHASE 3 — Compliance gateway FIRST, then reviews/content
**Build the engine before any write feature (P3A).** Opus:
```
Ticket P3A-2. Read /docs/01_PRD.md §9 and CLAUDE.md compliance rules. 
Implement the Policy Compliance Engine as a mandatory gateway every external write must pass. Hard violations return 422 with {rule, ruleset_version} and are logged to compliance_events. 
Write tests proving: an incentive word ('discount') in a review reply is blocked; a staff-name solicitation is blocked; and add a test that FAILS if any schema column or API field could enable sentiment-based review routing. Run them.
```
Then reviews/content tickets — each one, remind Claude: "every external write goes through the Policy Engine."

### PHASE 4–6
Same loop. For protection (P4A-2) reinforce the safety rule explicitly:
```
Ticket P4A-2. Implement profile protection reverts. revert_mode has three values: alert_only (default, NO auto-write), auto_revert_critical (only the narrow malicious patterns, rate-limited, audited), off. 
Do NOT build any timer-based silent corrective write. Write tests proving alert_only never writes to Google and auto_revert_critical only reverts allowed fields. 
```

---

## Part 8 — How to test (and what to test)

For **every** ticket, after implementing:
```
Write unit tests for what you just built following /docs/08_Test_Strategy.md, then run them. Fix only failures related to this ticket. Report coverage of the new code.
```
Run suites yourself anytime with `!`:
```
!cd backend && pytest -q
!cd frontend && npx vitest run
```
**The five things you must always test** (from `08_Test_Strategy.md`):
1. **Entitlement resolver** — all 4 levels + dependencies.
2. **Compliance engine** — that violations are *blocked* (gating, incentives, reply-only).
3. **Tenant isolation** — no cross-tenant access.
4. **Protection** — bounded revert, no silent writes.
5. **Geo/GEO math** — coordinates, SoLV, SAIV.

Before merging a phase, walk its **exit criteria** in `03_Phased_Roadmap.md` by hand.

---

## Part 9 — Staying safe & out of trouble

- **Always work on a branch**, never directly on `main`. Commit after each ticket so you can roll back.
- **Make a checkpoint commit before big tasks.** If Claude goes sideways, `git restore` / `git checkout .`.
- **Review diffs before approving.** Read what changed; don't blind-accept.
- **Never run with `--dangerously-skip-permissions`** outside a throwaway sandbox.
- **Don't let it loop.** If Claude keeps "fixing" and breaking things, stop (`Esc`), `/clear`, and give a narrower instruction pointing at specific files/lines.
- **Keep secrets out of git.** The secret-scan hook (Part 6.4) helps; also add a `.gitignore` for `.env`.

---

## Part 10 — Cost & context control

- Watch spend with `/cost`. Use **Haiku for cheap grunt work**, **Sonnet by default**, **Opus only for hard/critical parts**.
- Long sessions get expensive and forgetful. Use **`/clear` between tickets** and **`/compact`** mid-ticket if needed.
- Keep `CLAUDE.md` short (~100 lines). Point to `/docs` for detail rather than pasting it.
- **Narrow prompts beat broad ones** — both for quality and cost. "Fix the timeout in lines 45–60 of tasks.py" not "fix all the errors."

---

## Part 11 — When you get stuck (debugging prompts)

- Paste the error:
  ```
  I ran `pytest` and got this error: <paste>. 
  Find the root cause, explain it in plain English, propose a fix, and wait for my OK before changing files.
  ```
- It references a file that doesn't exist or broke something unrelated:
  ```
  Stop. You changed files outside this ticket. Revert those, and only touch the files listed in the ticket plan.
  ```
- It's going in circles:
  ```
  Let's reset. /clear, then we restart this ticket with a smaller first step: just <one small thing>.
  ```
- You don't understand the code it wrote:
  ```
  Explain what this function does, line by line, as if I'm new to programming.
  ```

---

## Part 12 — A realistic first day

1. Do all of Part 2 (setup).
2. Ask Claude to summarize the project (Part 2.4).
3. Set up the safety **hooks** (Part 6.4).
4. Build **P0-1** (scaffold) end to end: plan → implement → verify → commit.
5. Build **P1A-1** (database models) → test → commit.
6. Stop. You now have a running skeleton with a database. Everything after is the same loop, ticket by ticket.

> The whole platform is just this loop repeated across the backlog, in phase order, with the compliance and entitlement rules never bent. Go one ticket at a time and you'll get there.

---

## Quick command cheat-sheet
```
claude                       start a session
/doctor                      check install health
/init                        create a project CLAUDE.md (we provide one)
Shift+Tab (x2)               Plan Mode (read-only)
/model                       switch model
/clear                       fresh conversation (between tickets)
/compact                     summarize a long session
/cost                        usage & spend
/skills /agents /plugin /mcp list extensions
@file                        point Claude at a file
!cmd                         run a shell command yourself
#note                        save a memory note
/review                      review pending branch changes
/export                      save the conversation to Markdown
```
