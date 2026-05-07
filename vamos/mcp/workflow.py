"""Compute next-action hints from a ticket's current state.

Every MCP response carries a `next_actions` field. Claude doesn't need to
remember where it is in the flow — each call recomputes from ground truth
(ADO state + linked PRs + recent trail).

The list is opinionated: 1-3 concrete tool calls Claude should consider next,
ordered most-likely first. Empty list = ticket looks done.
"""
from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass
from typing import Any

from ..ado import ADOClient, WorkItem
from ..config import Config
from . import trail

log = logging.getLogger(__name__)

# State buckets — ADO has dozens of states across templates; we group them.
NEW_STATES = {"New", "To Do", "Proposed", "Approved"}
ACTIVE_STATES = {"Active", "In Progress", "Committed", "Doing"}
RESOLVED_STATES = {"Resolved", "In Review"}
CLOSED_STATES = {"Closed", "Done", "Removed", "Completed"}
BLOCKED_TAG_PATTERNS = [re.compile(r"\bblocked\b", re.I)]


@dataclass
class NextAction:
    tool: str
    why: str
    args: dict[str, Any] | None = None  # suggested args (Claude can override)


def compute(
    cfg: Config,
    client: ADOClient,
    item: WorkItem,
    relations: list[dict[str, Any]] | None = None,
) -> list[NextAction]:
    """Read state + relations + trail and produce next_actions."""
    relations = relations if relations is not None else client.get_work_item_relations(item.id)
    pr_links = _extract_pr_links(relations)
    events = trail.read_events(cfg.state_dir, item.id, limit=20)

    state = item.state
    actions: list[NextAction] = []

    # Closed/Done — nothing to do.
    if state in CLOSED_STATES:
        return []

    # Resolved — verify hygiene + maybe close.
    if state in RESOLVED_STATES:
        if not trail.has_recent_tool(events, "run_hygiene_check"):
            actions.append(NextAction(
                tool="run_hygiene_check",
                why="Ticket is Resolved/In Review — verify hygiene before close",
                args={"ticket_id": item.id},
            ))
        actions.append(NextAction(
            tool="close_ticket",
            why="Ready to close once hygiene is clean. Requires confirm=True.",
            args={"ticket_id": item.id, "confirm": False},
        ))
        return actions

    # New — start work.
    if state in NEW_STATES:
        actions.append(NextAction(
            tool="start_work",
            why="Ticket is in a new state and unblocked — move to Active and post a daily comment",
            args={"ticket_id": item.id},
        ))
        return actions

    # Active — depends on whether there's a PR.
    if state in ACTIVE_STATES:
        if not pr_links:
            actions.append(NextAction(
                tool="post_comment",
                why="No daily comment yet today — keep the board honest",
                args={"ticket_id": item.id, "text": "(progress note)"},
            ))
            actions.append(NextAction(
                tool="open_pr",
                why="Active ticket has no linked PR yet — open one when code is ready",
                args={"ticket_id": item.id, "repo": "(repo name)", "source_branch": "(branch)"},
            ))
            return actions

        # Has a PR — review it, then move to resolved.
        latest_pr = pr_links[-1]
        if not trail.has_recent_tool(events, "run_pr_review"):
            actions.append(NextAction(
                tool="run_pr_review",
                why=f"PR #{latest_pr['pr_id']} is linked but hasn't been reviewed yet",
                args={"pr_id": latest_pr["pr_id"], "repo": latest_pr["repo"]},
            ))
        actions.append(NextAction(
            tool="run_hygiene_check",
            why="Run hygiene before transitioning to Resolved",
            args={"ticket_id": item.id},
        ))
        return actions

    # Anything else (custom states): suggest a hygiene check as a generic probe.
    actions.append(NextAction(
        tool="run_hygiene_check",
        why=f"Unrecognized state {state!r} — run hygiene to surface what's missing",
        args={"ticket_id": item.id},
    ))
    return actions


def to_json(actions: list[NextAction]) -> list[dict[str, Any]]:
    return [asdict(a) for a in actions]


def _extract_pr_links(relations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Pull (repo, pr_id) out of artifact-link relations on a work item.

    ADO encodes PR links as `vstfs:///Git/PullRequestId/<projectId>%2F<repoId>%2F<prId>`.
    We only need the PR id — repo can be re-resolved by the caller via PR APIs
    when needed. For now we expose just pr_id; tools that need the repo can
    call client.list_repo_names() and search.
    """
    out: list[dict[str, Any]] = []
    for r in relations:
        if r.get("rel") != "ArtifactLink":
            continue
        url = r.get("url") or ""
        if "PullRequestId" not in url:
            continue
        # Format: vstfs:///Git/PullRequestId/<projectId>%2F<repoId>%2F<prId>
        # PR id is the last segment after the final %2F.
        try:
            pr_id = int(url.rsplit("%2F", 1)[-1])
        except (ValueError, IndexError):
            continue
        # Repo id is the middle segment; we'd need a repo-id-to-name lookup
        # to resolve it. For now the caller passes repo explicitly.
        out.append({"pr_id": pr_id, "repo": "", "url": url})
    return out
