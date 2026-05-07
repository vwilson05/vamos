"""Help — CLI reference, env vars, hygiene rules, what's new."""
from __future__ import annotations

from nicegui import ui

from .. import theme


@ui.page("/help")
def help_page():
    theme.render_shell(active_route="/help")

    with ui.column().classes("p-6 max-w-5xl mx-auto w-full gap-4"):
        theme.section_header(
            "Help & reference",
            subtitle="What vamos is, how to run each agent, and how to configure deployment.",
        )

        with ui.tabs().classes("w-full") as tabs:
            tab_whatsnew = ui.tab("What's new", icon="campaign")
            tab_overview = ui.tab("Overview", icon="info")
            tab_cli = ui.tab("CLI reference", icon="terminal")
            tab_mcp = ui.tab("Claude (MCP)", icon="rocket_launch")
            tab_config = ui.tab("Configuration", icon="settings")
            tab_hygiene = ui.tab("Hygiene rules", icon="cleaning_services")
            tab_ops = ui.tab("Operations", icon="construction")

        with ui.tab_panels(tabs, value=tab_whatsnew).classes("w-full"):
            with ui.tab_panel(tab_whatsnew):
                _render_whatsnew()
            with ui.tab_panel(tab_overview):
                _render_overview()
            with ui.tab_panel(tab_cli):
                _render_cli_reference()
            with ui.tab_panel(tab_mcp):
                _render_mcp()
            with ui.tab_panel(tab_config):
                _render_config()
            with ui.tab_panel(tab_hygiene):
                _render_hygiene_rules()
            with ui.tab_panel(tab_ops):
                _render_ops()


def _render_whatsnew():
    ui.label("vamos 0.7.0").classes("text-xl font-bold text-slate-900 dark:text-slate-50")
    ui.label("Released 2026-05-06  ·  Full persona coverage in MCP (25 tools).").classes(
        "text-xs text-slate-500 dark:text-slate-400"
    )

    with ui.card().classes("w-full p-5 mt-2 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700"):
        ui.markdown("""
#### 0.7.0 — Full persona coverage in MCP

The MCP server now mirrors the entire vamos CLI surface — 25 tools across
4 personas. Claude can drive vamos exactly the way an engineer, reviewer,
manager, or leader would type CLI commands.

- **Engineer flow orchestrators** (8 new): `run_sod`, `run_sync`, `run_eod`,
  `run_prep`, `capture_ticket`, `get_inbox`, `get_standup`, `get_dependencies`.
  *"Claude, generate my EOD and post to Teams"* now works end-to-end.
- **Reviewer** (3 new): `get_review_queue`, `get_review_load`, `vote_on_pr`.
  *"Run review on PR 1234"* → read findings → *"approve it"* → done, all
  without leaving Claude Code.
- **Manager** (3 new): `list_engineer_tickets`, `get_engineer_brief`, `get_retro`.
- **Leadership** (4 new): `get_at_risk`, `get_team_hygiene`,
  `get_team_healthcheck`, `run_metrics`.

Leadership tools always run side-effect-free — they never post to Teams/Slack
from MCP. Use the CLI explicitly when you want to deliver a report.

Restart your MCP connection (or run `claude mcp restart vamos`) to pick up
the new tools.
        """).classes("prose dark:prose-invert max-w-none text-sm")

    with ui.card().classes("w-full p-5 mt-2 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700"):
        ui.markdown("""
#### 0.6.0 — vamos as an MCP server for Claude

vamos now exposes its core actions as an MCP server. Claude Desktop and
Claude Code can drive your entire ticket-to-close flow: pick up a ticket,
plan, code, open a PR, run review, verify hygiene, and close cleanly.

- **8 tools**: `get_ticket`, `list_my_tickets`, `start_work`, `post_comment`,
  `open_pr`, `run_pr_review`, `run_hygiene_check`, `close_ticket`.
- **Stateless with workflow hints** — every response carries a `next_actions`
  field derived live from ADO, so Claude doesn't have to track where it is
  in the flow.
- **Safety rails** — read-only and low-stakes writes auto-execute;
  `close_ticket` and `run_pr_review --post` require an explicit `confirm=True`
  so Claude can't accidentally mutate state.
- **Audit trail** — every tool call appends to `state/trail/<ticket>.jsonl`
  with actor + tool + result, so you can see who did what (Claude, the CLI,
  or a human in the UI).

Install in 30 seconds:

```bash
pip install -e '.[mcp]'
claude mcp add vamos -- vamos mcp     # Claude Code
vamos mcp install                     # Claude Desktop snippet
```

See the **Claude (MCP)** tab for the full reference.
        """).classes("prose dark:prose-invert max-w-none text-sm")

    with ui.card().classes("w-full p-5 mt-2 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700"):
        ui.markdown("""
#### 0.5.0 — UI migrated from Streamlit to NiceGUI

- **Reactive UI** — clicking buttons no longer re-runs the whole page. State is held in regular Python variables / `app.storage.user` instead of session state plumbing.
- **Native dark mode** via Quasar; toggle in the header. No more chasing widget contrast bugs.
- **Real streaming logs** — every long-running operation pipes log lines to a `ui.log` element as they happen, no thread-queue hacks.
- **Inline Clean dialog** for hygiene findings: click Clean → modal opens → proposal builds in real time → Apply or Skip.
- **Tailwind / Quasar classes** for styling. Cards, pills, KPIs are first-class components.
- **Sidebar navigation** — header + drawer with active-route highlighting. Single-page-app feel.

The CLI is unchanged. All agents (`sod`, `sync`, `eod`, `daily`, `prep`, `metrics`, `healthcheck`, `hygiene`, `at-risk`, `pr-review`, `inbox`, `standup`, `capture`, `brief`, `retro`, `deps`, `review-queue`, `cron-install/uninstall/list`, `ui`) are unchanged.
        """).classes("prose dark:prose-invert max-w-none text-sm")

    ui.label("Earlier releases").classes(
        "text-xs uppercase tracking-wider text-slate-500 dark:text-slate-400 mt-4"
    )
    ui.markdown("""
- **0.4.2** — Windows feature parity: Task Scheduler integration, `launch.ps1` mirror, `launch.bat` for double-click.
- **0.4.1** — `vamos prep` (one-shot SOD + inbox + standup), auto-prep on launch, "Today's prep" section on My day.
- **0.4.0** — `launch.sh` / `launch.command`, `crons.yml`, Settings page, hygiene `--clean` (AI-assisted finding fixes).
- **0.3.x** — board picker, log streaming, identity normalization, Windows scheduled tasks.
- **0.3.0** — 16 features across 4 personas: inbox, standup, capture, deps, brief, retro, at-risk, customer view, trends, blocked-on-me, buddy routing.
- **0.2.0** — suite rename, hygiene agent, pr-review consolidation, Streamlit UI.
- **0.1.x** — original ado-agent: sod / sync / eod / healthcheck / metrics.
    """).classes("prose dark:prose-invert max-w-none text-sm")


