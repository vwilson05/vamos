"""Help / README — in-app reference for vamos."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

from ui import style  # noqa: E402

st.set_page_config(page_title="Help · vamos", page_icon=None, layout="wide")
style.apply()
style.theme_toggle_in_sidebar()

cfg = style.get_cfg(st.session_state.get("profile_arg"), board=st.session_state.get("board_arg"))
st.session_state["cfg"] = cfg

style.section_header(
    "Help & reference",
    subtitle="What vamos is, how to run each agent, and how to configure deployment.",
)

tab_whatsnew, tab_overview, tab_cli, tab_config, tab_hygiene, tab_ops = st.tabs(
    ["What's new", "Overview", "CLI reference", "Configuration", "Hygiene rules", "Operations"]
)

# ============================================================================
# What's new
# ============================================================================
with tab_whatsnew:
    st.markdown("### vamos 0.4.2")
    st.caption("Released 2026-05-06  ·  Windows support · Auto-prep · One-command launcher · Settings · Hygiene clean.")

    with st.container(border=True):
        st.markdown("#### 0.4.2 patch — Windows support")
        st.markdown(
            """
- **`launch.ps1`** is now full feature-parity with `launch.sh`: `-InstallCrons`,
  `-Prep`, `-NoUi`, `-Update`, `-Port`, plus reads `VAMOS_AUTO_PREP` from `.env`.
- **`vamos cron-install` works on Windows** — translates the cron expressions
  in `crons.yml` to Task Scheduler entries via `schtasks.exe`. Supported
  patterns: `*/N * * * 1-5`, `0 H * * 1-5`, `0 H * * MON`, `*/N * * * *`,
  `0 H * * *`, plus `launchd` (run-on-startup).
- **`vamos cron-uninstall`** removes every `vamos-` task from Task Scheduler
  cleanly.
- **`vamos cron-list`** now also shows what's currently installed on the
  system (cron block on Mac/Linux, Task Scheduler entries on Windows).
            """
        )

    with st.container(border=True):
        st.markdown("#### 0.4.1 — auto-prep on launch (later this morning)")
        st.markdown(
            """
- **`vamos prep`** — one-shot morning routine: SOD (if needed) + inbox + standup.
  Persists each result to `state/<agent>/<YYYY-MM-DD>.{json,md}` so the UI
  loads them instantly without re-querying ADO.
- **`./launch.sh --prep`** — run prep before opening the UI.
- **`VAMOS_AUTO_PREP=true` in .env** (also a toggle in Settings) — `launch.sh`
  always preps when this is on. One command, you're ready.
- **My day page** now shows a **Today's prep** section at the top: standup
  brief on the left (with copy button), inbox preview on the right (top 6
  items). Auto-renders cached results; **Run prep** button rebuilds them.
            """
        )

    with st.container(border=True):
        st.markdown("#### 0.4.0 release")
        st.markdown(
            """
- **`launch.sh` / `launch.ps1`** — single-command setup. Creates the venv,
  installs deps, optionally installs cron entries, launches the UI. Use
  `./launch.sh --install-crons` to wire scheduled runs from `crons.yml`.
- **`crons.yml`** — declarative cron config. `vamos cron-install`,
  `cron-uninstall`, `cron-list` manage a marker-bracketed block in your
  crontab so installs are idempotent.
- **Settings page** — edit `.env`, `.env.personal`, `.env.team`, and
  `crons.yml` in the browser. Secrets masked by default; **Test connection**
  runs a smoke check against ADO. Preserves comments + ordering on save.
- **Hygiene `--clean`** *(CLI + UI button)* — for each finding, vamos asks
  Claude to propose a concrete fix (comment text, state change, field values),
  shows it to you, and applies on confirm. Five rules covered: state-discipline,
  daily-comments, required-fields, resolution-on-close, stale-blocked. CLI walks
  proposals with `y/n/all/skip-rule/quit`; UI shows a **Clean** button on every
  applicable finding card. Apply is gated by `HYGIENE_LIVE_MODE=true`.
