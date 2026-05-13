"""active-overload — engineer has >1 ticket in Active. Per board standards,
one Active at a time keeps focus tight.

Overlaps with hygiene's state-discipline rule, but framed advisory instead
of standards-violation: this is "consider re-focusing", not "fix this".
"""
from __future__ import annotations

from collections import defaultdict

from ...config import Config
from ...core.report import Finding
from ...core.snapshot import TeamSnapshot

RULE_ID = "active-overload"


def check(snapshot: TeamSnapshot, cfg: Config) -> list[Finding]:
    findings: list[Finding] = []

    by_eng: dict[str, list] = defaultdict(list)
    for w in snapshot.active_items():
        if w.assigned_to:
            by_eng[w.assigned_to].append(w)

    for eng, items in by_eng.items():
        if len(items) <= 1:
            continue
        ids = ", ".join(f"#{w.id}" for w in items[:5])
        more = f" (+{len(items) - 5} more)" if len(items) > 5 else ""
        findings.append(Finding(
            rule_id=RULE_ID,
            severity="info",
            engineer=eng,
            ticket_id=None,
            ticket_url=None,
            message=(
                f"{len(items)} tickets in Active state ({ids}{more}). "
                "Consider keeping just one in Active — move the rest to Blocked or back to To Do."
            ),
        ))

    return findings
