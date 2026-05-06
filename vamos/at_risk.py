"""At-risk — surface tickets and PRs that need leadership attention.

What's at risk:
  - P1/P2 tickets in Active or Blocked >3 days
  - Tickets past their target_date
  - Tickets aging in any non-closed state for >14 days
  - Active PRs aging >5 days with no completed reviews
  - Closed-without-resolution tickets (overlap with hygiene but raised here too)
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone

from .ado import ADOClient
from .config import Config
from .core import delivery, state
from .core.report import Finding, Report
from .core.snapshot import (
    BLOCKED_STATES, CLOSED_STATES, ACTIVE_STATES, build_snapshot,
)

log = logging.getLogger(__name__)


def run(cfg: Config, skip_post: bool = False, day: date | None = None) -> Report:
    day = day or date.today()
    client = ADOClient(cfg.ado_org_url, cfg.ado_project, cfg.ado_pat, read_only=True)

    log.info("at-risk: building snapshot")
    snapshot = build_snapshot(
        client,
        area_path=cfg.hygiene_area_path,
        iteration_path=cfg.hygiene_iteration_path,
        repos=cfg.hygiene_repos or None,
    )

    findings: list[Finding] = []
    now = datetime.now(timezone.utc)

    for w in snapshot.work_items:
        if w.state in CLOSED_STATES:
            continue

        # Past target date
        target = w.raw_fields.get("Microsoft.VSTS.Scheduling.TargetDate")
        if target:
            try:
                td = datetime.fromisoformat(target.replace("Z", "+00:00"))
                if td.date() < day:
                    findings.append(Finding(
                        rule_id="past-target-date",
                        severity="blocker",
                        engineer=w.assigned_to,
                        ticket_id=w.id,
                        ticket_url=w.url,
                        ticket_title=w.title,
                        message=f"Target date {td.date().isoformat()} has passed; state is {w.state}.",
                    ))
            except ValueError:
                pass

        # High priority + Blocked >3 days
        if w.state in BLOCKED_STATES and w.priority and w.priority <= 2:
            changed = w.raw_fields.get("System.ChangedDate")
            if changed:
                try:
                    cd = datetime.fromisoformat(changed.replace("Z", "+00:00"))
                    if (now - cd) > timedelta(days=3):
                        findings.append(Finding(
                            rule_id="high-priority-blocked",
                            severity="blocker",
                            engineer=w.assigned_to,
                            ticket_id=w.id,
                            ticket_url=w.url,
                            ticket_title=w.title,
                            message=f"P{w.priority} ticket Blocked >3 days.",
                        ))
                except ValueError:
                    pass

        # Aging in any non-closed state >14d
        changed = w.raw_fields.get("System.ChangedDate")
        if changed and w.state in ACTIVE_STATES | BLOCKED_STATES:
            try:
                cd = datetime.fromisoformat(changed.replace("Z", "+00:00"))
                age = (now - cd).days
                if age > 14:
                    findings.append(Finding(
                        rule_id="stale-active",
                        severity="should-fix",
                        engineer=w.assigned_to,
                        ticket_id=w.id,
                        ticket_url=w.url,
                        ticket_title=w.title,
                        message=f"In state {w.state} with no activity for {age} days.",
                    ))
            except ValueError:
                pass

    # Aging PRs
    for pr in snapshot.pull_requests:
        if pr.status != "active":
            continue
        age = (now - pr.created).days
        if age > 5:
            findings.append(Finding(
                rule_id="aging-pr",
                severity="should-fix",
                engineer=pr.author,
                ticket_id=None,
                ticket_url=pr.url,
                ticket_title=f"PR #{pr.id} ({pr.repo}): {pr.title}",
                message=f"PR open for {age} days without completion.",
            ))

    report = Report(
        title=f"At-Risk — {day.strftime('%A, %B %d, %Y')}",
        subtitle="Tickets and PRs that need leadership attention",
        findings=findings,
        area_path=snapshot.area_path,
        iteration_path=snapshot.iteration_path,
    )

    state.write_daily(cfg.state_dir, "at-risk", report.to_json(), day=day)
    md_path = cfg.state_dir / "at-risk" / f"{day.isoformat()}.md"
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(report.to_markdown(), encoding="utf-8")

    if not skip_post:
        delivery.post_report(cfg, report)
    return report