- **Help moved to last in nav** (was 07; now 08 to make room for Settings).
            """
        )

    st.markdown("### vamos 0.3.1")
    st.caption("Patch 2026-05-05  ·  Board picker, log streaming, no-emoji sweep, healthcheck path fix.")

    with st.container(border=True):
        st.markdown("#### 0.3.1 patch")
        st.markdown(
            """
- **Board picker** *(global sidebar selector + `vamos --board <name>` CLI flag)* —
  switch between boards from `.ado-metrics.yml` (Ingestion Engineering, Platform
  Core, DevOps), or pick `(all boards)` to span every team in one query. Multi-board
  queries are resilient: aspirational paths that don't exist in ADO log a warning
  and are skipped, valid ones still return data.
- **Streaming logs** in every long-running operation — click any *Run X* button
  and watch the agent log lines appear in a status panel as they happen
  (timestamps + level + message). On error the panel turns red and stays
  expanded; on success it auto-collapses.
- **No-emoji sweep** — stripped emojis from healthcheck output, metrics CLI,
  PR-review printer, and the Report renderer. Severity now shows as bracketed
  text labels (e.g. `[BLOCKER]`) in markdown output and as colored pills in the UI.
- **Healthcheck path fix** — `developers.yml` is now read from the repo root
  (where it's actually stored), not from `work/`. If the file is empty or missing,
  healthcheck auto-discovers the team from ADO assignees in the configured
  area path.
- **Dark-mode contrast pass** — explicit text/background colors for every
  Streamlit widget (buttons, number-input ± steps, selectbox dropdowns, radios,
  checkboxes, expanders, toasts) so light buttons always have dark text and
  vice-versa.
- **Help moved to bottom of nav** so it doesn't interrupt the daily-use pages.
            """
        )

    st.markdown("### vamos 0.3.0")
    st.caption("Released 2026-05-05  ·  16 new features across 4 personas.")

    with st.container(border=True):
        st.markdown("#### For engineers")
        st.markdown(
            """
- **Inbox** *(new page + `vamos inbox`)* — single feed of review requests, comments
  on your tickets, @-mentions, and freshly-assigned P1/P2 items. Looks across every
  project repo + your assigned tickets.
- **Standup brief** *(My day card + `vamos standup`)* — auto-drafts yesterday/today/blockers
  from your daily MD + closed tickets + active items. Copy-pastable into Slack.
- **Quick capture** *(My day card + `vamos capture "<text>"`)* — append a `[NEW]` section
  to today's markdown from anywhere; next sync turns it into a real ticket.
- **Dependencies view** *(`vamos deps <id>`)* — shows parent / children / blocked-by /
  blocks / related links for a ticket so you can see the chain of stuckness.
- **Reply convention in MD** — keep using `### Notes` to thread your replies; vamos
  auto-posts them as comments and the daily MD becomes the running conversation.
            """
        )

    with st.container(border=True):
        st.markdown("#### For project leadership")
        st.markdown(
            """
- **Trends** *(Team status → Trends)* — week-over-week sparklines for blockers,
  should-fix, nits, total findings; per-engineer hygiene streaks (last 14 days);
  WoW change indicators.
- **Customers** *(Team status → Customers)* — every active ticket grouped by
  extracted customer (Vituity, UHC, MEMS, Northstar, …); active/blocked counts
  per customer; click to expand.
- **At-risk** *(Team status → At-risk + `vamos at-risk`)* — past-target tickets,
  P1s blocked >3d, items aging >14d, PRs aging >5d. The "what should I worry
  about" view.
- **Drill-down KPIs** — clicking a hygiene KPI tile filters the breakdown below.
            """
        )

    with st.container(border=True):
        st.markdown("#### For Jeff and other managers")
        st.markdown(
            """
- **1:1 brief** *(Brief page + `vamos brief <engineer>`)* — per-engineer summary
  for 1:1 prep: shipped this window, currently active, blocked, PRs, comments,
  hygiene record, clean-day count.
- **Sprint retro** *(Brief page → Retro tab + `vamos retro`)* — auto-draft retro
  starter: shipped, missed targets, top customers, recurring blocker themes,
  velocity (story points completed), discussion prompts.
- **Hygiene trends per engineer** *(Trends tab)* — shows each engineer's
  finding count over time as a sparkline plus their clean-day streak.
- **Identity normalization** — vamos collapses ADO's split identities
  (display-name vs email vs OIDCONFLICT_UpnReuse_…) so per-engineer reports
  don't double-count the same human.
            """
        )

    with st.container(border=True):
        st.markdown("#### For PR reviewers")
        st.markdown(
            """
- **Triaged review queue** *(PR queue → Triaged + `vamos review-queue`)* — sorted
  blocked-on-me first, then assigned (author/reviewer), then everyone else;
  shows age, role, and draft status.
- **Blocked on me** indicator — checks every open thread on every PR you're
  involved with; if the last comment isn't yours, it surfaces here.
- **Auto-buddy routing check** — define `buddies` in `routing.yml` (or
  `.ado-metrics.yml`) mapping author → expected first-reviewer; the queue
  tags any PR where the buddy was skipped (e.g. India PR that didn't go
  through Costa Rica buddy first).
- **Review load distribution** *(PR queue → Review load + `vamos review-queue --load`)* —
  bar chart of how many active PRs each person is currently a reviewer on; helps
  rebalance assignment fairness.
            """
        )

    st.markdown("---")
    st.caption(
        "Earlier releases: 0.2.0 (suite rename, hygiene agent, pr-review consolidation, "
        "Streamlit UI, light/dark theme, metrics in UI)  ·  "
        "0.1.x (original ado-agent: sod / sync / eod / healthcheck / metrics)."
    )

# ============================================================================
# Overview
# ============================================================================
with tab_overview:
    st.markdown(
        """
### What is vamos?

vamos is HaloMD's agent suite for the data engineering team. **One CLI binary** plus
**one Streamlit UI**, bundling every workflow agent the team uses.

It's three products under one tool:

1. **Personal daily flow** — pulls your assigned ADO tickets into a daily markdown file,
   syncs your edits back to ADO every few hours, posts an EOD summary to Teams or Slack.
2. **Team reporting** — generates metrics, healthcheck, and hygiene reports for project
   leadership, posted to a shared channel on a schedule.
3. **PR review** — reviews Azure DevOps PRs (interactively or as a polling service)
   and posts structured findings as inline comments.
        """
    )

    style.label("Three deployment shapes")
    c1, c2, c3 = st.columns(3)
    for col, name, who, what, env in [
        (c1, "Personal",
         "Each engineer's laptop",
         "vamos daily on cron · vamos sod / sync / eod ad-hoc · vamos pr-review",
         ".env + .env.personal"),
        (c2, "Team service",
         "One always-on host or GitHub Actions",
         "vamos metrics · healthcheck · hygiene · pr-review --watch (cron, service PAT)",
         ".env + .env.team"),
        (c3, "On-demand",
         "Any laptop",
         "Anything ad-hoc · vamos ui for non-techies",
         "Whatever's local"),
    ]:
        with col:
            with st.container(border=True):
                st.markdown(
                    f"<div style='font-weight:700; font-size:1rem; "
                    f"color:var(--text-primary); margin-bottom:0.25rem;'>{name}</div>"
                    f"<div style='color:var(--text-muted); font-size:0.75rem; "
                    f"text-transform:uppercase; letter-spacing:0.05em;'>WHERE</div>"
                    f"<div style='font-size:0.875rem; margin-bottom:0.5rem;'>{who}</div>"
                    f"<div style='color:var(--text-muted); font-size:0.75rem; "
                    f"text-transform:uppercase; letter-spacing:0.05em;'>RUNS</div>"
                    f"<div style='font-size:0.875rem; margin-bottom:0.5rem;'>{what}</div>"
                    f"<div style='color:var(--text-muted); font-size:0.75rem; "
                    f"text-transform:uppercase; letter-spacing:0.05em;'>ENV</div>"
                    f"<div style='font-size:0.875rem;'><code>{env}</code></div>",
                    unsafe_allow_html=True,
                )

    style.label("Quick start")
    st.code(
        """git clone …  &&  cd ado-agent-v2
python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[ui]'         # installs vamos + Streamlit

cp .env.example .env           # fill ADO_PAT, project, etc.
cp .env.personal.example .env.personal   # only on your own laptop
# (or)
cp .env.team.example .env.team           # only on the team service host

vamos test                     # confirms ADO auth
vamos hygiene --skip-post      # try the hygiene report
vamos ui                       # launch this UI on http://localhost:8501""",
        language="bash",
    )

