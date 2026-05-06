"""stale-blocked cleaner.

For tickets sitting in Blocked > N days with no recent comments. Two paths:
- If linked-PR has activity → propose a "PR review pending" status comment
- Otherwise → propose a "still blocked, no movement — escalating" comment

Conservative: never auto-closes. Always proposes a comment, not a state change.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from ...cleaner import Action, Proposal
from ...config import Config
from ...core.report import Finding
from ...core.snapshot import TeamSnapshot
from ...llm import call_claude, LLMError

log = logging.getLogger(__name__)

RULE_ID = "stale-blocked"


def propose(finding: Finding, snapshot: TeamSnapshot, cfg: Config) -> Proposal | None:
    if not finding.ticket_id:
        return None
    w = next((x for x in snapshot.work_items if x.id == finding.ticket_id), None)
    if not w:
        return None

    comments = snapshot.comments_by_item.get(w.id, [])
    last_comment = comments[-1] if comments else None
    days_since = None
    if last_comment:
        days_since = (datetime.now(timezone.utc) - last_comment.created).days

    prs = snapshot.prs_for_item(w.id)
    description = (w.description or "").strip()[:500]

    prompt = f"""You are vamos, posting a status update on an Azure DevOps ticket that has been in Blocked state for {cfg.hygiene_stale_blocked_days}+ days with no recent comments.

Write a 1-2 sentence status comment from the assignee's perspective. Be neutral. Acknowledge the staleness, name the blocker (if you can identify one from the description / linked PRs), and propose a next step (escalate / chase / close as no longer relevant). 200 chars max.

Ticket: #{w.id} — {w.title}
State: Blocked  ·  Days since last comment: {days_since if days_since is not None else '(none)'}

Description (excerpt):
{description or '(none)'}

Linked PRs:
{chr(10).join(f"  PR #{pr.id} ({pr.repo}) — {pr.title}" for pr in prs) if prs else '  (none)'}

Output ONLY the comment text — no preamble, no quotes, no markdown.
"""

    try:
        suggested = call_claude(prompt, claude_bin=cfg.claude_bin, timeout=120).strip()
        if suggested.startswith('"') and suggested.endswith('"'):
            suggested = suggested[1:-1]
        confidence = "medium"
    except LLMError as exc:
        log.warning("stale-blocked cleaner: LLM call failed (%s); using fallback", exc)
        suggested = (
            f"Still Blocked with no movement in {days_since or '?'} days — chasing the blocker."
        )
        confidence = "low"

    final = f"[vamos hygiene clean] {suggested}"

    return Proposal(
        finding=finding,
        rationale=f"Post a chase-the-blocker status comment ({days_since or '?'}d since last activity).",
        actions=[Action(kind="comment", work_item_id=w.id, payload={"text": final})],
        confidence=confidence,
    )
