"""Reminders runner — board-wide advisory recommendations.

Pattern mirrors hygiene/at_risk: build a TeamSnapshot once, run rules over
it, assemble a Report, optionally deliver.

Posting semantics:
- `skip_post=True` (default for MCP/preview): never delivers anywhere.
- `skip_post=False`: posts the report to Teams/Slack per cfg.connection_option.
- `comment_tickets=True`: in addition to the channel post, leaves a per-ticket
  comment on every finding that has a `suggested_comment` and a `ticket_id`.
  Gated by HYGIENE_LIVE_MODE (re-uses the same safety flag — if the engineer
  doesn't trust hygiene to comment, they shouldn't trust reminders either).
"""
from __future__ import annotations

import hashlib
import logging
from collections import defaultdict
from datetime import date

from ..ado import ADOClient, ReadOnlyError
from ..config import Config
from ..core import delivery, state
from ..core.report import Finding, Report
from ..core.snapshot import build_snapshot
from .rules import ALL_RULES

log = logging.getLogger(__name__)


def run(
    cfg: Config,
    skip_post: bool = True,
    comment_tickets: bool = False,
    channel: str | None = None,
    day: date | None = None,
) -> Report:
    """Generate the board-reminders report.

    Defaults to `skip_post=True` so importing this module from MCP / tests
    is safe — explicit opt-in to deliver. CLI sets `skip_post=False` only
    after the user confirms.
    """
    day = day or date.today()
    needs_writes = comment_tickets and cfg.hygiene_live_mode
    client = ADOClient(
        cfg.ado_org_url, cfg.ado_project, cfg.ado_pat,
        read_only=not needs_writes,
    )

    log.info("reminders: building team snapshot")
    snapshot = build_snapshot(
        client,
        area_path=cfg.hygiene_area_path,
        iteration_path=cfg.hygiene_iteration_path,
        repos=cfg.hygiene_repos or None,
    )

    findings: list[Finding] = []
    for rule_id, fn in ALL_RULES:
        try:
            rule_findings = fn(snapshot, cfg)
        except Exception as exc:
            log.exception("reminders rule %s crashed: %s", rule_id, exc)
            findings.append(Finding(
                rule_id=rule_id,
                severity="info",
                message=f"Rule '{rule_id}' crashed: {exc!r}. See logs.",
            ))
            continue
        log.info("reminders rule %s: %d finding(s)", rule_id, len(rule_findings))
        findings.extend(rule_findings)

    report = Report(
        title=f"Board Reminders — {day.strftime('%A, %B %d, %Y')}",
        subtitle="Advisory recommendations across the board",
        findings=findings,
        area_path=snapshot.area_path,
        iteration_path=snapshot.iteration_path,
    )

    state.write_daily(cfg.state_dir, "reminders", report.to_json(), day=day)
    md_path = cfg.state_dir / "reminders" / f"{day.isoformat()}.md"
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(report.to_markdown(), encoding="utf-8")
    log.info("reminders: wrote report to %s", md_path)

    if comment_tickets:
        if not cfg.hygiene_live_mode:
            log.warning(
                "reminders: --comment-tickets requested but HYGIENE_LIVE_MODE=false; "
                "skipping per-ticket comments"
            )
        else:
            _post_per_ticket_comments(client, cfg, findings)

    if not skip_post:
        delivery.post_report(cfg, report, prefer=channel)
    else:
        log.info("reminders: skip-post set; not delivering to Teams/Slack")

    return report


def _post_per_ticket_comments(
    client: ADOClient, cfg: Config, findings: list[Finding]
) -> None:
    """One comment per ticket, deduped by content hash (same pattern as hygiene)."""
    by_ticket: dict[int, list[Finding]] = defaultdict(list)
    for f in findings:
        if f.ticket_id and f.suggested_comment:
            by_ticket[f.ticket_id].append(f)

    posted_path = cfg.state_dir / "reminders" / "posted-hashes.txt"
    posted: set[str] = set()
    if posted_path.exists():
        posted = {
            line.strip() for line in posted_path.read_text().splitlines() if line.strip()
        }

    new_hashes: list[str] = []
    for ticket_id, ticket_findings in by_ticket.items():
        body_lines = ["**vamos reminder** — advisory note", ""]
        for f in ticket_findings:
            body_lines.append(f"- _{f.rule_id}_: {f.suggested_comment}")
        body = "\n".join(body_lines)
        h = hashlib.sha256(f"{ticket_id}:{body}".encode()).hexdigest()
        if h in posted:
            continue
        try:
            client.add_comment(ticket_id, body)
            new_hashes.append(h)
            log.info("reminders: posted comment on #%d", ticket_id)
        except ReadOnlyError:
            log.warning("reminders: client is read-only; cannot post comments")
            return
        except Exception as exc:
            log.error("reminders: failed to post on #%d: %s", ticket_id, exc)

    if new_hashes:
        posted_path.parent.mkdir(parents=True, exist_ok=True)
        with posted_path.open("a", encoding="utf-8") as fh:
            for h in new_hashes:
                fh.write(h + "\n")
