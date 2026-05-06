"""Hygiene clean runner — for each finding, build a Proposal and (optionally) apply it."""
from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from datetime import date
from typing import Callable

from ..ado import ADOClient
from ..cleaner import ApplyResult, Proposal, apply_proposal
from ..config import Config
from ..core import state
from ..core.report import Finding
from ..core.snapshot import TeamSnapshot, build_snapshot
from .cleaners import PROPOSERS
from .runner import run_rules

log = logging.getLogger(__name__)


@dataclass
class CleanRun:
    proposals: list[Proposal]
    applied: list[ApplyResult]
    skipped: list[Proposal]


def collect_proposals(
    snapshot: TeamSnapshot,
    findings: list[Finding],
    cfg: Config,
    rule_filter: set[str] | None = None,
) -> list[Proposal]:
    """Build proposals from findings. Skips rules without a registered cleaner."""
    proposals: list[Proposal] = []
    for f in findings:
        if rule_filter and f.rule_id not in rule_filter:
            continue
        proposer = PROPOSERS.get(f.rule_id)
        if not proposer:
            log.debug("no cleaner registered for rule %s; skipping", f.rule_id)
            continue
        try:
            p = proposer(f, snapshot, cfg)
        except Exception as exc:
            log.exception("cleaner %s crashed on finding for #%s", f.rule_id, f.ticket_id)
            continue
        if p and not p.is_empty:
            proposals.append(p)
    return proposals


def run(
    cfg: Config,
    apply: bool = False,
    rule_filter: set[str] | None = None,
    interactive: bool = True,
    on_proposal: Callable[[Proposal], str] | None = None,
    day: date | None = None,
) -> CleanRun:
    """Build snapshot, run rules, build proposals, apply (or prompt) for each.

    `on_proposal` lets the UI inject a custom prompt; if None, falls back to
    stdin y/n/skip in interactive mode, or auto-apply / dry-run otherwise.
    `apply=True` requires HYGIENE_LIVE_MODE=true at the cfg level.
    """
    day = day or date.today()
    if apply and not cfg.hygiene_live_mode:
        raise SystemExit("--apply requires HYGIENE_LIVE_MODE=true in config.")

    client = ADOClient(cfg.ado_org_url, cfg.ado_project, cfg.ado_pat,
                       read_only=not apply)

    log.info("hygiene clean: building team snapshot")
    snapshot = build_snapshot(
        client,
        area_path=cfg.hygiene_area_path,
        iteration_path=cfg.hygiene_iteration_path,
        repos=cfg.hygiene_repos or None,
    )

    findings = run_rules(snapshot, cfg)
    log.info("hygiene clean: %d finding(s) total", len(findings))

    proposals = collect_proposals(snapshot, findings, cfg, rule_filter=rule_filter)
    log.info("hygiene clean: %d proposal(s) constructed", len(proposals))

    applied: list[ApplyResult] = []
    skipped: list[Proposal] = []

    auto_apply_all = False
    for i, p in enumerate(proposals, 1):
        choice = "skip"
        if on_proposal is not None:
            choice = on_proposal(p)
        elif interactive and not auto_apply_all:
            print(f"\n=== Proposal {i}/{len(proposals)} ===")
            print(p.describe())
            print("\nApply? [y]es / [n]o / [a]ll-yes / [s]kip-rule / [q]uit > ", end="", flush=True)
            raw = sys.stdin.readline().strip().lower()
            if raw in ("a", "all"):
                auto_apply_all = True
                choice = "apply"
            elif raw in ("q", "quit"):
                break
            elif raw in ("s", "skip-rule"):
                rule_filter = (rule_filter or set()) - {p.finding.rule_id}
                # Simpler: just skip remaining proposals of this rule
                _to_skip = {p.finding.rule_id}
                proposals = [x for x in proposals if x.finding.rule_id not in _to_skip]
                skipped.append(p)
                continue
            elif raw in ("y", "yes"):
                choice = "apply"
            else:
                choice = "skip"
        elif auto_apply_all:
            choice = "apply"
        else:
            # Headless: dry-run summary
            choice = "apply" if apply else "skip"

        if choice == "apply":
            if not apply and on_proposal is None:
                # CLI was interactive without --apply; we can still post the action
                # since the user explicitly said "yes". Re-init writable client lazily.
                if client.read_only:
                    client = ADOClient(cfg.ado_org_url, cfg.ado_project, cfg.ado_pat,
                                       read_only=False)
            result = apply_proposal(client, p)
            applied.append(result)
            if result.applied:
                log.info("hygiene clean: applied #%s (rule %s)",
                         p.finding.ticket_id, p.finding.rule_id)
            else:
                log.warning("hygiene clean: failed #%s — %s",
                            p.finding.ticket_id, result.error)
        else:
            skipped.append(p)

    # Persist the audit trail
    state.write_log(cfg.state_dir, "hygiene-clean", {
        "day": day.isoformat(),
        "total_findings": len(findings),
        "proposals": len(proposals),
        "applied": [r.to_log_dict() for r in applied],
        "skipped_count": len(skipped),
    })

    return CleanRun(proposals=proposals, applied=applied, skipped=skipped)