# ============================================================================
# CLI reference
# ============================================================================
with tab_cli:
    st.markdown("### Every command")
    st.markdown(
        "Click the copy icon at the top-right of any code block to copy it. "
        "All commands accept `-v` / `--verbose` and `--profile {personal,team}`."
    )

    sections: list[tuple[str, str, list[tuple[str, str]]]] = [
        (
            "Personal daily flow",
            "Each engineer runs these against their own ADO PAT. Posts as them.",
            [
                ("vamos sod", "Pull today's assigned tickets into work/YYYY-MM-DD.md."),
                ("vamos sod --force", "Overwrite today's markdown."),
                ("vamos sync --dry-run", "Preview what sync would change."),
                ("vamos sync", "Apply edits to ADO (state changes, comments, new tickets)."),
                ("vamos eod", "Generate EOD summary, run final sync, post to Teams/Slack."),
                ("vamos eod --skip-post", "Same, but don't post — just print."),
                ("vamos daily", "Cron-friendly dispatcher: picks sod / sync / eod / nothing based on time + state."),
                ("vamos daily --force sync", "Force a specific phase regardless of schedule."),
            ],
        ),
        (
            "Team reporting",
            "Run on a shared host with a service-account PAT. Posts to the team channel.",
            [
                ("vamos healthcheck", "Per-developer ticket snapshot + team rollup."),
                ("vamos healthcheck --skip-post", "Generate locally; don't deliver."),
                ("vamos metrics generate", "Backlog stats, throughput, aging — HTML by default."),
                ("vamos metrics generate --format markdown", "Markdown output (best for Slack/Teams)."),
                ("vamos metrics preview", "Terminal-only preview of metrics; always read-only."),
                ("vamos metrics boards", "List boards configured in .ado-metrics.yml."),
                ("vamos hygiene", "Run all 7 hygiene rules across every project repo. Read-only by default."),
                ("vamos hygiene --skip-post", "Generate locally; don't post to Teams/Slack."),
                ("vamos hygiene --repo halo-cooling", "Limit to one repo (repeatable for several)."),
                ("vamos hygiene --auto-comment", "Live mode: post nudge comments on offending tickets. Requires HYGIENE_LIVE_MODE=true."),
            ],
        ),
        (
            "PR review",
            "Auto-detects the repo from your cwd's git remote, or accepts --repo, or searches every project repo for a given PR id.",
            [
                ("vamos pr-review", "List active PRs (cwd's repo, or all project repos)."),
                ("vamos pr-review 1234", "Review PR #1234 — repo auto-detected or auto-searched."),
                ("vamos pr-review 1234 --repo dagster-elt", "Skip auto-search, target one repo."),
                ("vamos pr-review 1234 --no-post", "Generate review locally, don't post."),
                ("vamos pr-review --watch", "Service mode: poll every project repo, auto-review new iterations. Cron-friendly."),
            ],
        ),
        (
            "Engineer-focused (new in 0.3)",
            "Quality-of-life commands for the engineer who lives in ADO all day.",
            [
                ("vamos inbox", "What wants your attention: review requests, comments, mentions, new P1/P2."),
                ("vamos inbox --since-hours 24", "Tighter look-back window."),
                ("vamos inbox --json", "Emit JSON for scripting."),
                ("vamos standup", "Auto-draft yesterday/today/blockers."),
                ("vamos capture \"<text>\"", "Quick-add a [NEW] section to today's MD."),
                ("vamos capture \"...\" --customer Vituity --priority 2", "Capture with hints."),
                ("vamos deps 12345", "Show parent/children/blocked-by/related for a ticket."),
            ],
        ),
        (
            "Manager / leadership (new in 0.3)",
            "1:1 prep, retros, risk scans.",
            [
                ("vamos brief \"Victor Wilson\"", "1:1 brief covering last 1 week."),
                ("vamos brief vwilson@halomd.com --weeks 2", "Email also works; 2-week window."),
                ("vamos retro", "Sprint retro starter (default last 2 weeks)."),
                ("vamos retro --iteration \"Data Platform\\\\Sprint 12\"", "Different iteration."),
                ("vamos at-risk", "Past-target / blocked-P1 / aging items + aging PRs."),
                ("vamos at-risk --skip-post", "Generate locally, don't deliver."),
            ],
        ),
        (
            "PR review queue (new in 0.3)",
            "Triaged across all project repos; blocked-on-me first.",
            [
                ("vamos review-queue", "Triaged list across all repos."),
                ("vamos review-queue --repo halo-cooling", "Single-repo focus."),
                ("vamos review-queue --load", "Reviewer load distribution."),
            ],
        ),
        (
            "UI + diagnostics",
            "",
            [
                ("vamos ui", "Launch this Streamlit app on http://localhost:8501."),
                ("vamos ui --port 9000", "Pick a different port."),
                ("vamos test", "Smoke test ADO auth + list a few of your assigned items."),
                ("vamos --help", "List every subcommand."),
                ("vamos hygiene --help", "Per-subcommand options."),
            ],
        ),
    ]

    for header, blurb, cmds in sections:
        with st.container(border=True):
            st.markdown(
                f"<div style='font-weight:700; font-size:1rem; color:var(--text-primary);'>{header}</div>",
                unsafe_allow_html=True,
            )
            if blurb:
                st.markdown(
                    f"<div style='color:var(--text-muted); font-size:0.875rem; "
                    f"margin-bottom:0.75rem;'>{blurb}</div>",
                    unsafe_allow_html=True,
                )
            for cmd, desc in cmds:
                cc, dc = st.columns([2, 3])
                with cc:
                    st.code(cmd, language="bash")
                with dc:
                    st.markdown(
                        f"<div style='padding-top:0.5rem; color:var(--text-secondary); "
                        f"font-size:0.875rem;'>{desc}</div>",
                        unsafe_allow_html=True,
                    )

