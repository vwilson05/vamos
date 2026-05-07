"""Append-only audit trail per ticket.

Every MCP tool call writes one JSONL line to state/trail/<ticket>.jsonl. The
record is intentionally small — actor + tool + a result summary — so the file
stays cheap to tail when computing next-actions.

The trail exists for two reasons:
  1. Audit. "Who closed ticket 12345 — Claude or Victor?"
  2. Workflow hints. next_actions() reads recent events to answer
     "did we already run pr-review on this PR?" without re-querying ADO.
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

ACTOR_CLAUDE = "claude"
ACTOR_HUMAN = "human"
ACTOR_CLI = "cli"


@dataclass
class TrailEvent:
    ts: str
    actor: str
    tool: str
    args: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] = field(default_factory=dict)


def _trail_dir(state_dir: Path) -> Path:
    p = state_dir / "trail"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _trail_file(state_dir: Path, ticket_id: int) -> Path:
    return _trail_dir(state_dir) / f"{ticket_id}.jsonl"


def append_event(
    state_dir: Path,
    ticket_id: int,
    tool: str,
    args: dict[str, Any] | None = None,
    result: dict[str, Any] | None = None,
    actor: str = ACTOR_CLAUDE,
) -> TrailEvent:
    """Append one event line. Never raises — trail failures shouldn't block tools."""
    event = TrailEvent(
        ts=datetime.now(timezone.utc).isoformat(),
        actor=actor,
        tool=tool,
        args=_redact(args or {}),
        result=_compact(result or {}),
    )
    try:
        path = _trail_file(state_dir, ticket_id)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(asdict(event)) + "\n")
    except Exception as exc:  # noqa: BLE001
        log.warning("trail: append failed for #%d: %s", ticket_id, exc)
    return event


def read_events(state_dir: Path, ticket_id: int, limit: int = 20) -> list[TrailEvent]:
    path = _trail_file(state_dir, ticket_id)
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()[-limit:]
    out: list[TrailEvent] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
            out.append(TrailEvent(**d))
        except Exception as exc:  # noqa: BLE001
            log.debug("trail: skipping malformed line in #%d: %s", ticket_id, exc)
    return out


def has_recent_tool(events: list[TrailEvent], tool: str) -> bool:
    return any(e.tool == tool for e in events)


def _redact(d: dict[str, Any]) -> dict[str, Any]:
    """Strip long bodies — comments and PR descriptions get clipped to 200 chars."""
    out: dict[str, Any] = {}
    for k, v in d.items():
        if isinstance(v, str) and len(v) > 200:
            out[k] = v[:200] + "..."
        else:
            out[k] = v
    return out


def _compact(d: dict[str, Any]) -> dict[str, Any]:
    return _redact(d)