def _render_overview():
    ui.markdown("""
### What is vamos?

vamos is HaloMD's agent suite for the data engineering team. **One CLI binary** plus
**one NiceGUI app**, bundling every workflow agent the team uses.

It's three products under one tool:

1. **Personal daily flow** — pulls your assigned ADO tickets into a daily markdown file,
   syncs your edits back to ADO every few hours, posts an EOD summary to Teams or Slack.
2. **Team reporting** — generates metrics, healthcheck, and hygiene reports for project
   leadership, posted to a shared channel on a schedule.
3. **PR review** — reviews Azure DevOps PRs (interactively or as a polling service)
   and posts structured findings as inline comments.
    """).classes("prose dark:prose-invert max-w-none")

    ui.label("Three deployment shapes").classes(
        "text-xs uppercase tracking-wider text-slate-500 mt-4 mb-2"
    )

    with ui.row().classes("w-full gap-3 flex-wrap"):
        for name, who, what in [
            ("Personal", "Each engineer's laptop",
             "vamos daily on cron · vamos sod / sync / eod ad-hoc · vamos pr-review"),
            ("Team service", "One always-on host or GitHub Actions",
             "vamos metrics · healthcheck · hygiene · pr-review --watch"),
            ("On-demand", "Any laptop",
             "Anything ad-hoc · vamos ui for non-techies"),
        ]:
            with ui.card().classes(
                "flex-1 min-w-64 p-4 rounded-xl border border-slate-200 dark:border-slate-700 "
                "bg-white dark:bg-slate-800"
            ):
                ui.label(name).classes("font-bold text-base text-slate-900 dark:text-slate-50")
                theme.small_label("Where")
                ui.label(who).classes("text-sm text-slate-700 dark:text-slate-300 mb-2")
                theme.small_label("Runs")
                ui.label(what).classes("text-sm text-slate-700 dark:text-slate-300")


