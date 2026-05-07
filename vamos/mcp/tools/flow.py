"""Engineer flow orchestrator MCP tools.

These wrap the existing CLI subcommands (sod, sync, eod, prep, capture)
1:1 so Claude can drive them exactly the way an engineer would type
`vamos sod` / `vamos sync` / `vamos eod`.

The LLM-backed ones (run_sync, run_eod) shell out to `claude -p` internally
and take 30-90s. Tool descriptions warn callers.
"""
from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any

from ... import capture as capture_mod
from ... import eod as eod_mod
from ... import prep as prep_mod
from ... import sod as sod_mod
from ... import standup as standup_mod
from ... import sync as sync_mod
from ...inbox import build as inbox_build, to_dict_list as inbox_to_dict
from .._context import get_ctx

log = logging.getLogger(__name__)


def _today() -> _date:
    return _date.today()


def run_sod(force: bool = False) -> dict[str, Any]:
    """Pull today's assigned tickets into work/YYYY-MM-DD.md.

    Idempotent — if today's markdown already exists, returns the existing
    path unless force=True.
    """
    ctx = get_ctx()
    path = sod_mod.run(ctx.cfg, force=force, day=_today())
    return {
        "markdown_path": str(path),
        "exists": path.exists(),
        "day": _today().isoformat(),
    }


def run_sync(dry_run: bool = False) -> dict[str, Any]:
    """Apply today's markdown edits to ADO via claude -p.

    LLM-backed — takes 30-90s. Reads work/YYYY-MM-DD.md, asks Claude to
    diff against ADO, gets back an action plan (state changes, comments,
    new tickets, links), executes. Returns counts + the log path.

    Pass dry_run=True to generate the action plan without executing — use
    this if you want to preview before committing edits.
    """
    ctx = get_ctx()
    result = sync_mod.run(ctx.cfg, dry_run=dry_run, day=_today())
    return {
        "actions_proposed": result.actions_proposed,
        "actions_executed": result.actions_executed,
        "actions_failed": result.actions_failed,
        "summary": result.summary,
        "log_path": str(result.log_path),
        "dry_run": dry_run,
    }


def run_eod(
    dry_run: bool = False,
    skip_sync: bool = False,
    skip_post: bool = False,
    skip_slack: bool = False,
) -> dict[str, Any]:
    """Generate EOD summary, run final sync, post to Teams/Slack.

    LLM-backed — takes 30-60s. Steps:
      1. Final sync (unless skip_sync) — applies any last markdown edits.
      2. Generate the EOD text via Claude.
      3. Post to Teams (unless skip_post) and Slack (unless skip_slack).

    Pass dry_run=True to preview the EOD text without posting or syncing.
    Returns the EOD text in `text` so Claude can show it before posting.
    """
    ctx = get_ctx()
    text = eod_mod.run(
        ctx.cfg,
        dry_run=dry_run,
        skip_sync=skip_sync,
        skip_post=skip_post,
        skip_slack=skip_slack,
        day=_today(),
    )
    return {
        "text": text,
        "dry_run": dry_run,
        "synced": not skip_sync and not dry_run,
        "posted_teams": not skip_post and not dry_run,
        "posted_slack": not skip_slack and not dry_run,
        "day": _today().isoformat(),
    }


def run_prep(
    force_sod: bool = False,
    skip_sod: bool = False,
    skip_inbox: bool = False,
    skip_standup: bool = False,
) -> dict[str, Any]:
    """One-shot morning routine: SOD + inbox + standup, all cached for the UI.

    Persists results to state/ so the UI can render them instantly. Use
    this as a single "good morning" call instead of running sod, get_inbox,
    get_standup separately.
    """
    ctx = get_ctx()
    result = prep_mod.run(
        ctx.cfg,
        force_sod=force_sod,
        skip_sod=skip_sod,
        skip_inbox=skip_inbox,
        skip_standup=skip_standup,
        day=_today(),
    )
    return {
        "sod_path": str(result.sod_path) if result.sod_path else None,
        "inbox_count": result.inbox_count,
        "standup_path": str(result.standup_path) if result.standup_path else None,
        "skipped": list(result.skipped),
    }


def capture_ticket(
    text: str,
    customer: str | None = None,
    priority: int | None = None,
) -> dict[str, Any]:
    """Append a [NEW] section to today's daily markdown.

    Quick capture from anywhere — engineer hears about a new bug or task,
    drops it into today's MD via this tool. The next `run_sync` will turn
    it into a real ADO work item.

    First line of `text` becomes the title; subsequent lines become the
    description. Pass `customer` (e.g. "Vituity") and `priority` (1-4) as
    hints if you have them.
    """
    if not text or not text.strip():
        return {"error": "text is required"}
    if priority is not None and priority not in (1, 2, 3, 4):
        return {"error": "priority must be 1-4"}
    ctx = get_ctx()
    path = capture_mod.run(
        ctx.cfg, text=text, customer=customer, priority=priority, day=_today(),
    )
    return {
        "markdown_path": str(path),
        "captured": text.splitlines()[0][:120],
        "customer": customer,
        "priority": priority,
    }


def get_inbox(since_hours: int = 48) -> dict[str, Any]:
    """Aggregate everything that wants the engineer's attention.

    Returns review requests, PR comments, ticket comments mentioning you,
    and new P1/P2 assignments from the last `since_hours` (default 48).
    Each item has kind, title, url, actor, when, summary, severity.
    """
    ctx = get_ctx()
    items = inbox_build(ctx.cfg, since_hours=since_hours)
    return {
        "since_hours": since_hours,
        "count": len(items),
        "items": inbox_to_dict(items),
    }


def get_standup() -> dict[str, Any]:
    """Auto-draft yesterday/today/blockers brief.

    Reads recent ADO activity (closed yesterday, active today, blocked
    items) and produces a markdown standup brief. Engineers paste this
    into the daily standup channel.
    """
    ctx = get_ctx()
    text = standup_mod.run(ctx.cfg, day=_today())
    return {"day": _today().isoformat(), "text": text}
