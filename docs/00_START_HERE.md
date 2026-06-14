# START HERE — How to Build LumenLocal with Claude Code

This folder is a **complete, build-ready specification** for an agency-first, GEO-native Google Business Profile (GBP) optimization platform, designed to be built using **Claude Code**.

## The document set (read in this order)

| # | Document | What it is | Who/what reads it |
|---|---|---|---|
| 00 | **START_HERE.md** (this file) | Map of everything + how to drive Claude Code | You |
| 01 | `01_PRD.md` | Product Requirements — what we're building and why | You + Claude Code |
| 02 | `02_Technical_Architecture.md` | System design, components, stack | Claude Code |
| 03 | `03_Phased_Roadmap.md` | Build order (Phase 0 → 6) | You (to sequence work) |
| 04 | `04_Database_Schema.md` | Full PostgreSQL schema | Claude Code |
| 05 | `05_API_Specification.md` | REST endpoint contracts | Claude Code |
| 06 | `06_Backlog_Epics_and_Stories.md` | Every feature broken into buildable tickets | You + Claude Code (one ticket = one work session) |
| 07 | `07_CLAUDE.md` | The project memory file — **copy this to your repo root as `CLAUDE.md`** | Claude Code (loaded every session) |
| 08 | `08_Test_Strategy.md` | What to test and how | Claude Code |
| 09 | `09_Claude_Code_Build_Guidebook.md` | **Beginner's step-by-step guide with every prompt** | You |

## The one-paragraph summary
You will build a multi-tenant SaaS where **agencies** manage many clients' GBPs. The headline differentiator is **AI-search / GEO visibility** (showing up in AI Overviews, Gemini, ChatGPT, etc.), and the platform is **compliant by architecture** (it structurally cannot do the things that get profiles suspended). Agencies can toggle features **per client**. Stack: **Next.js + FastAPI + PostgreSQL + Redis/Celery**.

## How to actually build it (the short version)
1. Install Claude Code and the tools in **`09_Claude_Code_Build_Guidebook.md` §1–2**.
2. Copy `07_CLAUDE.md` into your new repo as `CLAUDE.md`. This is the single most important step — it tells Claude Code the rules every session.
3. Put this entire docs folder inside your repo (e.g. `/docs`) so Claude Code can read it.
4. Work **one ticket at a time** from `06_Backlog_Epics_and_Stories.md`, following the **phase order** in `03_Phased_Roadmap.md`.
5. For each ticket, use the **prompt patterns** in the guidebook (§4 onward). Plan first, build small, test, commit.

## The golden rules (expanded in the guidebook)
- **Small steps, frequent commits.** Never ask for "build the whole app." One ticket per session.
- **Plan before building.** Use Plan Mode (`Shift+Tab` twice) for anything non-trivial.
- **Test as you go.** A feature isn't done until its tests pass.
- **Use Git branches + checkpoints.** Claude Code edits real files; protect yourself.
- **Compliance is non-negotiable.** The rules in `CLAUDE.md` about review gating, auto-revert, and API limits are not optional — they're why this product is safe to sell.

Start with **`09_Claude_Code_Build_Guidebook.md`**.
