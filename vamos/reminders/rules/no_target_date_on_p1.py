"""no-target-date-on-p1 — Active P1 tickets without a target date.

Per board standards, every story needs a target date. P1s especially —
leadership tracks these. Soft reminder, not a blocker.
"""
from __future__ import annotations

from ...config import Config
from ...core.report import Finding
from ...core.snapshot import ACTIVE_STATES, BLOCKED_STATES, TeamSnapshot

RULE_ID = "no-target-date-on-p1"


def check(snapshot: TeamSnapshot, cfg: Config) -> list[Finding]:
    findings: list[Finding] = []

    for w in snapshot.work_items:
        if w.state not in (ACTIVE_STATES | BLOCKED_STATES):
            continue
        if w.priority is None or w.priority > 1:
            continue
        if w.raw_fields.get("Microsoft.VSTS.Scheduling.TargetDate"):
            continue

        findings.append(Finding(
            rule_id=RULE_ID,
            severity="should-fix",
            engineer=w.assigned_to,
            ticket_id=w.id,
            ticket_url=w.url,
            ticket_title=w.title,
            message=(
                f"P1 in {w.state} with no target date. "
                "Set one so leadership can track it."
            ),
            suggested_comment=(
                "P1 tickets should have a target date set. "
                "Please add one (start date + target date, per board standards)."
            ),
        ))

    return findings
