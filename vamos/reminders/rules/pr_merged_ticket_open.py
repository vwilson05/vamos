"""pr-merged-ticket-open — linked PR is completed but the ticket is still
Active/Blocked. The dev probably forgot to close.

Snapshot only loads *active* PRs, so we can't see merged ones directly. We
detect this via the ticket's recent comments — most merge bots leave an
automated comment like "PR #1234 was completed". If your bot doesn't do
that, this rule will be quiet (and that's fine — it's advisory).
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from ...config import Config
from ...core.report import Finding
from ...core.snapshot import ACTIVE_STATES, BLOCKED_STATES, TeamSnapshot

RULE_ID = "pr-merged-ticket-open"

_MERGE_PATTERNS = [
    re.compile(r"\bpull\s+request\s+#?\d+\s+(was\s+)?(completed|merged|approved\s+and\s+merged)\b", re.I),
    re.compile(r"\bpr\s+#?\d+\s+(was\s+)?(completed|merged)\b", re.I),
    re.compile(r"\bmerged\s+(into\s+)?(main|master|develop|prod)\b", re.I),
    re.compile(r"\bpushed\s+to\s+(prod|production)\b", re.I),
]


def check(snapshot: TeamSnapshot, cfg: Config) -> list[Finding]:
    findings: list[Finding] = []
    cutoff = datetime.now(timezone.utc) - timedelta(days=5)

    for w in snapshot.work_items:
        if w.state not in (ACTIVE_STATES | BLOCKED_STATES):
            continue
        comments = snapshot.comments_by_item.get(w.id, [])
        hit = None
        for c in comments:
            if c.created < cutoff:
                continue
            if any(p.search(c.text) for p in _MERGE_PATTERNS):
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
                f"PR appears merged on {hit.created.date().isoformat()} "
                f"but ticket is still {w.state}. Close it out?"
            ),
            suggested_comment=(
                "Looks like the linked PR is merged. "
                "If work is complete, please move this ticket to Resolved/Closed."
            ),
        ))

    return findings
