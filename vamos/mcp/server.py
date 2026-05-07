"""FastMCP server for vamos.

Exposes 8 tools to Claude over stdio:

  Read-only:
    get_ticket(ticket_id)
    list_my_tickets(include_closed=False)

  Low-stakes writes (auto-execute):
    start_work(ticket_id, comment=None)
    post_comment(ticket_id, text)
    open_pr(ticket_id, repo, source_branch, title, ...)

  Read pipelines:
    run_pr_review(pr_id, repo, post=False, confirm=False)
    run_hygiene_check(ticket_id)

  Confirm-required:
    close_ticket(ticket_id, ..., confirm=False)

Run with: `vamos mcp` (or python -m vamos.mcp.server)
"""
from __future__ import annotations

import logging
import sys
from typing import Any

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as exc:  # pragma: no cover
    print(
        "ERROR: mcp SDK is not installed. Run:  pip install -e '.[mcp]'\n"
        f"  ({exc})",
        file=sys.stderr,
    )
    raise

from .tools import hygiene as hygiene_tools
from .tools import prs as pr_tools
from .tools import tickets as ticket_tools

log = logging.getLogger(__name__)

mcp = FastMCP(
    "vamos",
    instructions=(
        "vamos exposes Azure DevOps ticket and PR actions for HaloMD's engineering "
        "workflow. Every response includes `next_actions` — concrete tool calls "
        "to consider next. Read-only and low-stakes write tools auto-execute. "
        "close_ticket and run_pr_review (with post=True) require confirm=True; "
        "always show the preview to a human before re-calling with confirm."
    ),
)


# ---------------- Read-only ----------------

@mcp.tool()
def get_ticket(ticket_id: int) -> dict[str, Any]:
    """Fetch a single ADO work item with everything needed to plan work.

    Returns title, state, priority, assignee, description, acceptance criteria,
    a suggested git branch name, recent comments, linked PRs, and `next_actions`
    (which tool to call next based on the ticket's current state).

    Use this as the starting point for any work on a ticket.
    """
    return ticket_ools_safe(ticket_tools.get_ticket, ticket_id=ticket_id)


@mcp.tool()
def list_my_tickets(include_closed: bool = False) -> dict[str, Any]:
    """List tickets currently assigned to the configured user.

    Each entry has a `next_action_hint` so you can pick the most actionable
    ticket to work on first. Pass include_closed=True to include recently
    closed tickets (useful for retros and standups).
    """
    return ticket_ools_safe(ticket_tools.list_my_tickets, include_closed=include_closed)


# ---------------- Low-stakes writes ----------------

@mcp.tool()
def start_work(ticket_id: int, comment: str | None = None) -> dict[str, Any]:
    """Move a ticket to Active and post a starting daily-standup comment.

    Returns a suggested git branch name. Auto-executes (no confirm) — moving
    a ticket to Active is reversible and leaving a "started" comment is harmless.

    Pass `comment` to override the default "Started YYYY-MM-DD..." text.
    """
    return ticket_ools_safe(ticket_tools.start_work, ticket_id=ticket_id, comment=comment)


@mcp.tool()
def post_comment(ticket_id: int, text: str) -> dict[str, Any]:
    """Post a comment on a ticket — typically a daily progress note.

    The hygiene rules expect one comment per business day on every Active
    ticket. Use this to satisfy that requirement and keep the board honest.
    Text is posted verbatim with no prefix.
    """
    return ticket_ools_safe(ticket_tools.post_comment, ticket_id=ticket_id, text=text)


@mcp.tool()
def open_pr(
    ticket_id: int,
    repo: str,
    source_branch: str,
    title: str,
    description: str = "",
    target_branch: str = "main",
    is_draft: bool = False,
) -> dict[str, Any]:
    """Open a PR in the named ADO git repo and link it to the ticket.

    `repo` is the ADO repo name (e.g. "ado-agent-v2"). `source_branch` is the
    branch you've already pushed (e.g. "feature/12345-add-foo"). The work
    item is auto-linked. Returns the PR id and web URL.

    Auto-executes — PRs are easy to abandon if wrong.
    """
    return ticket_ools_safe(
        pr_tools.open_pr,
        ticket_id=ticket_id, repo=repo, source_branch=source_branch,
        title=title, description=description, target_branch=target_branch,
        is_draft=is_draft,
    )


# ---------------- Read pipelines (LLM-backed) ----------------

@mcp.tool()
def run_pr_review(
    pr_id: int,
    repo: str,
    post: bool = False,
    confirm: bool = False,
) -> dict[str, Any]:
    """Run vamos's automated PR reviewer and return structured findings.

    Default: returns the review JSON without posting. To publish findings
    as PR comments, pass post=True AND confirm=True (two-step safety so
    Claude can't accidentally spam comments).

    Findings include verdict, summary, and a list of {severity, file, line,
    description, suggested_change} entries. Surface the verdict + any
    [BLOCKER]/[SHOULD-FIX] findings to the human before deciding whether
    to act on them.
    """
    return ticket_ools_safe(
        pr_tools.run_pr_review,
        pr_id=pr_id, repo=repo, post=post, confirm=confirm,
    )


@mcp.tool()
def run_hygiene_check(ticket_id: int) -> dict[str, Any]:
    """Run all board-standards rules against a single ticket.

    Read-only — never posts comments. Returns a list of findings keyed by
    rule_id (state-discipline, daily-comments, required-fields, pr-linkage,
    branch-naming, resolution-on-close, stale-blocked) with severity and
    a suggested fix.

    Run this before close_ticket to verify the ticket is in good shape.
    """
    return ticket_ools_safe(hygiene_tools.run_hygiene_check, ticket_id=ticket_id)


# ---------------- Confirm-required ----------------

@mcp.tool()
def close_ticket(
    ticket_id: int,
    resolution: str = "Fixed",
    comment: str | None = None,
    target_state: str = "Resolved",
    confirm: bool = False,
) -> dict[str, Any]:
    """Move a ticket to Resolved/Closed with a resolution reason.

    SAFETY: returns a dry-run preview unless confirm=True. Always show the
    preview to a human before re-calling with confirm=True.

    `target_state` defaults to "Resolved" — many ADO templates require an
    intermediate Resolved step before Closed. Pass target_state="Closed"
    if your template skips Resolved.

    Common `resolution` values: "Fixed", "Won't Fix", "Duplicate", "As Designed".
    """
    return ticket_ools_safe(
        ticket_tools.close_ticket,
        ticket_id=ticket_id, resolution=resolution, comment=comment,
        target_state=target_state, confirm=confirm,
    )


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def ticket_ools_safe(fn, **kwargs) -> dict[str, Any]:
    """Wrap a tool call with a uniform error envelope so MCP responses always
    serialize cleanly. Without this, an unhandled exception leaks a stack
    trace to the client and breaks the JSON-RPC contract."""
    try:
        return fn(**kwargs)
    except Exception as exc:  # noqa: BLE001
        log.exception("vamos-mcp tool failed: %s", fn.__name__)
        return {"error": f"{type(exc).__name__}: {exc}", "tool": fn.__name__}


def run() -> None:
    """Entry point — start the stdio MCP server."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s | %(message)s",
        # MCP stdio uses stdout for JSON-RPC; logs MUST go to stderr.
        stream=sys.stderr,
    )
    log.info("vamos-mcp: starting stdio server")
    mcp.run()


if __name__ == "__main__":
    run()
