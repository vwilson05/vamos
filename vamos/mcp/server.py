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

from .tools import flow as flow_tools
from .tools import hygiene as hygiene_tools
from .tools import prs as pr_tools
from .tools import team as team_tools
from .tools import tickets as ticket_tools

log = logging.getLogger(__name__)

mcp = FastMCP(
    "vamos",
    instructions=(
        "vamos exposes HaloMD's full ADO workflow as MCP tools, organized by "
        "persona: engineer (atomic + flow orchestrators), reviewer, manager, "
        "leadership. Every ticket-shaped response includes `next_actions` — "
        "concrete tool calls to consider next. Read-only and low-stakes write "
        "tools auto-execute. close_ticket and run_pr_review (with post=True) "
        "require confirm=True; always show the preview to a human before "
        "re-calling with confirm. LLM-backed tools (run_sync, run_eod, "
        "get_engineer_brief, get_retro) take 30-90s — set expectations."
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
def vote_on_pr(
    pr_id: int,
    repo: str,
    vote: str,
    confirm: bool = False,
) -> dict[str, Any]:
    """Cast (or change) the current user's vote on a PR.

    SAFETY: returns a dry-run preview unless confirm=True. When the user
    explicitly says "approve it" / "reject this PR", treat that as the
    confirmation and pass confirm=True directly — no extra round-trip.

    Valid vote values:
      - "approve"                  (score 10)
      - "approve-with-suggestions" (score 5)
      - "wait-for-author"          (score -5)
      - "reject"                   (score -10)
      - "no-vote"                  (score 0, clears any existing vote)
    """
    return ticket_ools_safe(
        pr_tools.vote_on_pr,
        pr_id=pr_id, repo=repo, vote=vote, confirm=confirm,
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


# ---------------- Engineer flow orchestrators ----------------

@mcp.tool()
def run_sod(force: bool = False) -> dict[str, Any]:
    """Pull today's assigned tickets into work/YYYY-MM-DD.md.

    Idempotent — returns the existing path if today's file is already
    written, unless force=True.
    """
    return ticket_ools_safe(flow_tools.run_sod, force=force)


@mcp.tool()
def run_sync(dry_run: bool = False) -> dict[str, Any]:
    """Apply today's markdown edits to ADO via claude -p.

    LLM-backed — takes 30-90s. Use this when an engineer says "I just did X
    for ticket N, post the comments and commit my edits". Pass dry_run=True
    to preview the action plan without executing.
    """
    return ticket_ools_safe(flow_tools.run_sync, dry_run=dry_run)


@mcp.tool()
def run_eod(
    dry_run: bool = False,
    skip_sync: bool = False,
    skip_post: bool = False,
    skip_slack: bool = False,
) -> dict[str, Any]:
    """Generate EOD summary, run final sync, post to Teams/Slack.

    LLM-backed — takes 30-60s. Returns the generated text in `text` so
    you can show the user before posting. Pass dry_run=True to preview
    without posting or syncing.
    """
    return ticket_ools_safe(
        flow_tools.run_eod,
        dry_run=dry_run, skip_sync=skip_sync,
        skip_post=skip_post, skip_slack=skip_slack,
    )


@mcp.tool()
def run_prep(
    force_sod: bool = False,
    skip_sod: bool = False,
    skip_inbox: bool = False,
    skip_standup: bool = False,
) -> dict[str, Any]:
    """One-shot morning routine: SOD + inbox + standup, all cached.

    Use as a single "good morning, prep my day" call. Persists results
    to state/ so the UI loads them instantly.
    """
    return ticket_ools_safe(
        flow_tools.run_prep,
        force_sod=force_sod, skip_sod=skip_sod,
        skip_inbox=skip_inbox, skip_standup=skip_standup,
    )


@mcp.tool()
def capture_ticket(
    text: str,
    customer: str | None = None,
    priority: int | None = None,
) -> dict[str, Any]:
    """Append a [NEW] section to today's daily markdown.

    Quick-capture from anywhere. The next `run_sync` will turn it into
    a real ADO work item. First line is the title; rest is description.
    """
    return ticket_ools_safe(
        flow_tools.capture_ticket,
        text=text, customer=customer, priority=priority,
    )


# ---------------- Engineer support ----------------

@mcp.tool()
def get_inbox(since_hours: int = 48) -> dict[str, Any]:
    """Aggregate everything that wants the engineer's attention.

    Returns review requests, PR comments, ticket comments mentioning you,
    and new P1/P2 assignments from the last `since_hours`.
    """
    return ticket_ools_safe(flow_tools.get_inbox, since_hours=since_hours)


@mcp.tool()
def get_standup() -> dict[str, Any]:
    """Auto-draft today's yesterday/today/blockers standup brief."""
    return ticket_ools_safe(flow_tools.get_standup)


@mcp.tool()
def get_dependencies(ticket_id: int) -> dict[str, Any]:
    """Show parent/children/blocked-by/blocks/related/duplicates for a ticket.

    Use before starting work on a ticket to understand the surrounding
    context. Returns deps grouped by relationship type.
    """
    return ticket_ools_safe(team_tools.get_dependencies, ticket_id=ticket_id)


# ---------------- Reviewer ----------------

@mcp.tool()
def get_review_queue(repo: str | None = None) -> dict[str, Any]:
    """Triaged PR review queue — blocked-on-me first.

    Pass `repo` to limit to one ADO repo, or omit to scan every repo in
    the project. Each item has age, role, blocked_on_me flag, and any
    buddy-routing skip warnings.
    """
    return ticket_ools_safe(team_tools.get_review_queue, repo=repo)


@mcp.tool()
def get_review_load() -> dict[str, Any]:
    """PR review-load distribution across all reviewers.

    Use before assigning a review to route fairly.
    """
    return ticket_ools_safe(team_tools.get_review_load)


# ---------------- Manager ----------------

@mcp.tool()
def list_engineer_tickets(
    engineer: str,
    include_closed: bool = False,
) -> dict[str, Any]:
    """List active tickets assigned to a specific engineer.

    `engineer` accepts display name or email — vamos's identity layer
    collapses ADO's split identities for you.
    """
    return ticket_ools_safe(
        team_tools.list_engineer_tickets,
        engineer=engineer, include_closed=include_closed,
    )


@mcp.tool()
def get_engineer_brief(engineer: str, weeks: int = 1) -> dict[str, Any]:
    """1:1 brief markdown for a specific engineer covering the last N weeks.

    LLM-backed — takes 30-60s. Returns recent shipped, active, blocked,
    and questions to ask, formatted for direct paste into the 1:1 doc.
    """
    return ticket_ools_safe(
        team_tools.get_engineer_brief, engineer=engineer, weeks=weeks,
    )


@mcp.tool()
def get_retro(iteration: str | None = None, weeks: int = 2) -> dict[str, Any]:
    """Sprint retro starter — shipped / missed / themes / customers.

    LLM-backed — takes 30-60s. Pass an explicit iteration path or omit
    to use HYGIENE_ITERATION_PATH from config.
    """
    return ticket_ools_safe(
        team_tools.get_retro, iteration=iteration, weeks=weeks,
    )


# ---------------- Leadership ----------------

@mcp.tool()
def get_at_risk() -> dict[str, Any]:
    """At-risk scan: past-target / blocked P1s / aging items + aging PRs.

    Read-only — never posts to Teams/Slack from MCP. Returns the full
    Report (findings + counts + markdown render).
    """
    return ticket_ools_safe(team_tools.get_at_risk)


@mcp.tool()
def get_team_hygiene() -> dict[str, Any]:
    """Full-board hygiene rollup — runs all 7 rules across the whole board.

    Wider scope than `run_hygiene_check` (single ticket). Read-only,
    never posts comments. Use for weekly leadership reviews.
    """
    return ticket_ools_safe(team_tools.get_team_hygiene)


@mcp.tool()
def get_team_healthcheck() -> dict[str, Any]:
    """Per-engineer team-wide ticket snapshot.

    Side-effect-free — never posts. Returns the full markdown rollup.
    """
    return ticket_ools_safe(team_tools.get_team_healthcheck)


@mcp.tool()
def run_metrics(format: str = "markdown") -> dict[str, Any]:
    """Generate the board metrics report — backlog / throughput / cycle time.

    `format` is "markdown", "html", or "json". Always dry-run from MCP —
    never sends notifications. Returns the output file path + a tiny
    summary; read the file with file tools for the full report.
    """
    return ticket_ools_safe(team_tools.run_metrics, format=format)


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
