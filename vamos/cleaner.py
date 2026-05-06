"""Cleaner — shared abstraction for AI-assisted "fix this finding" actions.

A `Proposal` is a finding plus 0..N concrete `Action`s vamos would take to fix
it (post a comment, update a state, set a field, link to another item). The
runner walks each finding, asks its rule's proposer to build a Proposal, and
either prompts the user (interactive) or applies it directly (live mode).

This module is rule-agnostic. Per-rule cleaners (in vamos/hygiene/cleaners/)
build the Proposal; the runner here applies it.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Literal

from .ado import ADOClient, ReadOnlyError
from .core.report import Finding

log = logging.getLogger(__name__)

ActionKind = Literal["comment", "set_state", "set_field", "set_fields", "link", "noop"]


@dataclass
class Action:
    kind: ActionKind
    work_item_id: int
    payload: dict[str, Any] = field(default_factory=dict)

    def describe(self) -> str:
        if self.kind == "comment":
            text = (self.payload.get("text") or "").strip()
            preview = text[:80] + ("…" if len(text) > 80 else "")
            return f"comment on #{self.work_item_id}: {preview}"
        if self.kind == "set_state":
            return f"set #{self.work_item_id} state → {self.payload.get('state')}"
        if self.kind == "set_field":
            return f"set #{self.work_item_id} {self.payload.get('field')} → {self.payload.get('value')}"
        if self.kind == "set_fields":
            fields = self.payload.get("fields", {}) or {}
            parts = ", ".join(f"{k}={v}" for k, v in fields.items())
            return f"set #{self.work_item_id} fields: {parts}"
        if self.kind == "link":
            return (
                f"link #{self.work_item_id} → #{self.payload.get('target_id')} "
                f"({self.payload.get('rel','related')})"
            )
        return f"noop on #{self.work_item_id}"


@dataclass
class Proposal:
    finding: Finding
    rationale: str
    actions: list[Action] = field(default_factory=list)
    confidence: Literal["high", "medium", "low"] = "medium"

    @property
    def is_empty(self) -> bool:
        return not self.actions or all(a.kind == "noop" for a in self.actions)

    def describe(self) -> str:
        lines = [f"Rule: {self.finding.rule_id}  ·  confidence: {self.confidence}"]
        ticket_ref = f"#{self.finding.ticket_id}" if self.finding.ticket_id else "(team-level)"
        lines.append(f"Finding: {ticket_ref} — {self.finding.message}")
        if self.rationale:
            lines.append(f"Why: {self.rationale}")
        if self.actions:
            lines.append("Will apply:")
            for a in self.actions:
                lines.append(f"  - {a.describe()}")
        else:
            lines.append("(no actions proposed — skip)")
        return "\n".join(lines)


# Per-rule proposer signature. Each cleaner module exports `RULE_ID` plus a
# `propose(finding, snapshot, cfg) -> Proposal | None` function.
ProposerFn = Callable[..., Any]


@dataclass
class ApplyResult:
    proposal: Proposal
    applied: bool
    error: str | None = None
    api_responses: list[dict] = field(default_factory=list)

    def to_log_dict(self) -> dict:
        return {
            "proposal": {
                "rule_id": self.proposal.finding.rule_id,
                "ticket_id": self.proposal.finding.ticket_id,
                "engineer": self.proposal.finding.engineer,
                "message": self.proposal.finding.message,
                "rationale": self.proposal.rationale,
                "confidence": self.proposal.confidence,
                "actions": [asdict(a) for a in self.proposal.actions],
            },
            "applied": self.applied,
            "error": self.error,
        }


def apply_proposal(client: ADOClient, proposal: Proposal) -> ApplyResult:
    """Execute every action in the proposal against ADO. Stops at first error."""
    if proposal.is_empty:
        return ApplyResult(proposal, applied=False, error="empty proposal — nothing to apply")
    responses: list[dict] = []
    for a in proposal.actions:
        try:
            resp = _apply_action(client, a) or {}
            responses.append({"action": a.describe(), "ok": True, "response_id": resp.get("id")})
        except ReadOnlyError as exc:
            return ApplyResult(proposal, applied=False, error=f"read-only mode: {exc}",
                               api_responses=responses)
        except Exception as exc:
            log.exception("apply_action failed for %s", a.describe())
            return ApplyResult(proposal, applied=False, error=str(exc),
                               api_responses=responses)
    return ApplyResult(proposal, applied=True, api_responses=responses)


def _apply_action(client: ADOClient, a: Action) -> dict | None:
    if a.kind == "comment":
        return client.add_comment(a.work_item_id, a.payload["text"])
    if a.kind == "set_state":
        return client.patch_fields(a.work_item_id, {"System.State": a.payload["state"]}).raw_fields
    if a.kind == "set_field":
        return client.patch_fields(a.work_item_id, {a.payload["field"]: a.payload["value"]}).raw_fields
    if a.kind == "set_fields":
        return client.patch_fields(a.work_item_id, a.payload.get("fields") or {}).raw_fields
    if a.kind == "link":
        return client.link_work_items(
            a.work_item_id, int(a.payload["target_id"]),
            rel=a.payload.get("rel", "System.LinkTypes.Related"),
        ).raw_fields
    if a.kind == "noop":
        return None
    raise ValueError(f"unknown action kind: {a.kind}")