def _render_cli_reference():
    sections = [
        ("Personal flow", [
            ("vamos sod", "Pull today's assigned tickets into work/YYYY-MM-DD.md."),
            ("vamos sync --dry-run", "Preview what sync would change."),
            ("vamos sync", "Apply edits to ADO."),
            ("vamos eod", "Generate EOD summary, run final sync, post to Teams/Slack."),
            ("vamos daily", "Cron-friendly dispatcher: picks sod / sync / eod by time."),
            ("vamos prep", "One-shot: SOD + inbox + standup, all cached for instant UI load."),
        ]),
        ("Team reporting", [
            ("vamos healthcheck", "Per-developer ticket snapshot + team rollup."),
            ("vamos metrics generate", "HTML/markdown/JSON metrics report."),
            ("vamos hygiene", "Run all 7 hygiene rules across project repos. Read-only by default."),
            ("vamos hygiene --clean", "Walk findings, propose fixes, apply on confirm."),
            ("vamos hygiene --clean --apply", "Auto-apply (gated by HYGIENE_LIVE_MODE=true)."),
            ("vamos at-risk", "Past-target / blocked P1s / aging items."),
        ]),
        ("Engineer tools", [
            ("vamos inbox", "Aggregated review-requests / comments / mentions / new P1s."),
            ("vamos standup", "Auto-draft yesterday/today/blockers."),
            ("vamos capture \"text\"", "Quick-add a [NEW] section to today's MD."),
            ("vamos deps 1234", "Show parent/children/blocked-by/related links."),
        ]),
        ("Manager tools", [
            ("vamos brief \"Engineer Name\"", "1:1 brief covering the last week."),
            ("vamos retro", "Sprint retro starter (last 2 weeks)."),
        ]),
        ("PR review", [
            ("vamos pr-review", "List active PRs across all repos."),
            ("vamos pr-review 1234", "Review specific PR — auto-detects repo."),
            ("vamos pr-review --watch", "Service mode: poll + auto-review new iterations."),
            ("vamos review-queue", "Triaged queue, blocked-on-me first."),
        ]),
        ("Claude (MCP)", [
            ("vamos mcp", "Run the stdio MCP server (Claude calls this)."),
            ("vamos mcp install", "Print copy-paste install instructions."),
            ("vamos mcp print-config", "Emit JSON for claude_desktop_config.json."),
        ]),
        ("Setup", [
            ("./launch.sh", "Mac/Linux: ensure venv → install deps → launch UI."),
            (".\\launch.ps1", "Windows: same."),
            ("./launch.sh --install-crons", "Install vamos cron entries."),
            ("vamos cron-list", "Show configured + currently-installed scheduled tasks."),
            ("vamos --board all hygiene", "Override board scope at runtime."),
            ("vamos ui", "Launch this NiceGUI app on http://localhost:8501."),
        ]),
    ]
    for title, cmds in sections:
        ui.label(title).classes(
            "font-bold text-base text-slate-900 dark:text-slate-50 mt-4"
        )
        with ui.card().classes(
            "w-full p-3 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800"
        ):
            for cmd, desc in cmds:
                with ui.row().classes("py-1 w-full items-center border-b border-slate-100 dark:border-slate-700 last:border-b-0"):
                    ui.code(cmd).classes("font-mono text-xs w-1/2 truncate")
                    ui.label(desc).classes(
                        "text-sm text-slate-700 dark:text-slate-300 flex-1"
                    )


