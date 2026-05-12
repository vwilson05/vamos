"""workbook-sent-but-open — if a recent comment indicates the QA workbook was
shared with the BA, the dev ticket should usually be closed (a new ticket gets
opened if BA feedback requires changes).

Heuristic: scan comments from the last 3 days on Active/Blocked tickets for
phrases like "sent the workbook", "shared QA workbook", "workbook posted".
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from ...config import Config
from ...core.report import Finding
from ...core.snapshot import ACTIVE_STATES, BLOCKED_STATES, TeamSnapshot

RULE_ID = "workbook-sent-but-open"

_WORKBOOK_PATTERNS = [
    re.compile(r"\b(qa\s+)?workbook[s]?\s+(sent|shared|posted|uploaded|delivered)\b", re.I),
    re.compile(r"\b(sent|shared|posted|uploaded|delivered)\s+(the\s+)?(qa\s+)?workbook\b", re.I),
    re.compile(r"\bworkbook\b.*\bto\s+ba\b", re.I),
    re.compile(r"\bba\b.*\bworkbook\b", re.I),
]


def check(snapshot: TeamSnapshot, cfg: Config) -> list[Finding]:
    findings: list[Finding] = []
    cutoff = datetime.now(timezone.utc) - timedelta(days=3)

    for w in snapshot.work_items:
        if w.state not in (ACTIVE_STATES | BLOCKED_STATES):
            continue
        comments = snapshot.comments_by_item.get(w.id, [])
        recent = [c for c in comments if c.created >= cutoff]
        hit = None
        for c in recent:
            if any(p.search(c.text) for p in _WORKBOOK_PATTERNS):
                hit = c
                break
        if not hit:
            continue
        findings.append(Finding(
            rule_id=RULE_ID,
            severity="should-fix",
            engineer=w.assigned_to,
            ticket_id=w.id,
            ticket_url=w.url,
            ticket_title=w.title,
            message=(
                f"Workbook appears sent on {hit.created.date().isoformat()} — "
                "consider closing this ticket. Open a new one for any follow-up work."
            ),
            suggested_comment=(
                "Heads up — looks like the QA workbook was sent. "
                "Per board standards, close this ticket once the workbook is delivered; "
                "open a new ticket if BA feedback requires additional changes."
            ),
        ))

    return findings