# ============================================================================
# Configuration
# ============================================================================
with tab_config:
    st.markdown("### .env reference")
    st.markdown(
        "vamos loads `.env` first as a baseline. If `--profile personal` or "
        "`--profile team` is set (or `VAMOS_PROFILE=…` is in the environment), "
        "it overlays `.env.personal` or `.env.team` on top — profile keys win. "
        "All three files live at the repo root and are git-ignored."
    )

    style.label("Required (in .env)")
    st.code(
        """ADO_ORG_URL=https://dev.azure.com/HaloMDLLC
ADO_PROJECT=Data Platform
ADO_PAT=…                       # Work Items R/W (+ Code R/W & PR Threads R/W for pr-review)""",
        language="bash",
    )

    style.label("Personal flow (sod / sync / eod / daily)")
    st.code(
        """ADO_USER_EMAIL=               # blank = @Me; set for read-only testing on a teammate's queue
ADO_READ_ONLY=false
DEVELOPER_NAME="Your Full Name"
CONNECTION_OPTION=Slack         # or Teams
TEAMS_WEBHOOK_URL=…             # used when CONNECTION_OPTION=Teams
SLACK_WEBHOOK_URL=…             # used when CONNECTION_OPTION=Slack
CLAUDE_BIN=claude               # path to Claude Code binary; default "claude" on PATH
WORK_DIR=                       # blank = ./work
STATE_DIR=                      # blank = ./state
SOD_CLEANUP_ENABLED=true        # delete prior days' MD/state on SOD
RUN_SOD_AT=08:00
RUN_EOD_AT=18:00
RUN_SYNC_INTERVAL_MIN=180
RUN_SKIP_WEEKENDS=true""",
        language="bash",
    )

    style.label("Team reporting (healthcheck / metrics / hygiene)")
    st.code(
        """HEALTHCHECK_AREA_PATH=Data Platform\\\\Engineering
HEALTHCHECK_ITERATION_PATH=Data Platform\\\\Ingestion Engineering Kanban

# Metrics defaults (also override per-board via .ado-metrics.yml)
METRICS_AREA_PATH=Data Platform\\\\Engineering
METRICS_ITERATION_PATH=Data Platform\\\\Ingestion Engineering Kanban
METRICS_DRY_RUN=true
METRICS_NOTIFICATIONS_ENABLED=false

# Hygiene
HYGIENE_AREA_PATH=               # blank = falls back to HEALTHCHECK_AREA_PATH
HYGIENE_ITERATION_PATH=
HYGIENE_REPOS=                   # blank = auto-discover ALL repos in project
HYGIENE_LIVE_MODE=false          # flip to true to allow auto-comment posting
HYGIENE_DAILY_COMMENT_DEADLINE=17:00
HYGIENE_STALE_BLOCKED_DAYS=5
HYGIENE_BRANCH_PATTERN=^(feature|bugfix|hotfix)/\\d+-[a-z0-9-]+$""",
        language="bash",
    )

    style.label("PR-review")
    st.code(
        """VAMOS_PR_REVIEW_INTERVAL=300     # seconds between polls in --watch mode""",
        language="bash",
    )

    style.label("Profile selection")
    st.code(
        """VAMOS_PROFILE=                   # blank, "personal", or "team"
                                 # CLI --profile flag overrides this""",
        language="bash",
    )

    st.markdown("---")
    style.label("Where things live")
    st.markdown(
        """
| Path | What |
| --- | --- |
| `.env`, `.env.personal`, `.env.team` | Config (gitignored) |
| `.ado-metrics.yml` | Predefined boards + metrics defaults |
| `prompts/sync.md`, `prompts/eod.md`, `prompts/pr_review/reviewer.md` | LLM prompts |
| `templates/new-ticket.md` | Format for `[NEW]` ticket sections |
| `work/YYYY-MM-DD.md` | Today's daily markdown (the personal flow's source of truth) |
| `state/<agent>/<YYYY-MM-DD>.{json,md}` | Latest run output per agent |
| `state/<agent>/logs/*.json` | Audit trail |
| `metrics_reports/*.html` | Generated metrics |
        """
    )

