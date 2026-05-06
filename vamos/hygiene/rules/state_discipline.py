"""state-discipline — Two states only (Active + Blocked). One Active per engineer.

Per Jeff's spec: QA / PR Ready states are deprecated; Active means working on it,
Blocked means waiting; one Active at a time per engineer.
"""
from __future__ import annotations

from collections import defaultdict

from ...config import Config
from ...core.report import Finding
from ...core.snapshot import ACTIVE_STATES, DEPRECATED_STATES, TeamSnapshot

RULE_ID = "state-discipline"


def check(snapshot: TeamSnapshot, cfg: Config) -> list[Finding]:
    findings: list[Finding] = []

    # 1) Tickets in deprecated states (QA, PR Ready, etc.)
    for w in snapshot.work_items:
        if w.state in DEPRECATED_STATES:
            findings.append(Finding(
                rule_id=RULE_ID,
                severity="should-fix",
                engineer=w.assigned_to,
                ticket_id=w.id,
                ticket_url=w.url,
                ticket_title=w.title,
                message=f"State '{w.state}' is deprecated — go straight to Closed when done. "
                        f"Code Review state is automated by ADO when a PR is submitted.",
                suggested_comment=(
                    f"Heads up — '{w.state}' is deprecated per Jeff's standards. "
                    "Move to Closed when work is done; Code Review is automated."
                ),
            ))

    # 2) More than 1 Active per engineer
    by_eng: dict[str, list] = defaultdict(list)
    for w in snapshot.active_items():
        if w.assigned_to:
            by_eng[w.assigned_to].append(w)
    for eng, items in by_eng.items():
        if len(items) > 1:
            ids = ", ".join(f"#{w.id}" for w in items)
            findings.append(Finding(
                rule_id=RULE_ID,
                severity="should-fix",
                engineer=eng,
                ticket_id=None,
                ticket_url=None,
                message=f"{len(items)} tickets in Active state ({ids}). "
                        "Move all but one to Blocked or Groomed/Ready — one Active at a time.",
            ))

    return findings
