"""Single-master dispatcher.

Cron / Task Scheduler runs `vamos daily` every 30 minutes on weekdays.
This module looks at the current time and the state of today's files to decide
what to do — exactly one of {sod, sync, eod, nothing}. State-driven so missed
runs catch up automatically (laptop sleep, VPN drop, late start).

Schedule (configurable via env, all times local):
- SOD:  do once per weekday, the first run at or after RUN_SOD_AT (default 08:00)
- SYNC: every RUN_SYNC_INTERVAL_MIN minutes between SOD and EOD (default 180)
- EOD:  do once per weekday, the first run at or after RUN_EOD_AT (default 18:00)
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path

from . import eod as eod_mod
from . import sod as sod_mod
from . import sync as sync_mod
from .config import Config
from .markdown_io import daily_path

log = logging.getLogger(__name__)


@dataclass
class Schedule:
    sod_at: time
    eod_at: time
    sync_interval_min: int
    skip_weekends: bool

    @classmethod
    def from_env(cls) -> "Schedule":
        return cls(
            sod_at=_parse_time(os.getenv("RUN_SOD_AT", "08:00")),
            eod_at=_parse_time(os.getenv("RUN_EOD_AT", "18:00")),
            sync_interval_min=int(os.getenv("RUN_SYNC_INTERVAL_MIN", "180")),
            skip_weekends=os.getenv("RUN_SKIP_WEEKENDS", "true").strip().lower()
            in ("1", "true", "yes"),
        )


def dispatch(cfg: Config, now: datetime | None = None, force: str | None = None) -> str:
    """Decide and run the right command. Returns the action taken."""
    schedule = Schedule.from_env()
    now = now or datetime.now()
    today = now.date()

    if force:
        return _run(force, cfg, today)

    if schedule.skip_weekends and now.weekday() >= 5:
        log.info("dispatch: weekend (%s) — skipping", now.strftime("%A"))
        return "skip-weekend"

    state = _load_run_state(cfg.state_dir, today)

    # 1) EOD window — once we're past EOD time, do EOD if not yet done.
    if now.time() >= schedule.eod_at and not state.get("eod_done"):
        result = _run("eod", cfg, today)
        state["eod_done"] = now.isoformat()
        _save_run_state(cfg.state_dir, today, state)
        return result

    # 2) SOD — first run of the day at/after SOD time, before EOD.
    if now.time() >= schedule.sod_at and not state.get("sod_done"):
        result = _run("sod", cfg, today)
        state["sod_done"] = now.isoformat()
        state["last_sync"] = now.isoformat()  # SOD seeds the timer; first sync ~3h later
        _save_run_state(cfg.state_dir, today, state)
        return result

    # 3) SYNC — only after SOD and before EOD, throttled by interval.
    if state.get("sod_done") and now.time() < schedule.eod_at:
        last_sync_iso = state.get("last_sync")
        if last_sync_iso:
            last_sync = datetime.fromisoformat(last_sync_iso)
        else:
            last_sync = datetime.combine(today, schedule.sod_at)
        if now - last_sync >= timedelta(minutes=schedule.sync_interval_min):
            result = _run("sync", cfg, today)
            state["last_sync"] = now.isoformat()
            _save_run_state(cfg.state_dir, today, state)
            return result

    log.info("dispatch: nothing to do at %s", now.strftime("%Y-%m-%d %H:%M"))
    return "noop"


def _run(cmd: str, cfg: Config, today: date) -> str:
    log.info("dispatch: running %s", cmd)
    if cmd == "sod":
        sod_mod.run(cfg, force=False, day=today)
        return "sod"
    if cmd == "sync":
        # Skip if no markdown yet (SOD didn't run).
        if not daily_path(cfg.work_dir, today).exists():
            log.warning("sync requested but no markdown for %s — running sod first", today)
            sod_mod.run(cfg, force=False, day=today)
        sync_mod.run(cfg, dry_run=False, day=today)
        return "sync"
    if cmd == "eod":
        if not daily_path(cfg.work_dir, today).exists():
            log.warning("eod requested but no markdown for %s — running sod first", today)
            sod_mod.run(cfg, force=False, day=today)
        eod_mod.run(cfg, day=today)
        return "eod"
    raise ValueError(f"unknown command: {cmd}")


def _state_path(state_dir: Path, day: date) -> Path:
    return state_dir / f"{day.isoformat()}-run.json"


def _load_run_state(state_dir: Path, day: date) -> dict:
    path = _state_path(state_dir, day)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _save_run_state(state_dir: Path, day: date, state: dict) -> None:
    _state_path(state_dir, day).write_text(json.dumps(state, indent=2), encoding="utf-8")


def _parse_time(value: str) -> time:
    parts = value.strip().split(":")
    if len(parts) != 2:
        raise ValueError(f"expected HH:MM, got {value!r}")
    return time(int(parts[0]), int(parts[1]))