# ============================================================================
# Hygiene rules
# ============================================================================
with tab_hygiene:
    st.markdown(
        "### Hygiene rule reference\n\n"
        "Each rule maps to one piece of Jeff Jordan's ADO board standards (May 5, 2026). "
        "All seven run on every `vamos hygiene` invocation. Severity informs the "
        "report tile color and the priority order in the per-engineer breakdown."
    )

    rules = [
        ("state-discipline", "should-fix",
         "Two states only (Active + Blocked). One Active per engineer. "
         "Tickets in deprecated states (QA, PR Ready) flagged. Code Review state "
         "is automated by ADO when a PR is submitted."),
        ("daily-comments", "blocker",
         "Active or Blocked tickets need a comment from the assignee on the "
         "current working day, before HYGIENE_DAILY_COMMENT_DEADLINE (default 17:00 local). "
         "Dan tracks this every day."),
        ("required-fields", "should-fix",
         "Every story needs: assignee, story points (1 SP = 1 hour), start date, target date. "
         "Start/target dates only required once the ticket leaves the Groomed/Ready state."),
        ("pr-linkage", "blocker",
         "Every active PR must link to at least one ADO work item. Closed stories "
         "with no PR and no linked Code Review ticket also flagged (should-fix)."),
        ("branch-naming", "nit",
         "PR source branches must match HYGIENE_BRANCH_PATTERN — by default "
         "`feature|bugfix|hotfix / <ticket> - <slug>`. Lowercase + hyphens only."),
        ("resolution-on-close", "should-fix",
         "Closed tickets need a resolution note (Notes / Custom.Notes / "
         "Microsoft.VSTS.Common.Resolution / System.Reason). Generic auto-set values "
         "like 'Done' or 'Completed' don't count."),
        ("stale-blocked", "should-fix",
         "Tickets in Blocked state for more than HYGIENE_STALE_BLOCKED_DAYS days "
         "(default 5) with no recent comments. Either chase the unblock, escalate, or close."),
    ]

    for rule_id, severity, body in rules:
        tone = {"blocker": "red", "should-fix": "amber", "nit": "indigo"}.get(severity, "slate")
        with st.container(border=True):
            st.markdown(
                f"<div style='display:flex; justify-content:space-between; align-items:center; "
                f"margin-bottom:0.5rem;'>"
                f"<div style='font-family:JetBrains Mono,monospace; font-weight:600; "
                f"font-size:0.9375rem; color:var(--text-primary);'>{rule_id}</div>"
                f"<div>{style.pill(severity.upper(), tone)}</div></div>"
                f"<div style='color:var(--text-secondary); font-size:0.875rem; "
                f"line-height:1.5;'>{body}</div>",
                unsafe_allow_html=True,
            )

    st.markdown("---")
    style.label("Adding a new rule")
    st.markdown(
        """
Drop a file in `vamos/hygiene/rules/` exporting `RULE_ID` and `check(snapshot, cfg) -> list[Finding]`,
then register it in `vamos/hygiene/rules/__init__.py`. The `TeamSnapshot`
(`vamos.core.snapshot`) loads the team's work items, comments on Active/Blocked
tickets, and PRs from configured repos in one round-trip — don't re-query ADO
from inside a rule.
        """
    )

