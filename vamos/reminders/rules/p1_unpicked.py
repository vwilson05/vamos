"""p1-unpicked — P1 tickets sitting in 'To Do' state without active pickup.

Only fires on state == 'To Do' (NOT 'New' — fresh-off-grooming items may not
be ready for pickup yet; To Do means groomed and waiting). Surfaces these as
team-level findings so the next person free can grab them.
"""
from __future__ import annotations

from datetime import datetime, timezone

from ...config import Config
from ...core.report import Finding
from ...core.snapshot import TeamSnapshot

RULE_ID = "p1-unpicked"


def check(snapshot: TeamSnapshot, cfg: Config) -> list[Finding]:
    findings: list[Finding] = []
    now = datetime.now(timezone.utc)

    for w in snapshot.work_items:
        if w.state != "To Do":
            continue
        if w.priority is None or w.priority > 1:
            continue

        age_days: int | None = None
        changed = w.raw_fields.get("System.ChangedDate")
        if changed:
            try:
                cd = datetime.fromisoformat(changed.replace("Z", "+00:00"))
                age_days = (now - cd).days
            except ValueError:
                pass

        age_part = f" (in To Do for {age_days}d)" if age_days is not None else ""
        assignee_part = f" — assigned to {w.assigned_to}" if w.assigned_to else " — unassigned"

        findings.append(Finding(
            rule_id=RULE_ID,
            severity="should-fix",
            engineer=None,  # team-level — anyone could pick this up
            ticket_id=w.id,
            ticket_url=w.url,
            ticket_title=w.title,
            message=(
                f"P1 in To Do{age_part}{assignee_part}. "
                "Highest priority — needs pickup."
            ),
            extra={"age_days": age_days, "priority": w.priority},
        ))

    return findings