def _render_mcp():
    ui.markdown("""
### Claude integration (MCP)

vamos ships a stdio MCP server so **Claude Desktop** and **Claude Code** can
drive your ADO work directly. After installing, you can ask Claude things like
*"work ticket 28855"* and it will fetch the ticket, plan the work, open a PR,
run review, verify hygiene, and close cleanly — pausing for you whenever
human judgment is needed.

#### Install

```bash
pip install -e '.[mcp]'

# Claude Code (recommended):
claude mcp add vamos -- vamos mcp

# Claude Desktop: print the config snippet to paste:
vamos mcp install
```

Restart Claude. Try: *"use vamos to fetch ticket 12345"*.

#### How it works

- **Stateless tools, computed hints.** Every response carries a `next_actions`
  field derived live from ADO state + linked PRs + recent trail. Claude
  doesn't need to remember where it is — each call tells it.
- **Safety rails.** Read-only and low-stakes writes auto-execute. Mutations
  with real blast radius (`close_ticket`, posting PR review comments)
  return a dry-run preview unless `confirm=True`.
- **Audit trail.** Every tool call appends to `state/trail/<ticket>.jsonl`
  with `actor + tool + args + result`. You can tell which actions came from
  Claude vs. the CLI vs. a human.
- **Per-engineer install** over stdio. No shared service, no auth shenanigans
  — Claude inherits whatever PAT is in your `.env`.
    """).classes("prose dark:prose-invert max-w-none")

    persona_groups = [
        ("Engineer (atomic)", [
            ("get_ticket(id)", "read-only",
             "Title, state, AC, branch suggestion, recent comments, linked PRs, next_actions."),
            ("list_my_tickets(include_closed=False)", "read-only",
             "Active tickets assigned to you, each with a state-aware next-action hint."),
            ("start_work(id, comment=None)", "auto",
             "Move ticket to Active and post a starting daily-standup comment."),
            ("post_comment(id, text)", "auto",
             "Post a daily progress note (satisfies the daily-comments rule)."),
            ("open_pr(id, repo, branch, title, ...)", "auto",
             "Create a PR via the ADO API and link the work item."),
            ("run_pr_review(pr_id, repo, post=False, confirm=False)", "preview",
             "Run the automated reviewer; pass post=True + confirm=True to publish."),
            ("vote_on_pr(pr_id, repo, vote, confirm=False)", "confirm",
             "Cast a PR vote (approve / approve-with-suggestions / wait-for-author / reject)."),
            ("share_success_story(action, summary, ticket_id?, pr_id?, repo?)", "auto",
             "Post a shout-out to the share channel (halo-nation) — manual ad-hoc moments."),
            ("run_hygiene_check(id)", "read-only",
             "Run all 7 board-standards rules against one ticket."),
            ("close_ticket(id, resolution, ..., confirm=False)", "confirm",
             "Resolve/close with a reason. Preview unless confirm=True."),
        ]),
        ("Engineer (flow orchestrators)", [
            ("run_sod(force=False)", "auto",
             "Pull today's tickets into work/YYYY-MM-DD.md."),
            ("run_sync(dry_run=False)", "auto",
             "Apply markdown edits to ADO via claude -p (LLM, ~30-90s)."),
            ("run_eod(...)", "auto",
             "Generate EOD, run final sync, post to Teams/Slack (LLM, ~30-60s)."),
            ("run_prep(...)", "auto",
             "One-shot: SOD + inbox + standup, all cached for the UI."),
            ("capture_ticket(text, customer?, priority?)", "auto",
             "Append [NEW] to today's MD."),
            ("get_inbox(since_hours=48)", "read-only",
             "Review requests / mentions / new P1s."),
            ("get_standup()", "read-only",
             "Yesterday/today/blockers brief."),
            ("get_dependencies(ticket_id)", "read-only",
             "Parent / children / blocked-by / related."),
        ]),
        ("Reviewer", [
            ("get_review_queue(repo?)", "read-only",
             "Triaged queue, blocked-on-me first, with buddy-routing flags."),
            ("get_review_load()", "read-only",
             "PR review distribution across all reviewers."),
        ]),
        ("Manager", [
            ("list_engineer_tickets(engineer, include_closed=False)", "read-only",
             "What's on someone's plate."),
            ("get_engineer_brief(engineer, weeks=1)", "auto",
             "1:1 brief markdown (LLM, ~30-60s)."),
            ("get_retro(iteration?, weeks=2)", "auto",
             "Sprint retro starter (LLM, ~30-60s)."),
        ]),
        ("Leadership", [
            ("get_at_risk()", "read-only",
             "Past-target / blocked P1s / aging items + aging PRs."),
            ("get_team_hygiene()", "read-only",
             "Full-board hygiene rollup (vs. single-ticket run_hygiene_check)."),
            ("get_team_healthcheck()", "read-only",
             "Per-engineer team-wide ticket snapshot."),
            ("run_metrics(format='markdown')", "auto",
             "Backlog / throughput / cycle time report."),
        ]),
    ]

    safety_color = {
        "read-only": "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400",
        "auto": "bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-300",
        "preview": "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300",
        "confirm": "bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-400",
    }
    for persona, tools in persona_groups:
        ui.label(persona).classes(
            "text-xs uppercase tracking-wider text-slate-500 dark:text-slate-400 mt-4 mb-2 font-semibold"
        )
        with ui.column().classes("w-full gap-2"):
            for sig, safety, desc in tools:
                with ui.card().classes(
                    "w-full p-3 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700"
                ):
                    with ui.row().classes("items-start gap-3"):
                        ui.code(sig).classes("text-xs flex-1")
                        ui.label(safety).classes(
                            f"text-xs px-2 py-0.5 rounded-full font-semibold {safety_color[safety]}"
                        )
                    ui.label(desc).classes(
                        "text-sm text-slate-700 dark:text-slate-300 mt-2"
                    )


