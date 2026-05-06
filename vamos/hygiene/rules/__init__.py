"""Hygiene rule registry.

Adding a rule = drop a new file here that exposes `RULE_ID` and `check(snapshot, cfg) -> list[Finding]`,
then add it to ALL_RULES below. No other plumbing.
"""
from __future__ import annotations

from typing import Callable

from ...config import Config
from ...core.report import Finding
from ...core.snapshot import TeamSnapshot

from . import (
    branch_naming,
    daily_comments,
    pr_linkage,
    required_fields,
    resolution_on_close,
    stale_blocked,
    state_discipline,
)

RuleFn = Callable[[TeamSnapshot, Config], list[Finding]]

ALL_RULES: list[tuple[str, RuleFn]] = [
    (state_discipline.RULE_ID, state_discipline.check),
    (daily_comments.RULE_ID, daily_comments.check),
    (required_fields.RULE_ID, required_fields.check),
    (pr_linkage.RULE_ID, pr_linkage.check),
    (branch_naming.RULE_ID, branch_naming.check),
    (resolution_on_close.RULE_ID, resolution_on_close.check),
    (stale_blocked.RULE_ID, stale_blocked.check),
]
