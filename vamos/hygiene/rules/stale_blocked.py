"""stale-blocked — Blocked tickets that haven't been commented on in N days.

Blocked is a holding state; if it sits with no updates the team should either
unblock or close it. Default threshold: HYGIENE_STALE_BLOCKED_DAYS (5 days).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ...config import Config
from ...core.report import Finding
from ...core.snapshot import BLOCKED_STATES, TeamSnapshot

RULE_ID = "stale-blocked"


def check(snapshot: TeamSnapshot, cfg: Config) -> list[Finding]:
    findings: list[Finding] = []
    cutoff = datetime.now(timezone.utc) - timedelta(days=cfg.hygiene_stale_blocked_days)

    for w in snapshot.work_items:
        if w.state not in BLOCKED_STATES:
            continue
        comments = snapshot.comments_by_item.get(w.id, [])
        recent = [c for c in comments if c.created >= cutoff]
        if recent:
            continue
        # Also use the System.ChangedDate as a fallback signal of activity
        changed = w.raw_fields.get("System.ChangedDate")
        if changed:
            try:
                changed_dt = datetime.fromisoformat(changed.replace("Z", "+00:00"))
                if changed_dt >= cutoff:
                    continue
            except ValueError:
                pass
        findings.append(Finding(
            rule_id=RULE_ID,
            severity="should-fix",
            engineer=w.assigned_to,
            ticket_id=w.id,
            ticket_url=w.url,
            ticket_title=w.title,
            message=(
                f"Blocked with no activity in {cfg.hygiene_stale_blocked_days}+ days. "
                "Either chase the unblock, escalate, or close if the work is no longer needed."
            ),
            suggested_comment=(
                f"This ticket has been Blocked with no comments for {cfg.hygiene_stale_blocked_days}+ days. "
                "Drop a quick status: who/what we're waiting on, ETA, or close if no longer relevant."
            ),
        ))

    return findings
