"""resolution-on-close cleaner.

Generates a 1-2 sentence resolution note for a closed ticket that's missing one.
Reads the ticket's recent comments + linked PR descriptions and asks Claude to
summarize "what was done."
"""
from __future__ import annotations

import logging

from ...cleaner import Action, Proposal
from ...config import Config
from ...core.report import Finding
from ...core.snapshot import TeamSnapshot
from ...llm import call_claude, LLMError

log = logging.getLogger(__name__)

RULE_ID = "resolution-on-close"


def propose(finding: Finding, snapshot: TeamSnapshot, cfg: Config) -> Proposal | None:
    if not finding.ticket_id:
        return None
    w = next((x for x in snapshot.work_items if x.id == finding.ticket_id), None)
    if not w:
        return None

    comments = snapshot.comments_by_item.get(w.id, [])
    comment_lines = [
        f"  [{c.created.strftime('%m-%d')} · {c.author}] {c.text[:300]}"
        for c in comments[-5:]
    ]
    prs = snapshot.prs_for_item(w.id)
    pr_lines = [f"  PR #{pr.id} ({pr.repo}) — {pr.title}" for pr in prs]
    description = (w.description or "").strip()[:500]

    prompt = f"""You are vamos, filling in a missing resolution note on a closed Azure DevOps ticket.

Write a 1-2 sentence resolution from the assignee's perspective summarizing WHAT WAS DONE. Factual, past tense, ~200 chars max. If the ticket has no clear signal of completion, say "Closed — see linked PR for resolution." or similar.

Ticket: #{w.id} — {w.title}
State: {w.state}  ·  Type: {w.type}
Assignee: {w.assigned_to or '(unassigned)'}

Description (excerpt):
{description or '(none)'}

Recent comments (most recent last):
{chr(10).join(comment_lines) if comment_lines else '  (none)'}

Linked PRs:
{chr(10).join(pr_lines) if pr_lines else '  (none)'}

Output ONLY the resolution text — no preamble, no quotes, no markdown.
"""

    try:
        suggested = call_claude(prompt, claude_bin=cfg.claude_bin, timeout=120).strip()
        if suggested.startswith('"') and suggested.endswith('"'):
            suggested = suggested[1:-1]
        confidence = "medium"
    except LLMError as exc:
        log.warning("resolution-on-close cleaner: LLM call failed (%s); using fallback", exc)
        if prs:
            suggested = f"Closed — see linked PR(s) for implementation."
        else:
            suggested = "Closed — work completed; no resolution note recorded."
        confidence = "low"

    final = f"[vamos hygiene clean] {suggested}"

    return Proposal(
        finding=finding,
        rationale=f"Generate resolution note from {len(comments)} comment(s) + {len(prs)} linked PR(s).",
        actions=[Action(kind="comment", work_item_id=w.id, payload={"text": final})],
        confidence=confidence,
    )
