"""Ticket-centric MCP tools.

Each tool returns a JSON-serializable dict. Every response includes
`next_actions` — a hint for Claude on what to call next based on current state.

Safety contract:
  - get_ticket / list_my_tickets : read-only, auto-execute
  - start_work / post_comment    : low-stakes write, auto-execute
  - close_ticket                 : preview unless confirm=True

All write tools append to state/trail/<id>.jsonl for audit.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Any

from ...ado import WorkItem
from .. import share, trail, workflow
from .._context import get_ctx

log = logging.getLogger(__name__)

# Standard ADO state buckets used across HaloMD boards.
STATE_ACTIVE = "Active"
STATE_RESOLVED = "Resolved"
STATE_CLOSED = "Closed"

# Default resolution code; ADO accepts "Fixed", "Won't Fix", "Duplicate", "As Designed".
DEFAULT_RESOLUTION = "Fixed"


def get_ticket(ticket_id: int) -> dict[str, Any]:
    """Fetch a single ticket with everything Claude needs to plan work.

    Returns title, state, priority, AC, assignee, recent comments, linked PRs,
    and a `next_actions` hint describing the most likely next tool call(s).
    """
    ctx = get_ctx()
    items = ctx.client.get_work_items([ticket_id])
    if not items:
        return {"error": f"Ticket {ticket_id} not found"}
    item = items[0]
    relations = ctx.client.get_work_item_relations(ticket_id)
    comments = ctx.client.get_work_item_comments(ticket_id)
    next_actions = workflow.compute(ctx.cfg, ctx.client, item, relations=relations)

    return {
        "id": item.id,
        "type": item.type,
        "title": item.title,
        "state": item.state,
        "priority": item.priority,
        "assigned_to": item.assigned_to,
        "tags": item.tags,
        "url": item.url,
        "description": _strip_html(item.description or ""),
        "acceptance_criteria": _strip_html(
            item.raw_fields.get("Microsoft.VSTS.Common.AcceptanceCriteria") or ""
        ),
        "area_path": item.raw_fields.get("System.AreaPath"),
        "iteration_path": item.raw_fields.get("System.IterationPath"),
        "branch_suggestion": _branch_suggestion(item),
        "linked_prs": _summarize_pr_links(relations),
        "recent_comments": _summarize_comments(comments, limit=5),
        "next_actions": workflow.to_json(next_actions),
    }


def list_my_tickets(include_closed: bool = False) -> dict[str, Any]:
    """List tickets assigned to the configured user (ADO_USER_EMAIL).

    Each entry has id/title/state/priority + a tiny next_actions hint so
    Claude can pick the most relevant ticket to work on next.
    """
    ctx = get_ctx()
    ids = ctx.client.query_assigned(
        ctx.cfg.assigned_user_clause,
        include_closed=include_closed,
    )
    items = ctx.client.get_work_items(ids)
    out = []
    for item in items:
        # Avoid an extra relations call per ticket; light hint based on state alone.
        out.append({
            "id": item.id,
            "type": item.type,
            "title": item.title,
            "state": item.state,
            "priority": item.priority,
            "url": item.url,
            "next_action_hint": _light_hint(item),
        })
    return {"count": len(out), "tickets": out}


def start_work(ticket_id: int, comment: str | None = None) -> dict[str, Any]:
    """Move a ticket to Active and post a daily standup comment.

    Safe to call repeatedly — re-posting "Started 2026-05-06" is harmless.
    Auto-executes (no confirm).
    """
    ctx = get_ctx()
    today = date.today().isoformat()
    body = comment or f"Started {today}. Picking up this ticket."

    items_before = ctx.client.get_work_items([ticket_id])
    if not items_before:
        return {"error": f"Ticket {ticket_id} not found"}
    before = items_before[0]

    state_changed = False
    if before.state != STATE_ACTIVE and before.state not in workflow.CLOSED_STATES:
        ctx.client.patch_fields(ticket_id, {"System.State": STATE_ACTIVE})
        state_changed = True

    ctx.client.add_comment(ticket_id, body)

    after = ctx.client.get_work_items([ticket_id])[0]
    relations = ctx.client.get_work_item_relations(ticket_id)
    next_actions = workflow.compute(ctx.cfg, ctx.client, after, relations=relations)

    result = {
        "ticket_id": ticket_id,
        "previous_state": before.state,
        "new_state": after.state,
        "state_changed": state_changed,
        "comment_posted": body,
        "branch_suggestion": _branch_suggestion(after),
        "next_actions": workflow.to_json(next_actions),
    }
    trail.append_event(ctx.cfg.state_dir, ticket_id, "start_work",
                       args={"comment": body}, result=result)
    if state_changed:
        # Only shout when this actually moved a ticket — re-posting "Started"
        # on an already-Active ticket isn't a milestone worth announcing.
        share.started_work(ctx.cfg, ticket_id, title=after.title)
    return result


def post_comment(ticket_id: int, text: str) -> dict[str, Any]:
    """Post a comment formatted as a daily standup line.

    Use this for daily progress notes — the hygiene rules check that every
    Active ticket gets one comment per business day. The comment is posted
    verbatim; vamos doesn't add prefixes so Claude can format it freely.
    """
    if not text or not text.strip():
        return {"error": "text is required"}
    ctx = get_ctx()
    items = ctx.client.get_work_items([ticket_id])
    if not items:
        return {"error": f"Ticket {ticket_id} not found"}
    ctx.client.add_comment(ticket_id, text)
    item = items[0]
    next_actions = workflow.compute(ctx.cfg, ctx.client, item)
    result = {
        "ticket_id": ticket_id,
        "posted": text,
        "state": item.state,
        "next_actions": workflow.to_json(next_actions),
    }
    trail.append_event(ctx.cfg.state_dir, ticket_id, "post_comment",
                       args={"text": text}, result={"posted": True})
    return result


def close_ticket(
    ticket_id: int,
    resolution: str = DEFAULT_RESOLUTION,
    comment: str | None = None,
    target_state: str = STATE_RESOLVED,
    confirm: bool = False,
) -> dict[str, Any]:
    """Move a ticket to Resolved/Closed with a resolution reason.

    SAFETY: returns a dry-run preview unless `confirm=True`. The preview
    lists exactly what would change so a human can sanity-check before
    Claude re-calls with confirm=True.

    target_state defaults to "Resolved" — many ADO templates require an
    intermediate Resolved step before Closed. Pass target_state="Closed"
    if your template skips Resolved.
    """
    ctx = get_ctx()
    items = ctx.client.get_work_items([ticket_id])
    if not items:
        return {"error": f"Ticket {ticket_id} not found"}
    item = items[0]

    if item.state in workflow.CLOSED_STATES:
        return {
            "ticket_id": ticket_id,
            "noop": True,
            "reason": f"Ticket is already {item.state}",
            "state": item.state,
        }

    plan = {
        "ticket_id": ticket_id,
        "current_state": item.state,
        "would_set_state": target_state,
        "would_set_resolution": resolution,
        "would_post_comment": comment,
        "title": item.title,
    }

    if not confirm:
        return {
            **plan,
            "preview": True,
            "message": (
                "Dry run. To apply, re-call close_ticket with confirm=True. "
                "Verify with the human first if anything in the plan looks off."
            ),
        }

    # Apply
    fields: dict[str, Any] = {"System.State": target_state}
    if resolution:
        fields["Microsoft.VSTS.Common.ResolvedReason"] = resolution
    ctx.client.patch_fields(ticket_id, fields)
    if comment:
        ctx.client.add_comment(ticket_id, comment)

    after = ctx.client.get_work_items([ticket_id])[0]
    result = {
        **plan,
        "applied": True,
        "new_state": after.state,
    }
    trail.append_event(ctx.cfg.state_dir, ticket_id, "close_ticket",
                       args={"resolution": resolution, "target_state": target_state},
                       result={"new_state": after.state})
    share.closed_ticket(ctx.cfg, ticket_id, title=item.title, resolution=resolution)
    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _branch_suggestion(item: WorkItem) -> str:
    """Suggest a git branch name following HYGIENE_BRANCH_PATTERN: feature/<id>-<slug>."""
    type_prefix = {"Bug": "bugfix", "Hotfix": "hotfix"}.get(item.type, "feature")
    slug = "".join(c.lower() if c.isalnum() else "-" for c in item.title)
    while "--" in slug:
        slug = slug.replace("--", "-")
    slug = slug.strip("-")[:50]
    return f"{type_prefix}/{item.id}-{slug}"


def _summarize_pr_links(relations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for r in relations:
        if r.get("rel") != "ArtifactLink":
            continue
        url = r.get("url") or ""
        if "PullRequestId" not in url:
            continue
        try:
            pr_id = int(url.rsplit("%2F", 1)[-1])
        except (ValueError, IndexError):
            continue
        out.append({"pr_id": pr_id, "url": url})
    return out


def _summarize_comments(comments: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    """Return the most recent `limit` comments, newest last, with HTML stripped."""
    sorted_comments = sorted(
        comments, key=lambda c: c.get("createdDate") or "", reverse=False,
    )
    out = []
    for c in sorted_comments[-limit:]:
        author = c.get("createdBy", {})
        out.append({
            "author": author.get("displayName") or author.get("uniqueName"),
            "created": c.get("createdDate"),
            "text": _strip_html(c.get("text") or "")[:500],
        })
    return out


def _light_hint(item: WorkItem) -> str:
    if item.state in workflow.NEW_STATES:
        return "start_work"
    if item.state in workflow.ACTIVE_STATES:
        return "post_comment_or_open_pr"
    if item.state in workflow.RESOLVED_STATES:
        return "run_hygiene_check_then_close"
    return "get_ticket_for_details"


def _strip_html(text: str) -> str:
    import re as _re
    if not text:
        return ""
    return _re.sub(r"<[^>]+>", "", text).replace("&nbsp;", " ").strip()
