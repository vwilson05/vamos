"""Hygiene runner — orchestrates snapshot, rules, report, and (optionally) live nudges."""
from __future__ import annotations

import hashlib
import logging
from collections import defaultdict
from dataclasses import asdict
from datetime import date, datetime
from typing import Any

from ..ado import ADOClient, ReadOnlyError
from ..config import Config
from ..core import delivery, state
from ..core.report import Finding, Report
from ..core.snapshot import TeamSnapshot, build_snapshot
from .rules import ALL_RULES, RuleFn

log = logging.getLogger(__name__)


def run(
    cfg: Config,
    skip_post: bool = False,
    auto_comment: bool = False,
    day: date | None = None,
    repos_override: list[str] | None = None,
) -> Report:
    """Build a snapshot, run all rules, post the report, optionally nudge.

    Repo resolution (for PR-linkage / branch-naming rules):
      1. `repos_override` — from `--repo` CLI flag (single repo focus)
      2. `cfg.hygiene_repos` — from HYGIENE_REPOS env var (subset)
      3. Auto-discover ALL repos in the project (default)

    Returns the assembled Report so callers (CLI, UI) can render or inspect.
    """
    day = day or date.today()
    client = ADOClient(cfg.ado_org_url, cfg.ado_project, cfg.ado_pat,
                       read_only=not (auto_comment and cfg.hygiene_live_mode))

    if repos_override:
        repos: list[str] | None = repos_override
        log.info("hygiene: using --repo override: %s", repos)
    elif cfg.hygiene_repos:
        repos = cfg.hygiene_repos
        log.info("hygiene: using HYGIENE_REPOS from config: %s", repos)
    else:
        repos = None
        log.info("hygiene: HYGIENE_REPOS not set — auto-discovering all repos in project")

    log.info("hygiene: building team snapshot")
    snapshot = build_snapshot(
        client,
        area_path=cfg.hygiene_area_path,
        iteration_path=cfg.hygiene_iteration_path,
        repos=repos,
    )

    findings = run_rules(snapshot, cfg)

    report = Report(
        title=f"Team Hygiene — {day.strftime('%A, %B %d, %Y')}",
        subtitle="ADO board standards check (Jeff Jordan, May 5 2026)",
        findings=findings,
        area_path=snapshot.area_path,
        iteration_path=snapshot.iteration_path,
    )

    # Persist results for UI consumption + audit
    state.write_daily(cfg.state_dir, "hygiene", report.to_json(), day=day)
    state.write_log(cfg.state_dir, "hygiene", {
        "snapshot_at": snapshot.snapshot_at.isoformat(),
        "rule_count": len(ALL_RULES),
        "finding_count": len(findings),
        "auto_comment": auto_comment,
        "live_mode": cfg.hygiene_live_mode,
    })

    md_path = cfg.state_dir / "hygiene" / f"{day.isoformat()}.md"
    md_path.write_text(report.to_markdown(), encoding="utf-8")
    log.info("hygiene: wrote report to %s", md_path)

    # Optional live nudges
    if auto_comment:
        if not cfg.hygiene_live_mode:
            log.warning("--auto-comment requested but HYGIENE_LIVE_MODE=false; skipping comment posting")
        else:
            _post_nudges(client, cfg, findings)

    if not skip_post:
        delivery.post_report(cfg, report)
    else:
        log.info("hygiene: skip-post set; not delivering to Teams/Slack")

    return report


def run_rules(snapshot: TeamSnapshot, cfg: Config) -> list[Finding]:
    findings: list[Finding] = []
    for rule_id, fn in ALL_RULES:
        try:
            rule_findings = fn(snapshot, cfg)
        except Exception as exc:
            log.exception("rule %s crashed: %s", rule_id, exc)
            findings.append(Finding(
                rule_id=rule_id,
                severity="info",
                message=f"Rule '{rule_id}' crashed: {exc!r}. See logs.",
            ))
            continue
        log.info("rule %s: %d finding(s)", rule_id, len(rule_findings))
        findings.extend(rule_findings)
    return findings


def _post_nudges(client: ADOClient, cfg: Config, findings: list[Finding]) -> None:
    """Post one comment per ticket with all of its findings (deduped by hash).

    Hash dedup mirrors sync.py — re-running hygiene won't double-post.
    """
    by_ticket: dict[int, list[Finding]] = defaultdict(list)
    for f in findings:
        if f.ticket_id and f.suggested_comment:
            by_ticket[f.ticket_id].append(f)

    posted_path = cfg.state_dir / "hygiene" / "posted-hashes.txt"
    posted: set[str] = set()
    if posted_path.exists():
        posted = {line.strip() for line in posted_path.read_text().splitlines() if line.strip()}

    new_hashes: list[str] = []
    for ticket_id, ticket_findings in by_ticket.items():
        body_lines = ["**vamos hygiene** — automated nudge", ""]
        for f in ticket_findings:
            body_lines.append(f"- _{f.rule_id}_: {f.suggested_comment or f.message}")
        body = "\n".join(body_lines)
        h = hashlib.sha256(f"{ticket_id}:{body}".encode()).hexdigest()
        if h in posted:
            continue
        try:
            client.add_comment(ticket_id, body)
            new_hashes.append(h)
            log.info("hygiene: posted nudge on #%d (%d finding(s))", ticket_id, len(ticket_findings))
        except ReadOnlyError:
            log.warning("hygiene: ADOClient is read-only; cannot post nudges")
            return
        except Exception as exc:
            log.error("hygiene: failed to post on #%d: %s", ticket_id, exc)

    if new_hashes:
        posted_path.parent.mkdir(parents=True, exist_ok=True)
        with posted_path.open("a", encoding="utf-8") as fh:
            for h in new_hashes:
                fh.write(h + "\n")
