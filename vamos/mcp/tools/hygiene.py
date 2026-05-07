"""Hygiene MCP tool — runs board-standards rules against a single ticket.

Wraps the existing rule set (vamos.hygiene.rules.ALL_RULES) by building a
TeamSnapshot scoped to one work item. Findings are filtered to that ticket
so Claude gets a clean checklist of what's missing.

Read-only — never posts comments. Use the regular `vamos hygiene --clean`
CLI for AI-assisted fixes.
"""
from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from ...core.report import Finding
from ...core.snapshot import (
    Comment,
    PullRequest,
    TeamSnapshot,
    _parse_dt,
    _pr_from_api,
)
from ...hygiene.rules import ALL_RULES
from .. import trail
from .._context import get_ctx

log = logging.getLogger(__name__)


def run_hygiene_check(ticket_id: int) -> dict[str, Any]:
    """Run all hygiene rules against one ticket. Returns findings + summary.

    Builds a single-item TeamSnapshot:
      - the work item
      - its comments
      - any PRs linked to it (resolved via the ticket's relations)

    Findings from rules that scan multiple tickets (e.g. state-discipline)
    are filtered down to this ticket only.
    """
    ctx = get_ctx()
    items = ctx.client.get_work_items([ticket_id])
    if not items:
        return {"error": f"Ticket {ticket_id} not found"}
    item = items[0]

    # Comments
    try:
        raw_comments = ctx.client.get_work_item_comments(ticket_id)
    except Exception as exc:  # noqa: BLE001
        log.warning("hygiene-check: comment fetch failed for #%d: %s", ticket_id, exc)
        raw_comments = []
    comments = [_comment_from_api(ticket_id, c) for c in raw_comments]

    # Linked PRs — best effort across all repos in the project.
    # We resolve PR ids from the ticket's relations, then fetch each from the
    # right repo. If repo lookup fails we silently skip the PR-linkage rule.
    relations = ctx.client.get_work_item_relations(ticket_id)
    prs = _resolve_linked_prs(ctx, relations, ticket_id)

    snapshot = TeamSnapshot(
        area_path=item.raw_fields.get("System.AreaPath"),
        iteration_path=item.raw_fields.get("System.IterationPath"),
        work_items=[item],
        comments_by_item={ticket_id: comments},
        pull_requests=prs,
        snapshot_at=datetime.now(timezone.utc),
    )

    findings: list[Finding] = []
    for rule_id, fn in ALL_RULES:
        try:
            rule_findings = fn(snapshot, ctx.cfg)
        except Exception as exc:  # noqa: BLE001
            log.warning("hygiene-check: rule %s crashed on #%d: %s", rule_id, ticket_id, exc)
            continue
        # Filter to this ticket — some rules emit findings without ticket_id.
        for f in rule_findings:
            if f.ticket_id is None or f.ticket_id == ticket_id:
                findings.append(f)

    by_severity: dict[str, int] = {}
    for f in findings:
        by_severity[f.severity] = by_severity.get(f.severity, 0) + 1

    result = {
        "ticket_id": ticket_id,
        "title": item.title,
        "state": item.state,
        "finding_count": len(findings),
        "by_severity": by_severity,
        "findings": [_finding_to_dict(f) for f in findings],
        "is_clean": len(findings) == 0,
    }
    trail.append_event(
        ctx.cfg.state_dir, ticket_id, "run_hygiene_check",
        args={}, result={"finding_count": len(findings), "is_clean": result["is_clean"]},
    )
    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _comment_from_api(ticket_id: int, c: dict[str, Any]) -> Comment:
    author = c.get("createdBy") or {}
    return Comment(
        id=int(c.get("id", 0)),
        work_item_id=ticket_id,
        author=author.get("displayName", "?"),
        author_email=author.get("uniqueName"),
        text=c.get("text") or "",
        created=_parse_dt(c.get("createdDate")),
    )


def _resolve_linked_prs(ctx: Any, relations: list[dict[str, Any]], ticket_id: int) -> list[PullRequest]:
    """Pull each linked PR from its repo. Best-effort — skip on lookup failure."""
    pr_ids: list[int] = []
    for r in relations:
        if r.get("rel") != "ArtifactLink":
            continue
        url = r.get("url") or ""
        if "PullRequestId" not in url:
            continue
        try:
            pr_ids.append(int(url.rsplit("%2F", 1)[-1]))
        except (ValueError, IndexError):
            continue
    if not pr_ids:
        return []

    # Search across repos (small N — usually 1-3 PRs per ticket).
    try:
        repo_names = ctx.client.list_repo_names()
    except Exception:
        return []

    found: list[PullRequest] = []
    for repo in repo_names:
        try:
            active = ctx.client.list_active_prs(repo)
        except Exception:
            continue
        for p in active:
            if int(p.get("pullRequestId", 0)) in pr_ids:
                pr = _pr_from_api(p, repo)
                pr.work_item_ids = [ticket_id]
                found.append(pr)
        if len(found) == len(pr_ids):
            break
    return found


def _finding_to_dict(f: Finding) -> dict[str, Any]:
    """Convert a Finding dataclass to a JSON-friendly dict."""
    d = asdict(f)
    # asdict handles dates; we just need to make sure all values are JSON-safe.
    return {k: v for k, v in d.items() if v is not None}
