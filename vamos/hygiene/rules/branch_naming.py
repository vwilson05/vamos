"""branch-naming — PR source branches follow `<type>/<ticket>-<slug>`.

Pattern (configurable via HYGIENE_BRANCH_PATTERN):
  ^(feature|bugfix|hotfix)/\\d+-[a-z0-9-]+$
"""
from __future__ import annotations

import re

from ...config import Config
from ...core.report import Finding
from ...core.snapshot import TeamSnapshot

RULE_ID = "branch-naming"


def check(snapshot: TeamSnapshot, cfg: Config) -> list[Finding]:
    findings: list[Finding] = []

    try:
        pattern = re.compile(cfg.hygiene_branch_pattern)
    except re.error as exc:
        return [Finding(
            rule_id=RULE_ID,
            severity="info",
            message=f"HYGIENE_BRANCH_PATTERN is invalid regex: {exc}",
        )]

    for pr in snapshot.pull_requests:
        if pr.status != "active":
            continue
        if pattern.match(pr.source_branch):
            continue
        findings.append(Finding(
            rule_id=RULE_ID,
            severity="nit",
            engineer=pr.author,
            ticket_id=None,
            ticket_url=pr.url,
            ticket_title=f"PR #{pr.id} ({pr.repo}): {pr.title}",
            message=(
                f"Branch `{pr.source_branch}` doesn't match the naming standard "
                f"`{cfg.hygiene_branch_pattern}`. Format: `<type>/<ticket-number>-<short-description>`, "
                "type ∈ {feature, bugfix, hotfix}, lowercase + hyphens only."
            ),
        ))

    return findings
