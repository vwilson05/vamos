"""vamos — HaloMD agent suite. `vamos <command>` or `python cli.py <command>`."""
from __future__ import annotations

import argparse
import logging
import sys
import io
from datetime import date

# Fix Unicode encoding issues on Windows
if sys.platform == "win32":
    # Set UTF-8 encoding for stdout and stderr
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from . import config as config_mod
from . import sod, sync, eod, scheduler, healthcheck
from .ado import ADOClient
from . import metrics_cli
from . import hygiene as hygiene_mod
from . import pr_review as pr_review_mod
from . import inbox as inbox_mod
from . import standup as standup_mod
from . import capture as capture_mod
from . import brief as brief_mod
from . import retro as retro_mod
from . import at_risk as at_risk_mod
from . import deps as deps_mod
from . import reminders as reminders_mod
from .pr_review import queue as pr_queue_mod
from .core import boards as boards_mod
from . import cron_install as cron_install_mod
from . import prep as prep_mod


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="vamos",
        description="vamos — HaloMD agent suite (personal daily flow + team reporting + PR review)",
    )
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--day", help="Override day (YYYY-MM-DD), defaults to today")
    parser.add_argument(
        "--profile",
        choices=["personal", "team"],
        default=None,
        help="Credential profile to load (personal=your PAT/channels; team=service account/shared channels). "
             "Defaults to VAMOS_PROFILE env var, then 'personal'.",
    )
    parser.add_argument(
        "--board",
        default=None,
        help="Limit team agents to one board from .ado-metrics.yml (or 'all' to span every board). "
             "When set, overrides HEALTHCHECK_AREA_PATH / HYGIENE_AREA_PATH for this run. "
             f"Available: {', '.join(boards_mod.board_names()) or '(none configured)'}",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # --- Personal daily flow ---
    p_sod = sub.add_parser("sod", help="Start of day: pull assigned items into today's markdown")
    p_sod.add_argument("--force", action="store_true",
                       help="Overwrite today's markdown if it exists")

    p_sync = sub.add_parser("sync", help="Sync today's markdown to ADO via claude -p")
    p_sync.add_argument("--dry-run", action="store_true",
                        help="Generate the action plan but do not execute")

    p_eod = sub.add_parser("eod", help="Final sync + post EOD to Teams and Slack")
    p_eod.add_argument("--dry-run", action="store_true",
                       help="Generate the EOD text but do not post")
    p_eod.add_argument("--skip-sync", action="store_true",
                       help="Skip the final sync, just generate the EOD text")
    p_eod.add_argument("--skip-post", action="store_true",
                       help="Generate and save the EOD text but do not post to Teams")
    p_eod.add_argument("--skip-slack", action="store_true",
                       help="Generate and save the EOD text but do not post to Slack")

    p_daily = sub.add_parser(
        "daily",
        help="Personal daily-loop dispatcher: decides sod/sync/eod based on time and state. "
             "Schedule this every 30 min on weekdays.",
    )
    p_daily.add_argument("--force", choices=["sod", "sync", "eod"],
                         help="Force the given command regardless of schedule/state")

    # --- Team reporting ---
    p_healthcheck = sub.add_parser("healthcheck",
                                  help="Team healthcheck: ticket summaries for all developers")
    p_healthcheck.add_argument("--skip-post", action="store_true",
                              help="Generate the healthcheck report but do not post to Teams/Slack")

    p_hygiene = sub.add_parser(
        "hygiene",
        help="Team hygiene: enforce ADO board standards (state discipline, daily comments, PR linkage, etc.)",
    )
    p_hygiene.add_argument("--skip-post", action="store_true",
                           help="Generate the hygiene report but do not post to Teams/Slack")
    p_hygiene.add_argument("--auto-comment", action="store_true",
                           help="Post nudge comments on offending tickets (requires HYGIENE_LIVE_MODE=true)")
    p_hygiene.add_argument("--repo", action="append", default=None, metavar="REPO",
                           help="Limit hygiene to specific repo(s). Repeat for multiple. "
                                "If omitted: uses HYGIENE_REPOS from config; if also empty, "
                                "auto-discovers all repos in the project.")
    p_hygiene.add_argument("--clean", action="store_true",
                           help="Walk findings, propose AI-generated fixes, prompt y/n per item. "
                                "Asks Claude to suggest concrete actions (comment text, state changes, "
                                "field values). See vamos/hygiene/cleaners/.")
    p_hygiene.add_argument("--apply", action="store_true",
                           help="Auto-apply proposed fixes during --clean (no prompt). "
                                "Requires HYGIENE_LIVE_MODE=true in .env.")
    p_hygiene.add_argument("--clean-rule", action="append", default=None, metavar="RULE_ID",
                           help="Limit --clean to specific rule ids (repeat for multiple). "
                                "Available: state-discipline, daily-comments, required-fields, "
                                "resolution-on-close, stale-blocked.")

    # --- PR review ---
    p_pr = sub.add_parser(
        "pr-review",
        help="Review an Azure DevOps pull request and (optionally) post comments back",
    )
    p_pr.add_argument("pr_id", nargs="?", type=int, help="PR id (omit to interactively pick from active PRs)")
    p_pr.add_argument("--repo", help="Repo name (auto-detected from git remote if omitted)")
    p_pr.add_argument("--watch", action="store_true",
                      help="Service mode: poll for new PR iterations and auto-review")
    p_pr.add_argument("--interactive", action="store_true",
                      help="Prompt before posting (default in TTY)")
    p_pr.add_argument("--no-post", action="store_true",
                      help="Generate the review but do not post comments")

    # --- Engineer-focused agents ---
    p_inbox = sub.add_parser(
        "inbox",
        help="Aggregate everything that wants your attention "
             "(review requests, comments, mentions, new P1/P2 assignments)",
    )
    p_inbox.add_argument("--since-hours", type=int, default=48,
                         help="Look-back window (default 48 hours)")
    p_inbox.add_argument("--json", action="store_true",
                         help="Emit JSON instead of plain text")

    p_standup = sub.add_parser("standup",
                               help="Auto-draft a yesterday/today/blockers brief")

    p_capture = sub.add_parser(
        "capture",
        help="Append a [NEW] section to today's daily markdown — quick-capture from anywhere",
    )
    p_capture.add_argument("text", help="What to capture (first line is the title)")
    p_capture.add_argument("--customer", help="Customer prefix (Vituity, UHC, …)")
    p_capture.add_argument("--priority", type=int, choices=[1, 2, 3, 4],
                           help="Priority hint")

    p_deps = sub.add_parser("deps",
                            help="Show parent/child/blocked-by/related links for a ticket")
    p_deps.add_argument("ticket_id", type=int)

    # --- Manager / leadership agents ---
    p_brief = sub.add_parser("brief",
                             help="Per-engineer summary for 1:1s")
    p_brief.add_argument("engineer", help="Display name or email of the engineer")
    p_brief.add_argument("--weeks", type=int, default=1,
                         help="Look-back window in weeks (default 1)")

    p_retro = sub.add_parser("retro",
                             help="Sprint retro starter (shipped / missed / themes / customers)")
    p_retro.add_argument("--iteration",
                         help="Override iteration path (defaults to HYGIENE_ITERATION_PATH)")
    p_retro.add_argument("--weeks", type=int, default=2,
                         help="Look-back window in weeks (default 2)")

    p_at_risk = sub.add_parser("at-risk",
                               help="Tickets and PRs that need leadership attention "
                                    "(past target date, blocked P1s, aging items)")
    p_at_risk.add_argument("--skip-post", action="store_true",
                           help="Generate the at-risk report but do not post to Teams/Slack")

    p_reminders = sub.add_parser(
        "reminders",
        help="Advisory board-wide reminders + recommendations "
             "(workbook-sent close-outs, unpicked P1s, merged-but-open tickets, etc.). "
             "Generates a preview and prompts before sending.",
    )
    p_reminders.add_argument("--skip-post", action="store_true",
                             help="Generate the report only — never prompt, never post.")
    p_reminders.add_argument("--send", action="store_true",
                             help="Send to channel without an interactive prompt (for cron).")
    p_reminders.add_argument("--channel", choices=["Slack", "Teams"], default=None,
                             help="Override delivery channel (defaults to CONNECTION_OPTION).")
    p_reminders.add_argument("--comment-tickets", action="store_true",
                             help="Also post advisory comments on individual tickets "
                                  "(requires HYGIENE_LIVE_MODE=true).")

    # --- PR review queue (extends pr-review subcommand) ---
    p_review_queue = sub.add_parser(
        "review-queue",
        help="Triaged PR review queue — blocked-on-me first, with buddy-routing checks",
    )
    p_review_queue.add_argument("--repo",
                                help="Limit to one repo (default: all project repos)")
    p_review_queue.add_argument("--load", action="store_true",
                                help="Show review-load distribution across all reviewers")

    # --- Morning prep (sod + inbox + standup in one shot) ---
    p_prep = sub.add_parser(
        "prep",
        help="One-shot morning routine: SOD (if needed) + inbox + standup. "
             "Persists results to state/ so the UI loads them instantly.",
    )
    p_prep.add_argument("--force-sod", action="store_true",
                        help="Re-run SOD even if today's markdown exists")
    p_prep.add_argument("--skip-sod", action="store_true")
    p_prep.add_argument("--skip-inbox", action="store_true")
    p_prep.add_argument("--skip-standup", action="store_true")

    # --- Cron management ---
    p_cron_install = sub.add_parser("cron-install",
                                     help="Install vamos-managed crontab entries from crons.yml")
    p_cron_install.add_argument("--dry-run", action="store_true",
                                help="Print the would-be crontab; don't install.")
    p_cron_uninstall = sub.add_parser("cron-uninstall",
                                       help="Remove the vamos-managed crontab block")
    p_cron_uninstall.add_argument("--dry-run", action="store_true")
    sub.add_parser("cron-list", help="List configured cron entries from crons.yml")

    # --- UI ---
    p_ui = sub.add_parser("ui", help="Launch the Streamlit UI on localhost")
    p_ui.add_argument("--port", type=int, default=8501)

    # --- MCP server (Claude Desktop / Claude Code integration) ---
    p_mcp = sub.add_parser(
        "mcp",
        help="Run the vamos MCP server over stdio (for Claude Desktop / Claude Code)",
    )
    p_mcp.add_argument(
        "action", nargs="?", default="serve",
        choices=["serve", "install", "print-config"],
        help="serve (default) starts the stdio server. "
             "install prints copy-paste setup instructions. "
             "print-config emits JSON for claude_desktop_config.json.",
    )

    # --- Diagnostics ---
    sub.add_parser("test", help="Smoke test: verify ADO auth and print assigned item count")

    # --- Metrics (existing sub-dispatcher) ---
    metrics_cli.add_metrics_subcommands(sub)

    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s | %(message)s",
    )

    cfg = config_mod.load(profile=args.profile)
    day = date.fromisoformat(args.day) if args.day else None

    # Apply --board override BEFORE dispatching subcommands so they all see the
    # adjusted area/iteration paths via cfg.healthcheck_* and cfg.hygiene_*
    if args.board:
        areas, iters = boards_mod.resolve(args.board)
        if not areas:
            print(f"Unknown board: {args.board!r}. "
                  f"Available: {', '.join(boards_mod.board_names()) or '(none)'}.")
            return 64
        # Single-element lists collapse to scalars to keep query call sites simple
        area_val = areas[0] if len(areas) == 1 else areas
        iter_val = iters[0] if len(iters) == 1 else (iters if iters else None)
        cfg.healthcheck_area_path = area_val
        cfg.healthcheck_iteration_path = iter_val
        cfg.hygiene_area_path = area_val
        cfg.hygiene_iteration_path = iter_val
        if boards_mod.is_all(args.board):
            print(f"Board scope: ALL ({len(areas)} board(s))")
        else:
            print(f"Board scope: {args.board}")

    if args.cmd == "sod":
        path = sod.run(cfg, force=args.force, day=day)
        print(f"Wrote {path}")
        return 0

    if args.cmd == "sync":
        result = sync.run(cfg, dry_run=args.dry_run, day=day)
        print(f"Proposed: {result.actions_proposed}  "
              f"Executed: {result.actions_executed}  "
              f"Failed: {result.actions_failed}")
        if result.summary:
            print(f"Summary: {result.summary}")
        print(f"Log:     {result.log_path}")
        return 0 if result.actions_failed == 0 else 2

    if args.cmd == "eod":
        text = eod.run(
            cfg,
            dry_run=args.dry_run,
            skip_sync=args.skip_sync,
            skip_post=args.skip_post,
            skip_slack=args.skip_slack,
            day=day,
        )
        print()
        print(text)
        return 0

    if args.cmd == "daily":
        action = scheduler.dispatch(cfg, force=args.force)
        print(f"dispatch: {action}")
        return 0

    if args.cmd == "healthcheck":
        text = healthcheck.run(cfg, skip_post=args.skip_post, day=day)
        print()
        print(text)
        return 0

    if args.cmd == "hygiene":
        if args.clean:
            rule_filter = set(args.clean_rule) if args.clean_rule else None
            result = hygiene_mod.clean_runner.run(
                cfg, apply=args.apply, rule_filter=rule_filter,
                interactive=not args.apply, day=day,
            )
            print(f"\nDone — {len(result.proposals)} proposal(s), "
                  f"{len(result.applied)} applied, {len(result.skipped)} skipped.")
            n_failed = sum(1 for r in result.applied if not r.applied)
            return 0 if n_failed == 0 else 2

        report = hygiene_mod.run(
            cfg,
            skip_post=args.skip_post,
            auto_comment=args.auto_comment,
            day=day,
            repos_override=args.repo,
        )
        print()
        print(report.to_markdown())
        return 0 if not report.has_blockers else 1

    if args.cmd == "pr-review":
        return pr_review_mod.run(
            cfg,
            pr_id=args.pr_id,
            repo=args.repo,
            interactive=args.interactive,
            no_post=args.no_post,
            watch=args.watch,
        )

    if args.cmd == "inbox":
        items = inbox_mod.build(cfg, since_hours=args.since_hours)
        if args.json:
            import json
            print(json.dumps(inbox_mod.to_dict_list(items), indent=2))
        else:
            print(inbox_mod.render_text(items))
        return 0

    if args.cmd == "standup":
        print(standup_mod.run(cfg, day=day))
        return 0

    if args.cmd == "capture":
        path = capture_mod.run(
            cfg, text=args.text, customer=args.customer,
            priority=args.priority, day=day,
        )
        print(f"Appended [NEW] to {path}")
        return 0

    if args.cmd == "deps":
        client = ADOClient(cfg.ado_org_url, cfg.ado_project, cfg.ado_pat, read_only=True)
        deps = deps_mod.fetch(client, args.ticket_id)
        print(deps_mod.render_text(args.ticket_id, deps))
        return 0

    if args.cmd == "brief":
        text = brief_mod.run(cfg, engineer=args.engineer, weeks=args.weeks, day=day)
        print(text)
        return 0

    if args.cmd == "retro":
        text = retro_mod.run(cfg, iteration_path=args.iteration, weeks=args.weeks, day=day)
        print(text)
        return 0

    if args.cmd == "at-risk":
        report = at_risk_mod.run(cfg, skip_post=args.skip_post, day=day)
        print()
        print(report.to_markdown())
        return 0 if not report.has_blockers else 1

    if args.cmd == "reminders":
        # Generate without posting first — preview comes before the decision.
        report = reminders_mod.run(
            cfg,
            skip_post=True,
            comment_tickets=args.comment_tickets,
            channel=args.channel,
            day=day,
        )
        print()
        print(report.to_markdown())
        print()

        if args.skip_post:
            print("--skip-post set: report generated, not delivered.")
            return 0

        if not report.findings:
            print("No findings — nothing to send.")
            return 0

        target = args.channel or cfg.connection_option
        if args.send:
            do_send = True
        else:
            try:
                answer = input(f"Send to {target}? [y/N] ").strip().lower()
            except EOFError:
                answer = ""
            do_send = answer in ("y", "yes")

        if do_send:
            from .core import delivery as _delivery
            _delivery.post_report(cfg, report, prefer=args.channel)
            print(f"Sent to {target}.")
        else:
            print("Skipped sending. Report saved to state/reminders/.")
        return 0

    if args.cmd == "review-queue":
        if args.load:
            loads = pr_queue_mod.review_load(cfg)
            print("Active PR review load:")
            for name, n in loads.items():
                print(f"  {n:3d}  {name}")
            return 0
        items = pr_queue_mod.build_queue(cfg, repo=args.repo)
        if not items:
            print("No active PRs.")
            return 0
        print(f"Review queue — {len(items)} PR(s)")
        for q in items:
            tags = []
            if q.blocked_on_me:
                tags.append("BLOCKED-ON-ME")
            tags.append(q.role.upper())
            if q.is_draft:
                tags.append("DRAFT")
            if q.buddy_skipped:
                tags.append(f"BUDDY-SKIPPED:{q.buddy_skipped}")
            print(f"  [{q.repo}] #{q.pr_id}  age={q.age_days}d  {' '.join(tags)}")
            print(f"      {q.title}")
            print(f"      by {q.author}")
        return 0

    if args.cmd == "prep":
        result = prep_mod.run(
            cfg,
            force_sod=args.force_sod,
            skip_sod=args.skip_sod,
            skip_inbox=args.skip_inbox,
            skip_standup=args.skip_standup,
            day=day,
        )
        print(f"prep: SOD={result.sod_path or '(skipped)'} · "
              f"inbox={result.inbox_count} · standup={result.standup_path or '(skipped)'}")
        if result.skipped:
            print(f"   skipped: {', '.join(result.skipped)}")
        return 0

    if args.cmd == "cron-install":
        return cron_install_mod.cmd_install(args, cfg)
    if args.cmd == "cron-uninstall":
        return cron_install_mod.cmd_uninstall(args, cfg)
    if args.cmd == "cron-list":
        return cron_install_mod.cmd_list(args, cfg)

    if args.cmd == "ui":
        return _launch_ui(args.port)

    if args.cmd == "mcp":
        return _run_mcp(args.action)

    if args.cmd == "test":
        client = ADOClient(cfg.ado_org_url, cfg.ado_project, cfg.ado_pat, read_only=True)
        ids = client.query_assigned(cfg.assigned_user_clause)
        print(f"OK: {cfg.ado_org_url}/{cfg.ado_project}")
        print(f"Assigned items for {cfg.assigned_user_clause}: {len(ids)}")
        if ids:
            items = client.get_work_items(ids[:10])
            for item in items:
                print(f"  [{item.id}] {item.type} | P{item.priority} | {item.state} | {item.title[:80]}")
        return 0

    if args.cmd == "metrics":
        # Handle metrics subcommands
        if hasattr(args, 'func'):
            args.func(args, cfg)
            return 0
        else:
            parser.print_help()
            return 1

    parser.print_help()
    return 1