def _render_config():
    ui.markdown("""
### .env reference

vamos loads `.env` first as a baseline. If `--profile personal` or `--profile team` is set
(or `VAMOS_PROFILE=…` is in the environment), it overlays `.env.personal` or `.env.team`
on top — profile keys win. All three files live at the repo root and are git-ignored.
    """).classes("prose dark:prose-invert max-w-none")

    blocks = [
        ("Required (in .env)", """ADO_ORG_URL=https://dev.azure.com/HaloMDLLC
ADO_PROJECT=Data Platform
ADO_PAT=…"""),
        ("Personal flow", """ADO_USER_EMAIL=
ADO_READ_ONLY=false
DEVELOPER_NAME="Your Name"
CONNECTION_OPTION=Slack
TEAMS_WEBHOOK_URL=
SLACK_WEBHOOK_URL=
RUN_SOD_AT=08:00
RUN_EOD_AT=18:00
RUN_SYNC_INTERVAL_MIN=180
VAMOS_AUTO_PREP=false"""),
        ("Team agents", """HEALTHCHECK_AREA_PATH=Data Platform\\\\Engineering
HYGIENE_REPOS=
HYGIENE_LIVE_MODE=false
HYGIENE_DAILY_COMMENT_DEADLINE=17:00
HYGIENE_STALE_BLOCKED_DAYS=5"""),
    ]
    for title, code in blocks:
        ui.label(title).classes(
            "text-xs uppercase tracking-wider text-slate-500 mt-3"
        )
        ui.code(code, language="bash").classes("w-full")


def _render_hygiene_rules():
    rules = [
        ("state-discipline", "should-fix",
         "Two states only (Active + Blocked). One Active per engineer. "
         "Tickets in deprecated states (QA, PR Ready) flagged."),
        ("daily-comments", "blocker",
         "Active or Blocked tickets need a comment from the assignee on the current "
         "working day, before HYGIENE_DAILY_COMMENT_DEADLINE (default 17:00 local)."),
        ("required-fields", "should-fix",
         "Every story needs: assignee, story points (1 SP = 1 hour), start date, target date."),
        ("pr-linkage", "blocker",
         "Every active PR must link to at least one ADO work item."),
        ("branch-naming", "nit",
         "PR source branches must match `feature|bugfix|hotfix / <ticket> - <slug>`."),
        ("resolution-on-close", "should-fix",
         "Closed tickets need a resolution note in Notes / Resolution / System.Reason."),
        ("stale-blocked", "should-fix",
         "Tickets in Blocked state for more than HYGIENE_STALE_BLOCKED_DAYS (default 5)."),
    ]
    SEV_TONES = {"blocker": "red", "should-fix": "amber", "nit": "indigo"}
    for rule_id, severity, body in rules:
        with ui.card().classes(
            "w-full p-3 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 my-1"
        ):
            with ui.row().classes("items-center justify-between mb-2"):
                ui.label(rule_id).classes(
                    "font-mono font-semibold text-sm text-slate-900 dark:text-slate-100"
                )
                theme.pill(severity.upper(), SEV_TONES.get(severity, "slate"))
            ui.label(body).classes("text-sm text-slate-700 dark:text-slate-300")


def _render_ops():
    ui.markdown("""
### State directories

| Agent | Files |
|---|---|
| `daily` | `state/<date>-run.json` |
| `sync` | `state/<date>.json` + `state/logs/*.json` |
| `hygiene` | `state/hygiene/<date>.json,md` |
| `pr-review` | `state/pr-review/iterations.json` + `state/pr-review/logs/*.json` |
| `inbox` / `standup` / `at-risk` | `state/<agent>/<date>.json` |

### Cron / Task Scheduler

`vamos cron-install` reads `crons.yml` and installs scheduled tasks. On Mac/Linux, writes a marker-bracketed block to your crontab. On Windows, dispatches to `schtasks.exe`.

### Service mode

`vamos pr-review --watch` polls every project repo for new PR iterations and auto-reviews. Run under systemd / launchd / a long-running scheduled task.

### Safety

- `ADO_READ_ONLY=true` blocks all writes.
- `HYGIENE_LIVE_MODE=true` is required for `hygiene --auto-comment` or `--clean --apply`.
- `vamos pr-review --no-post` runs review without posting.
    """).classes("prose dark:prose-invert max-w-none text-sm")
