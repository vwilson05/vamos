"""required-fields — Every story needs points, start date, target date, assignee.

Per Jeff's spec: 1 SP = 1 hour. Start and target dates set when work begins.
"""
from __future__ import annotations

from ...config import Config
from ...core.report import Finding
from ...core.snapshot import CLOSED_STATES, TODO_STATES, TeamSnapshot

RULE_ID = "required-fields"

# Type fields ADO uses
F_POINTS = "Microsoft.VSTS.Scheduling.StoryPoints"
F_START = "Microsoft.VSTS.Scheduling.StartDate"
F_TARGET = "Microsoft.VSTS.Scheduling.TargetDate"


def check(snapshot: TeamSnapshot, cfg: Config) -> list[Finding]:
    findings: list[Finding] = []

    for w in snapshot.work_items:
        # Skip closed and not-yet-started items for some checks
        if w.state in CLOSED_STATES:
            continue
        if w.type not in ("User Story", "Story", "Bug", "Issue"):
            continue

        missing: list[str] = []
        if not w.assigned_to:
            missing.append("assignee")
        if not w.raw_fields.get(F_POINTS):
            missing.append("story points")
        # Start/target dates only required once the ticket is being worked or queued
        if w.state not in TODO_STATES:
            if not w.raw_fields.get(F_START):
                missing.append("start date")
            if not w.raw_fields.get(F_TARGET):
                missing.append("target date")

        if not missing:
            continue
        findings.append(Finding(
            rule_id=RULE_ID,
            severity="should-fix",
            engineer=w.assigned_to,
            ticket_id=w.id,
            ticket_url=w.url,
            ticket_title=w.title,
            message=f"Missing required field(s): {', '.join(missing)}.",
            suggested_comment=(
                f"Heads up — this ticket is missing {', '.join(missing)}. "
                "All stories need points (1 SP = 1 hour), a start date, and a target date."
            ),
        ))

    return findings
