"""resolution-on-close — Closed tickets must include a resolution note.

Per Jeff's spec: when a story closes, add a resolution to the Notes field
(System.Description / System.History or custom Notes field).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ...config import Config
from ...core.report import Finding
from ...core.snapshot import CLOSED_STATES, TeamSnapshot

RULE_ID = "resolution-on-close"

# Fields ADO commonly uses for "resolution" / "notes"
RESOLUTION_FIELDS = [
    "Custom.Notes",  # team-specific custom field
    "Microsoft.VSTS.Common.ResolvedReason",
    "Microsoft.VSTS.Common.Resolution",
    "System.Reason",
]


def check(snapshot: TeamSnapshot, cfg: Config) -> list[Finding]:
    findings: list[Finding] = []
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)

    for w in snapshot.closed_recently(cutoff):
        if w.state not in CLOSED_STATES:
            continue
        if any((w.raw_fields.get(f) or "").strip() for f in RESOLUTION_FIELDS):
            continue
        # System.Reason in ADO defaults to a value when closed — distinguish
        # between auto-set values and meaningful resolution text.
        reason = (w.raw_fields.get("System.Reason") or "").strip().lower()
        if reason and reason not in ("done", "completed", "fixed", "as designed", ""):
            continue
        findings.append(Finding(
            rule_id=RULE_ID,
            severity="should-fix",
            engineer=w.assigned_to,
            ticket_id=w.id,
            ticket_url=w.url,
            ticket_title=w.title,
            message=(
                "Closed without a resolution note. Add a Notes entry describing what was "
                "done / how it was resolved before final close."
            ),
        ))

    return findings
