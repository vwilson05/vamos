"""Manager + leadership MCP tools.

Wrap the existing team-reporting agents (brief, retro, at-risk, hygiene,
healthcheck, metrics). All return structured JSON; the markdown renders
are included for callers that want to surface text to the user directly.

LLM-backed tools (get_engineer_brief, get_retro) take 30-60s.

Posting side-effects are forced OFF — these tools never deliver to
Teams/Slack from Claude. If a manager wants to post the at-risk report,
they run `vamos at-risk` from the CLI explicitly.
"""
from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any

from ... import at_risk as at_risk_mod
from ... import brief as brief_mod
from ... import deps as deps_mod
from ... import healthcheck as healthcheck_mod
from ... import hygiene as hygiene_mod
from ... import retro as retro_mod
from ...ado import ADOClient
from ...pr_review import queue as pr_queue_mod
from .._context import get_ctx
from .._serialize import report_to_dict, to_jsonable

log = logging.getLogger(__name__)


def _today() -> _date:
    return _date.today()


# ---------------- Engineer support (deps lives here, not in flow) ----------------

def get_dependencies(ticket_id: int) -> dict[str, Any]:
    """Show parent/children/blocked-by/blocks/related/duplicates for a ticket.

    Use before starting work on a ticket to understand the surrounding
    context. Returns a list grouped by relationship type.
    """
    ctx = get_ctx()
    # Read-only client — deps doesn't mutate.
    ro = ADOClient(ctx.cfg.ado_org_url, ctx.cfg.ado_project, ctx.cfg.ado_pat, read_only=True)
    deps = deps_mod.fetch(ro, ticket_id)
    return {
        "ticket_id": ticket_id,
        "count": len(deps),
        "dependencies": [to_jsonable(d) for d in deps],
        "markdown": deps_mod.render_text(ticket_id, deps),
    }


# ---------------- Reviewer ----------------

def get_review_queue(repo: str | None = None) -> dict[str, Any]:
    """Triaged PR review queue — blocked-on-me first.

    Pass `repo` to limit to one ADO repo, or omit to scan every repo in
    the project. Each item has pr_id, repo, title, author, age_days, role
    (author/reviewer/both/observer), blocked_on_me flag, and any
    buddy-routing skip warnings.
    """
    ctx = get_ctx()
    items = pr_queue_mod.build_queue(ctx.cfg, repo=repo)
    return {
        "count": len(items),
        "blocked_on_me_count": sum(1 for i in items if i.blocked_on_me),
        "items": [to_jsonable(i) for i in items],
    }


def get_review_load() -> dict[str, Any]:
    """Distribution of active PR review assignments across all reviewers.

    Read this before assigning a review — gives you a "who's overloaded"
    snapshot so you can route reviews fairly.
    """
    ctx = get_ctx()
    loads = pr_queue_mod.review_load(ctx.cfg)
    return {
        "count": len(loads),
        "loads": dict(sorted(loads.items(), key=lambda kv: -kv[1])),
    }


# ---------------- Manager ----------------

def list_engineer_tickets(
    engineer: str,
    include_closed: bool = False,
) -> dict[str, Any]:
    """List active tickets assigned to a specific engineer.

    Use for manager check-ins ("what's on Jamie's plate?") or for blocked-on
    triage. `engineer` accepts display name or email — vamos's identity
    layer collapses ADO's split identities for you.
    """
    ctx = get_ctx()
    safe = engineer.replace("'", "''")
    user_clause = f"'{safe}'"
    ro = ADOClient(ctx.cfg.ado_org_url, ctx.cfg.ado_project, ctx.cfg.ado_pat, read_only=True)
    ids = ro.query_assigned(user_clause, include_closed=include_closed)
    items = ro.get_work_items(ids)
    return {
        "engineer": engineer,
        "include_closed": include_closed,
        "count": len(items),
        "tickets": [
            {
                "id": w.id,
                "type": w.type,
                "title": w.title,
                "state": w.state,
                "priority": w.priority,
                "tags": w.tags,
                "url": w.url,
            }
            for w in items
        ],
    }


def get_engineer_brief(engineer: str, weeks: int = 1) -> dict[str, Any]:
    """1:1 brief for a specific engineer covering the last N weeks.

    LLM-backed — takes 30-60s. Pulls assigned + closed work + recent
    comments + PR activity for the engineer, asks Claude to summarize
    into a 1:1-friendly markdown brief (recent shipped, active, blocked,
    questions to ask).
    """
    ctx = get_ctx()
    text = brief_mod.run(ctx.cfg, engineer=engineer, weeks=weeks, day=_today())
    return {"engineer": engineer, "weeks": weeks, "markdown": text}


def get_retro(iteration: str | None = None, weeks: int = 2) -> dict[str, Any]:
    """Sprint retro starter — shipped / missed / themes / customers.

    LLM-backed — takes 30-60s. Either pass an explicit `iteration` path
    (e.g. "Data Platform\\Sprint 47"), or omit to use HYGIENE_ITERATION_PATH.
    Returns markdown ready for the retro doc.
    """
    ctx = get_ctx()
    text = retro_mod.run(
        ctx.cfg, iteration_path=iteration, weeks=weeks, day=_today(),
    )
    return {"iteration": iteration, "weeks": weeks, "markdown": text}


# ---------------- Leadership ----------------

def get_at_risk() -> dict[str, Any]:
    """At-risk scan: past-target / blocked P1s / aging items + aging PRs.

    Returns the full Report (findings grouped by severity, plus the
    markdown render). Side-effect-free — never posts to Teams/Slack.
    """
    ctx = get_ctx()
    report = at_risk_mod.run(ctx.cfg, skip_post=True, day=_today())
    return report_to_dict(report)


def get_team_hygiene() -> dict[str, Any]:
    """Full-board hygiene rollup — runs all 7 rules across the whole board.

    Wider scope than `run_hygiene_check` (which scopes to one ticket).
    Use this for weekly leadership reviews or ahead of sprint retros.
    Read-only — never posts comments.
    """
    ctx = get_ctx()
    report = hygiene_mod.run(ctx.cfg, skip_post=True, auto_comment=False, day=_today())
    return report_to_dict(report)


def get_team_healthcheck() -> dict[str, Any]:
    """Per-engineer ticket snapshot + team rollup.

    Returns the markdown text directly (healthcheck doesn't use Report).
    Side-effect-free — never posts.
    """
    ctx = get_ctx()
    text = healthcheck_mod.run(ctx.cfg, skip_post=True, day=_today())
    return {"day": _today().isoformat(), "markdown": text}


def run_metrics(format: str = "markdown") -> dict[str, Any]:
    """Generate the board metrics report — backlog / throughput / cycle time.

    `format` is "markdown", "html", or "json". Returns the path to the
    generated report plus a short summary. The full report on disk can
    be read with the standard file tools if needed.
    """
    if format not in ("markdown", "html", "json"):
        return {"error": f"format must be markdown/html/json, got {format!r}"}
    ctx = get_ctx()
    from .. import metrics_dispatch
    return metrics_dispatch.generate(ctx.cfg, format=format)
