"""handoff-silent — the assignee changed in the last 3 days and the new
assignee hasn't commented yet. Either the handoff hasn't been acknowledged,
or it didn't actually happen.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ...config import Config
from ...core.report import Finding
from ...core.snapshot import ACTIVE_STATES, BLOCKED_STATES, TeamSnapshot

RULE_ID = "handoff-silent"


def check(snapshot: TeamSnapshot, cfg: Config) -> list[Finding]:
    findings: list[Finding] = []
    now = datetime.now(timezone.utc)
    handoff_cutoff = now - timedelta(days=3)

    for w in snapshot.work_items:
        if w.state not in (ACTIVE_STATES | BLOCKED_STATES):
            continue
        if not w.assigned_to:
            continue

        changed = w.raw_fields.get("System.ChangedDate")
        if not changed:
            continue
        try:
            cd = datetime.fromisoformat(changed.replace("Z", "+00:00"))
        except ValueError:
            continue
        if cd < handoff_cutoff:
            continue

        comments = snapshot.comments_by_item.get(w.id, [])
        own_recent = [
            c for c in comments
            if (c.author_email == w.assigned_to or c.author == w.assigned_to)
            and c.created >= cd - timedelta(hours=1)
        ]
        if own_recent:
            continue

        if not comments or all(
            c.author_email != w.assigned_to and c.author != w.assigned_to
            for c in comments
        ):
            findings.append(Finding(
                rule_id=RULE_ID,
                severity="info",
                engineer=w.assigned_to,
                ticket_id=w.id,
                ticket_url=w.url,
                ticket_title=w.title,
                message=(
                    f"Recently assigned/changed ({cd.date().isoformat()}) "
                    "but no comment yet from the assignee. Acknowledge the handoff?"
                ),
                suggested_comment=(
                    "Heads up — you're newly on this ticket. "
                    "Drop a quick comment to acknowledge the handoff and plan next steps."
                ),
            ))

    return findings
