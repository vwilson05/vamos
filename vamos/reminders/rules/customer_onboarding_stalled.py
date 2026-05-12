"""customer-onboarding-stalled — tickets tagged "Customer Onboarding" that
have been in Active/Blocked >10 days with no recent owner comment.

Onboarding tickets are time-sensitive — BAs and CS are waiting. If one
goes silent for 10+ days, that's worth surfacing.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ...config import Config
from ...core.report import Finding
from ...core.snapshot import ACTIVE_STATES, BLOCKED_STATES, TeamSnapshot

RULE_ID = "customer-onboarding-stalled"

_ONBOARDING_TAGS = {"customer onboarding", "onboarding"}


def check(snapshot: TeamSnapshot, cfg: Config) -> list[Finding]:
    findings: list[Finding] = []
    now = datetime.now(timezone.utc)

    for w in snapshot.work_items:
        if w.state not in (ACTIVE_STATES | BLOCKED_STATES):
            continue
        tags_lc = {t.lower() for t in (w.tags or [])}
        if not (tags_lc & _ONBOARDING_TAGS):
            continue

        changed = w.raw_fields.get("System.ChangedDate")
        if not changed:
            continue
        try:
            cd = datetime.fromisoformat(changed.replace("Z", "+00:00"))
        except ValueError:
            continue

        age = (now - cd).days
        if age <= 10:
            continue

        comments = snapshot.comments_by_item.get(w.id, [])
        own_recent = [
            c for c in comments
            if (c.author_email == w.assigned_to or c.author == w.assigned_to)
            and c.created >= now - timedelta(days=5)
        ]
        if own_recent:
            continue

        findings.append(Finding(
            rule_id=RULE_ID,
            severity="should-fix",
            engineer=w.assigned_to,
            ticket_id=w.id,
            ticket_url=w.url,
            ticket_title=w.title,
            message=(
                f"Customer Onboarding ticket in {w.state} for {age}d "
                "with no recent owner comment. BA / CS may be waiting — status update?"
            ),
            suggested_comment=(
                "This onboarding ticket has been quiet for a while. "
                "Please post a status update — BA and CS are tracking this."
            ),
        ))

    return findings
