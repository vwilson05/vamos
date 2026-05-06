"""pr-linkage — Every PR ties to at least one ADO story or bug.

Open PRs without a linked work item are blockers. Closed stories without a PR
or a linked Code Review ticket are should-fix (manual code review is allowed
but must be tracked).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ...config import Config
from ...core.report import Finding
from ...core.snapshot import CLOSED_STATES, TeamSnapshot

RULE_ID = "pr-linkage"


def check(snapshot: TeamSnapshot, cfg: Config) -> list[Finding]:
    findings: list[Finding] = []

    # PR rules run against whatever PRs the snapshot already loaded. The runner
    # auto-discovers all repos when HYGIENE_REPOS is unset; if the user explicitly
    # set HYGIENE_REPOS=  (empty) to disable PR rules, snapshot.pull_requests
    # will simply be empty and these checks emit nothing.

    # 1) Open PRs without a linked work item
    for pr in snapshot.pull_requests:
        if pr.status != "active":
            continue
        if pr.work_item_ids:
            continue
        findings.append(Finding(
            rule_id=RULE_ID,
            severity="blocker",
            engineer=pr.author,
            ticket_id=None,
            ticket_url=pr.url,
            ticket_title=f"PR #{pr.id} ({pr.repo}): {pr.title}",
            message=f"PR #{pr.id} in {pr.repo} has no linked ADO work item. "
                    "Every PR must tie to a story or bug.",
        ))

    # 2) Closed stories with no PR and no Code Review child
    cutoff = datetime.now(timezone.utc) - timedelta(days=14)
    for w in snapshot.closed_recently(cutoff):
        if w.type not in ("User Story", "Story", "Task"):
            continue
        prs = snapshot.prs_for_item(w.id)
        if prs:
            continue
        # Check for a linked Code Review item via raw_fields["System.Tags"] or
        # parent/child relations — heuristic since we don't load relations here.
        # Phase 1: flag as should-fix; engineer can confirm or add the link.
        findings.append(Finding(
            rule_id=RULE_ID,
            severity="should-fix",
            engineer=w.assigned_to,
            ticket_id=w.id,
            ticket_url=w.url,
            ticket_title=w.title,
            message=(
                f"Closed story has no associated PR. If no PR was needed, "
                "create a linked Code Review ticket assigned to Jeff (with code block + summary)."
            ),
        ))

    return findings
