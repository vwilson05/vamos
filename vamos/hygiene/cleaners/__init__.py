"""Per-rule hygiene cleaners.

Each cleaner exposes `RULE_ID` and `propose(finding, snapshot, cfg) -> Proposal | None`.
The clean runner registers them by rule id and dispatches per finding.
"""
from __future__ import annotations

from typing import Callable

from ...cleaner import Proposal
from ...config import Config
from ...core.report import Finding
from ...core.snapshot import TeamSnapshot

from . import (
    daily_comments,
    required_fields,
    resolution_on_close,
    stale_blocked,
    state_discipline,
)

ProposerFn = Callable[[Finding, TeamSnapshot, Config], Proposal | None]

PROPOSERS: dict[str, ProposerFn] = {
    state_discipline.RULE_ID: state_discipline.propose,
    daily_comments.RULE_ID: daily_comments.propose,
    required_fields.RULE_ID: required_fields.propose,
    resolution_on_close.RULE_ID: resolution_on_close.propose,
    stale_blocked.RULE_ID: stale_blocked.propose,
}
