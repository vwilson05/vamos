"""State — date-keyed JSON files per agent.

Layout:
  state/<agent>/<YYYY-MM-DD>.json   # latest snapshot/run for that agent
  state/<agent>/logs/<timestamp>.json   # full audit trail
"""
from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any


def agent_dir(state_root: Path, agent: str) -> Path:
    p = state_root / agent
    p.mkdir(parents=True, exist_ok=True)
    (p / "logs").mkdir(parents=True, exist_ok=True)
    return p


def daily_path(state_root: Path, agent: str, day: date | None = None) -> Path:
    day = day or date.today()
    return agent_dir(state_root, agent) / f"{day.isoformat()}.json"


def write_daily(state_root: Path, agent: str, payload: dict[str, Any], day: date | None = None) -> Path:
    p = daily_path(state_root, agent, day)
    p.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return p


def write_log(state_root: Path, agent: str, payload: dict[str, Any]) -> Path:
    ts = datetime.now().strftime("%Y%m%dT%H%M%S")
    p = agent_dir(state_root, agent) / "logs" / f"{ts}.json"
    p.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return p


def read_daily(state_root: Path, agent: str, day: date | None = None) -> dict[str, Any] | None:
    p = daily_path(state_root, agent, day)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