# ============================================================================
# Operations
# ============================================================================
with tab_ops:
    style.label("State directories")
    st.markdown(
        """
Each agent writes to its own subdirectory under `state/`:

| Agent | Files |
| --- | --- |
| `daily` | `state/<YYYY-MM-DD>-run.json` — dispatcher decision history |
| `sync` | `state/<YYYY-MM-DD>.json` — comment-hash dedup; `state/logs/<...>.json` audit trail |
| `hygiene` | `state/hygiene/<YYYY-MM-DD>.json` and `.md`; `posted-hashes.txt` for live-mode dedup |
| `pr-review` | `state/pr-review/iterations.json` — last reviewed iteration per (repo, pr); `state/pr-review/logs/*.json` audit trail |
        """
    )

    style.label("Posting flow (Teams + Slack)")
    st.markdown(
        """
Both Teams and Slack go through `vamos.core.delivery`. The active channel is
controlled by `CONNECTION_OPTION` in `.env`. Webhook URLs are in `TEAMS_WEBHOOK_URL` /
`SLACK_WEBHOOK_URL`. The team profile typically points at a shared channel; the
personal profile points at the engineer's DM.

For Teams, vamos auto-detects Workflows webhooks (`*.logic.azure.com`) vs the
deprecated legacy connector (`*.webhook.office.com`) and sends the right payload
schema. Teams "deep-link" URLs (`teams.cloud.microsoft/l/chat/...`) are NOT webhooks
and will fail.
        """
    )

    style.label("Cron / scheduler examples")
    st.markdown("**macOS / Linux (cron):**")
    st.code(
        """# Personal daily flow — every 30 min on weekdays
*/30 * * * 1-5 cd /path/to/ado-agent-v2 && /path/to/.venv/bin/vamos daily >> logs/daily.log 2>&1

# Team service — hygiene at 5pm CST weekdays
0 17 * * 1-5 cd /path/to/ado-agent-v2 && /path/to/.venv/bin/vamos --profile team hygiene >> logs/hygiene.log 2>&1

# Team service — metrics every Monday 9am
0 9 * * 1 cd /path/to/ado-agent-v2 && /path/to/.venv/bin/vamos --profile team metrics generate --format html >> logs/metrics.log 2>&1

# PR-review service — runs continuously (use systemd / launchd, not cron)
# (see "Service mode" below)""",
        language="bash",
    )

    st.markdown("**Windows (PowerShell):**")
    st.code(
        """$AdoAgent = "C:\\path\\to\\ado-agent-v2"
$Python   = "$AdoAgent\\.venv\\Scripts\\python.exe"
$action  = New-ScheduledTaskAction -Execute $Python -Argument "$AdoAgent\\cli.py daily" -WorkingDirectory $AdoAgent
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).Date.AddHours(7) `
            -RepetitionInterval (New-TimeSpan -Minutes 30) `
            -RepetitionDuration (New-TimeSpan -Hours 13)
Register-ScheduledTask -TaskName "vamos-daily" -Action $action -Trigger $trigger -RunLevel Highest""",
        language="powershell",
    )

    style.label("Service mode (pr-review --watch)")
    st.markdown(
        """
For continuous PR review, run `vamos pr-review --watch` under a process supervisor:

- **systemd** (Linux): drop a unit at `/etc/systemd/system/vamos-pr-review.service` with
  `ExecStart=/path/.venv/bin/vamos --profile team pr-review --watch`.
- **launchd** (macOS): a `LaunchDaemon` plist with `KeepAlive=true`.
- **GitHub Actions**: a workflow with `on: schedule` invoking `--watch` is
  awkward (Actions kills long-running jobs); prefer a shorter loop interval and
  a `cron` schedule, or use a self-hosted runner.

The watcher sleeps `VAMOS_PR_REVIEW_INTERVAL` seconds between polls (default 300).
Reviewed iterations are persisted to `state/pr-review/iterations.json`, so a
restart resumes without re-reviewing.
        """
    )

    style.label("Safety / read-only mode")
    st.markdown(
        """
Set `ADO_READ_ONLY=true` to forbid all writes (PATCH/POST). Useful for first-day
testing of any agent. Hygiene and pr-review have additional gates:

- `HYGIENE_LIVE_MODE=true` is required before `--auto-comment` will post anything to ADO.
- `vamos pr-review --no-post` runs the review but skips comment posting.
- `vamos pr-review --watch` always posts; turn it off by stopping the service.
        """
    )

    style.label("Credentials")
    st.markdown(
        """
Each developer uses their own ADO Personal Access Token, scoped to:

- **Work Items (Read, write, & manage)** — required for sod / sync / eod / healthcheck / hygiene / metrics
- **Code (Read & write)** + **Pull Request Threads (Read & write)** — required for pr-review

Generate one at `https://dev.azure.com/<org>/_usersSettings/tokens`.
Service-account PATs (for the team profile) need the same scopes.

`.env`, `.env.personal`, and `.env.team` are git-ignored. Never commit them.
        """
    )
