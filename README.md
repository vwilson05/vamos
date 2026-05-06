# vamos

> A multi-agent CLI + browser UI that automates the parts of Azure DevOps life that nobody likes doing — built at HaloMD, public on the off chance it's useful elsewhere.

vamos is one Python binary plus one NiceGUI browser app, bundling every workflow agent we use against Azure DevOps:

- **Personal daily flow** — pulls your assigned ADO tickets into a daily markdown file, syncs your edits back to ADO every few hours, posts an EOD summary to Teams or Slack.
- **Team reporting** — per-developer healthcheck snapshots, board metrics for leadership, hygiene checks against your standards, at-risk scans for past-target / blocked items.
- **PR review** — reviews Azure DevOps PRs (interactively or as a polling service) and posts structured findings as inline comments. Powered by Claude.
- **AI-assisted cleanup** — for hygiene findings, vamos proposes concrete fixes (comment text, state changes, field values) and applies them on confirm.

CLI for engineers, browser UI for project leadership / non-techies. Same backend either way. Cross-platform (macOS, Linux, Windows).

---

## Quick start

**Prerequisites**
- Python 3.10+
- An Azure DevOps Personal Access Token (Work Items R/W; plus Code R/W + Pull Request Threads R/W if you want PR review)
- Optional: [Claude Code](https://docs.claude.com/claude-code) — needed for `sync`, `eod`, `pr-review`, and the AI-driven hygiene cleaners

**macOS**

```bash
git clone https://github.com/vwilson05/vamos.git
cd vamos
cp .env.example .env
open .env                     # fill ADO_ORG_URL, ADO_PROJECT, ADO_PAT, DEVELOPER_NAME
```

Then **double-click `launch.command`** in Finder, or run `./launch.sh`. First run installs deps (~60s); browser opens to http://localhost:8501.

If macOS blocks the script the first time ("can't be opened, unidentified developer"), right-click → Open → Open. macOS remembers the choice.

**Windows**

```powershell
git clone https://github.com/vwilson05/vamos.git
cd vamos
copy .env.example .env
notepad .env                  # fill in same fields
```

Then **double-click `launch.bat`**, or run `.\launch.ps1`. If PowerShell blocks scripts, run once: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

**CLI only (no browser UI)**

```bash
./launch.sh --no-ui           # just the venv + dep install
source .venv/bin/activate
vamos --help                  # see every subcommand
```

---

## Three deployment shapes

vamos is one binary, three roles. Pick the recipe that matches you:

| Profile | Where it runs | What it runs | `.env` |
|---|---|---|---|
| **Personal** | Each engineer's laptop | `vamos daily` (cron) + ad-hoc `pr-review` | `.env` + `.env.personal` |
| **Team service** | One always-on host or GitHub Actions | `vamos metrics` / `healthcheck` / `hygiene` / `pr-review --watch` (cron, service PAT) | `.env` + `.env.team` |
| **On-demand** | Any laptop | Anything ad-hoc; `vamos ui` for non-techies | Whatever's local |

Profiles are layered: a base `.env` holds shared values; `.env.personal` or `.env.team` overlays profile-specific PATs and webhooks. Pick at runtime via `--profile personal|team` or `VAMOS_PROFILE=team`. Both example files ship in the repo.

---

## CLI reference

All commands accept `-v` / `--verbose` and `--profile {personal,team}`.

**Personal flow**

| Command | What it does |
|---|---|
| `vamos sod` | Pull today's assigned tickets into `work/YYYY-MM-DD.md`. |
| `vamos sync --dry-run` | Preview what sync would change. |
| `vamos sync` | Apply markdown edits to ADO (state changes, comments, new tickets). |
| `vamos eod` | Generate EOD summary, run final sync, post to Teams/Slack. |
| `vamos daily` | Cron-friendly dispatcher: picks `sod` / `sync` / `eod` based on time + state. |
| `vamos prep` | One-shot: SOD + inbox + standup, all cached for instant UI load. |

**Team reporting**

| Command | What it does |
|---|---|
| `vamos healthcheck` | Per-developer ticket snapshot + team rollup. |
| `vamos metrics generate` | Backlog metrics report — HTML, Markdown, or JSON. |
| `vamos hygiene` | Run all 7 hygiene rules across project repos. Read-only by default. |
| `vamos hygiene --clean` | Walk findings, propose AI-generated fixes, prompt y/n per item. |
| `vamos hygiene --clean --apply` | Auto-apply fixes (gated by `HYGIENE_LIVE_MODE=true`). |
| `vamos at-risk` | Past-target / blocked P1s / aging items + aging PRs. |

**Engineer tools**

| Command | What it does |
|---|---|
| `vamos inbox` | Aggregated review-requests / comments / mentions / new P1s. |
| `vamos standup` | Auto-draft yesterday/today/blockers. |
| `vamos capture "<text>"` | Quick-add a `[NEW]` section to today's MD. |
| `vamos deps 1234` | Show parent/children/blocked-by/related links for a ticket. |

**Manager tools**

| Command | What it does |
|---|---|
| `vamos brief "Engineer Name"` | 1:1 brief covering the last week (or `--weeks N`). |
| `vamos retro` | Sprint retro starter (last 2 weeks). |

**PR review**

| Command | What it does |
|---|---|
| `vamos pr-review` | List active PRs across all project repos. |
| `vamos pr-review 1234` | Review specific PR — auto-detects repo. |
| `vamos pr-review --watch` | Service mode: poll every repo, auto-review new iterations. |
| `vamos review-queue` | Triaged queue, blocked-on-me first. |

**Setup & scheduling**

| Command | What it does |
|---|---|
| `./launch.sh` | macOS/Linux: ensure venv → install deps → launch UI. |
| `./launch.sh --install-crons` | Install vamos cron entries from `crons.yml`. |
| `./launch.sh --prep` | Run `vamos prep` before launching the UI. |
| `vamos cron-install` | Install scheduled tasks (cron on Unix, Task Scheduler on Windows). |
| `vamos cron-list` | Show configured + currently-installed scheduled tasks. |
| `vamos --board all hygiene` | Run team agents across every board in `.ado-metrics.yml`. |
| `vamos ui` | Launch the NiceGUI app on http://localhost:8501. |

---

## Configuration (`.env` reference)

vamos loads `.env` first as a baseline. If `--profile personal` or `--profile team` is set (or `VAMOS_PROFILE=…` is in the environment), it overlays `.env.personal` or `.env.team` on top — profile keys win. All three files live at the repo root and are git-ignored.

**Required (in `.env`):**

```bash
ADO_ORG_URL=https://dev.azure.com/HaloMDLLC
ADO_PROJECT=Data Platform
ADO_PAT=…
```

**Personal flow:**

```bash
ADO_USER_EMAIL=
ADO_READ_ONLY=false
DEVELOPER_NAME="Your Name"
CONNECTION_OPTION=Slack
TEAMS_WEBHOOK_URL=
SLACK_WEBHOOK_URL=
RUN_SOD_AT=08:00
RUN_EOD_AT=18:00
RUN_SYNC_INTERVAL_MIN=180
VAMOS_AUTO_PREP=false
```

**Team agents:**

```bash
HEALTHCHECK_AREA_PATH=Data Platform\\Engineering
HYGIENE_REPOS=                    # blank = auto-discover all repos in project
HYGIENE_LIVE_MODE=false           # required for auto-comment / clean --apply
HYGIENE_DAILY_COMMENT_DEADLINE=17:00
HYGIENE_STALE_BLOCKED_DAYS=5
```

The Settings page (`/settings` in the UI) lets you edit all of these in the browser, with masked secrets and a one-click connection test.

---

## Hygiene rules

vamos hygiene checks every team member's tickets against seven rules. Five of them have AI-assisted **Clean** support (vamos proposes a concrete fix; you confirm or reject).

| Rule | Severity | What it checks |
|---|---|---|
| `state-discipline` | should-fix | Two states only (Active + Blocked). One Active per engineer. Tickets in deprecated states (QA, PR Ready) flagged. |
| `daily-comments` | blocker | Active or Blocked tickets need a comment from the assignee on the current working day, before `HYGIENE_DAILY_COMMENT_DEADLINE` (default 17:00 local). |
| `required-fields` | should-fix | Every story needs: assignee, story points (1 SP = 1 hour), start date, target date. |
| `pr-linkage` | blocker | Every active PR must link to at least one ADO work item. |
| `branch-naming` | nit | PR source branches must match `feature\|bugfix\|hotfix / <ticket> - <slug>`. |
| `resolution-on-close` | should-fix | Closed tickets need a resolution note in Notes / Resolution / System.Reason. |
| `stale-blocked` | should-fix | Tickets in Blocked state for more than `HYGIENE_STALE_BLOCKED_DAYS` (default 5). |

`pr-linkage` and `branch-naming` are surfaced but not auto-fixable; the others all have cleaners.

---

## Operations

**State directories** — each agent writes to its own subdirectory under `state/`:

| Agent | Files |
|---|---|
| `daily` | `state/<date>-run.json` |
| `sync` | `state/<date>.json` + `state/logs/*.json` |
| `hygiene` | `state/hygiene/<date>.json` and `.md` |
| `pr-review` | `state/pr-review/iterations.json` + `state/pr-review/logs/*.json` |
| `inbox` / `standup` / `at-risk` | `state/<agent>/<date>.json` |

**Cron / Task Scheduler** — `vamos cron-install` reads `crons.yml` and installs scheduled tasks. On macOS/Linux, writes a marker-bracketed block to your crontab so installs are idempotent. On Windows, dispatches to `schtasks.exe`. `vamos cron-list` shows what's configured AND what's currently active on the system.

**Service mode** — `vamos pr-review --watch` polls every project repo for new PR iterations and auto-reviews. Run under systemd, launchd, or a long-running scheduled task. Reviewed iterations persist to `state/pr-review/iterations.json` so a restart resumes without re-reviewing.

**Safety rails:**
- `ADO_READ_ONLY=true` blocks all writes.
- `HYGIENE_LIVE_MODE=true` is required before `hygiene --auto-comment` or `hygiene --clean --apply` will write to ADO.
- `vamos pr-review --no-post` runs the review but doesn't post comments.
- Comments include the marker `<!-- vamos:pr-review -->` so re-runs never double-post on the same iteration.

---

## What's new

**0.5.0** — UI rebuilt on NiceGUI. Reactive components, native dark mode, real streaming logs, inline Clean dialog for hygiene, sidebar navigation. CLI unchanged.

**0.4.x** — `launch.sh` / `launch.command` / `launch.bat`, `crons.yml` declarative scheduling, Settings page in UI, hygiene `--clean` (AI-assisted finding fixes), Windows Task Scheduler support, `vamos prep` morning routine, auto-prep on launch.

**0.3.x** — board picker, log streaming, identity normalization (collapses ADO's split identities), 16 features across four personas (inbox, standup, capture, deps, brief, retro, at-risk, customer view, trends, blocked-on-me, buddy routing).

**0.2.x** — suite rename (`ado-agent` → `vamos`), hygiene agent with rule registry, pr-review consolidation, original Streamlit UI.

**0.1.x** — original ado-agent: sod / sync / eod / healthcheck / metrics.

---

## Project layout

```
vamos/                       Python package (CLI + agents + cleaners)
├── core/                    Shared building blocks (snapshot, report, delivery, state)
├── hygiene/                 7 rules + 5 cleaners (AI-assisted)
├── pr_review/               PR client + reviewer + watch service
├── metrics/                 Board metrics collector + report generator
└── cli.py                   Argparse entry point

ui/                          NiceGUI app
├── main.py                  Entry: vamos ui
├── theme.py                 Layout shell + components (kpi, pill, copy_button, ...)
├── streaming.py             Async log capture for long-running ops
└── pages/                   8 pages: home, my-day, inbox, team-status, pr-queue, brief, settings, help

prompts/                     Claude prompts for sync, eod, pr-review
templates/                   New-ticket template
launch.sh / .ps1 / .command / .bat   Cross-platform launchers
crons.yml.example            Declarative cron config
.env.example                 Config template (3 profiles)
```

---

## Contributing

Bug reports, feature ideas, and PRs welcome. Open an issue on https://github.com/vwilson05/vamos/issues.

The codebase is small (~6,500 LOC) and modular. Adding a new hygiene rule is one file in `vamos/hygiene/rules/`; adding a UI page is one file in `ui/pages/`. The Help page in the UI (`/help`) doubles as live in-app documentation.

## License

Public — use it, fork it, build on it. No warranty.
