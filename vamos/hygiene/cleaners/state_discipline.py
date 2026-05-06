"""state-discipline cleaner.

Two finding shapes from the rule:
  1. Single ticket in a deprecated state (QA, PR Ready) → propose moving to
     Closed (or Active) with a transitional comment.
  2. Engineer with >1 Active items → propose moving all but the most recently
     active to Blocked (reason: context switch).
"""
from __future__ import annotations

from datetime import datetime, timezone

from ...cleaner import Action, Proposal
from ...config import Config
from ...core.report import Finding
from ...core.snapshot import ACTIVE_STATES, DEPRECATED_STATES, TeamSnapshot

RULE_ID = "state-discipline"


def propose(finding: Finding, snapshot: TeamSnapshot, cfg: Config) -> Proposal | None:
    if finding.ticket_id:
        # Single-ticket deprecated-state finding
        w = next((x for x in snapshot.work_items if x.id == finding.ticket_id), None)
        if not w or w.state not in DEPRECATED_STATES:
            return None
        return Proposal(
            finding=finding,
            rationale=(
                f"Move from deprecated state '{w.state}' to Closed. "
                f"Per Jeff's spec, Code Review is automated when a PR is submitted; "
                f"engineers shouldn't sit in QA / PR Ready states manually."
            ),
            actions=[
                Action(kind="set_state", work_item_id=w.id, payload={"state": "Closed"}),
                Action(kind="comment", work_item_id=w.id, payload={
                    "text": (
                        "[vamos hygiene clean] Moving to Closed — '"
                        f"{w.state}' state is deprecated per board standards. "
                        "Reverse if the work isn't actually done."
                    )
                }),
            ],
            confidence="medium",  # closing is destructive — surface for human confirm
        )

    # Engineer-level "more than one Active" finding
    if not finding.engineer:
        return None
    active = [w for w in snapshot.work_items
              if w.assigned_to == finding.engineer and w.state in ACTIVE_STATES]
    if len(active) <= 1:
        return None

    # Pick the most recently changed item to remain Active; demote the rest.
    def _changed(w):
        try:
            return datetime.fromisoformat(
                (w.raw_fields.get("System.ChangedDate") or "").replace("Z", "+00:00")
            )
        except (ValueError, AttributeError):
            return datetime.min.replace(tzinfo=timezone.utc)

    active.sort(key=_changed, reverse=True)
    keep, *demote = active

    actions: list[Action] = []
    for w in demote:
        actions.append(Action(
            kind="set_state", work_item_id=w.id, payload={"state": "Blocked"},
        ))
        actions.append(Action(
            kind="comment", work_item_id=w.id, payload={
                "text": (
                    "[vamos hygiene clean] Moving to Blocked — engineer has multiple "
                    f"Active tickets (#{', #'.join(str(x.id) for x in active)}); keeping "
                    f"#{keep.id} Active per most-recent activity. Move back to Active "
                    "when ready to resume."
                )
            },
        ))

    return Proposal(
        finding=finding,
        rationale=(
            f"{finding.engineer} has {len(active)} Active tickets. "
            f"Keep #{keep.id} (most recently changed) Active; move the other "
            f"{len(demote)} to Blocked. One Active at a time per board standards."
        ),
        actions=actions,
        confidence="high",
    )
