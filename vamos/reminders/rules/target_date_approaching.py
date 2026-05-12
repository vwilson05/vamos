"""target-date-approaching — target date is within 2 business days, and the
ticket hasn't had a progress comment in the last 2 days.

Soft nudge: "you've got a deadline coming, where are you?" — without firing
on every ticket with a near target date (only the silent ones).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ...config import Config
from ...core.report import Finding
from ...core.snapshot import ACTIVE_STATES, BLOCKED_STATES, CLOSED_STATES, TeamSnapshot

RULE_ID = "target-date-approaching"


def check(snapshot: TeamSnapshot, cfg: Config) -> list[Finding]:
    findings: list[Finding] = []
    now = datetime.now(timezone.utc)
    quiet_cutoff = now - timedelta(days=2)

    for w in snapshot.work_items:
        if w.state in CLOSED_STATES:
            continue
        if w.state not in (ACTIVE_STATES | BLOCKED_STATES):
            continue

        target = w.raw_fields.get("Microsoft.VSTS.Scheduling.TargetDate")
        if not target:
            continue
        try:
            td = datetime.fromisoformat(target.replace("Z", "+00:00"))
        except ValueError:
            continue

        days_until = (td.date() - now.date()).days
        if days_until < 0 or days_until > 2:
            continue

        comments = snapshot.comments_by_item.get(w.id, [])
        own = [c for c in comments if c.author_email == w.assigned_to or c.author == w.assigned_to]
        recent = [c for c in own if c.created >= quiet_cutoff]
        if recent:
            continue

        findings.append(Finding(
            rule_id=RULE_ID,
            severity="should-fix",
            engineer=w.assigned_to,
            ticket_id=w.id,
            ticket_url=w.url,
            ticket_title=w.title,
            message=(
                f"Target date {td.date().isoformat()} (~{days_until}d away), "
                "no progress comment in the last 2 days. Quick status update?"
            ),
            suggested_comment=(
                f"Target date is {td.date().isoformat()} — please drop a quick status "
                "(progress, blockers, ETA) so we know where this stands."
            ),
        ))

    return findings