def _run_mcp(action: str) -> int:
    """Dispatch the `vamos mcp` subcommand."""
    import shutil

    if action == "serve":
        try:
            from .mcp.server import run as run_server
        except ImportError as exc:
            print(f"ERROR: MCP extras not installed. Run: pip install -e '.[mcp]'  ({exc})")
            return 2
        run_server()
        return 0

    vamos_path = shutil.which("vamos") or "vamos"

    if action == "print-config":
        import json
        snippet = {
            "mcpServers": {
                "vamos": {
                    "command": vamos_path,
                    "args": ["mcp"],
                }
            }
        }
        print(json.dumps(snippet, indent=2))
        return 0

    if action == "install":
        print("vamos MCP server — install instructions")
        print()
        print("1. Make sure mcp extras are installed:")
        print("     pip install -e '.[mcp]'")
        print()
        print("2A. Claude Code (recommended):")
        print(f"     claude mcp add vamos -- {vamos_path} mcp")
        print()
        print("2B. Claude Desktop — add this to claude_desktop_config.json:")
        print()
        print('     {')
        print('       "mcpServers": {')
        print('         "vamos": {')
        print(f'           "command": "{vamos_path}",')
        print('           "args": ["mcp"]')
        print('         }')
        print('       }')
        print('     }')
        print()
        print("    Config locations:")
        print("      macOS:   ~/Library/Application Support/Claude/claude_desktop_config.json")
        print("      Windows: %APPDATA%\\Claude\\claude_desktop_config.json")
        print()
        print("3. Restart Claude. Try: 'use vamos to fetch ticket 12345'.")
        return 0

    print(f"Unknown mcp action: {action}")
    return 1


def _launch_ui(port: int) -> int:
    """Boot the NiceGUI app in this process. Adds repo root to sys.path as a
    fallback for editable-install setups where `ui` isn't yet on the path."""
    import sys
    from pathlib import Path
    repo_root = Path(__file__).resolve().parent.parent
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    try:
        from ui.main import run_app
    except ImportError as exc:
        print(f"ERROR: UI not installed. Run: pip install -e '.[ui]'  ({exc})")
        return 2
    run_app(port=port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
