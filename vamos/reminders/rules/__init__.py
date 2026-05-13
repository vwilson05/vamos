"""Reminder rule registry.

Each rule exposes `RULE_ID` and `check(snapshot, cfg) -> list[Finding]`.
Drop a new file here, register it in ALL_RULES, and you're done.

Reminder rules are *advisory* (severity info / should-fix), unlike hygiene
rules which are pass/fail standards enforcement.
"""
from __future__ import annotations

from typing import Callable

from ...config import Config
from ...core.report import Finding
from ...core.snapshot import TeamSnapshot

from . import (
    active_overload,
    customer_onboarding_stalled,
    handoff_silent,
    no_target_date_on_p1,
    p1_unpicked,
    pr_merged_ticket_open,
    target_date_approaching,
    workbook_sent,
)

RuleFn = Callable[[TeamSnapshot, Config], list[Finding]]

ALL_RULES: list[tuple[str, RuleFn]] = [
    (workbook_sent.RULE_ID, workbook_sent.check),
    (p1_unpicked.RULE_ID, p1_unpicked.check),
    (pr_merged_ticket_open.RULE_ID, pr_merged_ticket_open.check),
    (active_overload.RULE_ID, active_overload.check),
    (target_date_approaching.RULE_ID, target_date_approaching.check),
    (no_target_date_on_p1.RULE_ID, no_target_date_on_p1.check),
    (handoff_silent.RULE_ID, handoff_silent.check),
    (customer_onboarding_stalled.RULE_ID, customer_onboarding_stalled.check),
]
