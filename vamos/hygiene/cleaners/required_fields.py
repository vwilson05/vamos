"""required-fields cleaner.

For tickets missing one or more of: assignee, story points, start date, target date.
- Assignee: cannot infer safely — surface as a question only (low confidence, no actions)
- Story points: infer from the median SP of recently-closed similar-type tickets
- Start date: today (when the ticket is in an Active state)
- Target date: start + 5 working days (heuristic; user can adjust)
"""
from __future__ import annotations

from datetime import date, timedelta
from statistics import median
from typing import Iterable

from ...cleaner import Action, Proposal
from ...config import Config
from ...core.report import Finding
from ...core.snapshot import ACTIVE_STATES, CLOSED_STATES, TeamSnapshot

RULE_ID = "required-fields"

F_POINTS = "Microsoft.VSTS.Scheduling.StoryPoints"
F_START = "Microsoft.VSTS.Scheduling.StartDate"
F_TARGET = "Microsoft.VSTS.Scheduling.TargetDate"


def propose(finding: Finding, snapshot: TeamSnapshot, cfg: Config) -> Proposal | None:
    if not finding.ticket_id:
        return None
    w = next((x for x in snapshot.work_items if x.id == finding.ticket_id), None)
    if not w:
        return None

    fields_to_set: dict[str, object] = {}
    rationale_bits: list[str] = []

    # Story points
    if not w.raw_fields.get(F_POINTS):
        sp = _infer_story_points(snapshot.work_items, w.type)
        if sp is not None:
            fields_to_set[F_POINTS] = sp
            rationale_bits.append(
                f"story points = {sp} (median of recently-closed {w.type}s)"
            )

    # Start date — only if Active
    if w.state in ACTIVE_STATES and not w.raw_fields.get(F_START):
        today = date.today().isoformat()
        fields_to_set[F_START] = today
        rationale_bits.append(f"start date = today ({today})")

    # Target date — start + 5 working days (or today + 5 if start is now today)
    if not w.raw_fields.get(F_TARGET) and w.state in ACTIVE_STATES:
        target = date.today() + timedelta(days=7)
        fields_to_set[F_TARGET] = target.isoformat()
        rationale_bits.append(f"target date = {target.isoformat()} (start + 7 days)")

    if not fields_to_set:
        # Only missing assignee or other field we can't safely auto-fill
        return None

    return Proposal(
        finding=finding,
        rationale="; ".join(rationale_bits),
        actions=[Action(kind="set_fields", work_item_id=w.id,
                        payload={"fields": fields_to_set})],
        confidence="medium",
    )


def _infer_story_points(items: Iterable, ticket_type: str) -> int | None:
    """Return the median SP of recently-closed tickets of the same type, capped to a sane range."""
    sps: list[float] = []
    for w in items:
        if w.type != ticket_type:
            continue
        if w.state not in CLOSED_STATES:
            continue
        sp = w.raw_fields.get(F_POINTS)
        if isinstance(sp, (int, float)) and sp > 0:
            sps.append(float(sp))
    if not sps:
        return None
    val = median(sps)
    # Round to nearest reasonable integer
    rounded = max(1, min(13, int(round(val))))
    return rounded
