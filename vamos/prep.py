"""Prep — one-shot "morning routine" that runs SOD, inbox, and standup.

Persists each result to state/<agent>/<YYYY-MM-DD>.{json,md} so the UI can
read it immediately on page load without re-querying ADO.

Triggered by:
  - `vamos prep`                          (CLI on demand)
  - `./launch.sh --prep`                  (CLI flag during setup)
  - VAMOS_AUTO_PREP=true in .env          (always run on launch.sh)
  - "Auto-prep on launch" toggle in Settings UI
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date

from . import inbox as inbox_mod
from . import sod as sod_mod
from . import standup as standup_mod
from .config import Config
from .core import state
from .markdown_io import daily_path

log = logging.getLogger(__name__)


@dataclass
class PrepResult:
    sod_path: str | None
    inbox_count: int
    standup_path: str
    standup_text: str
    skipped: list[str]


def run(
    cfg: Config,
    force_sod: bool = False,
    skip_inbox: bool = False,
    skip_standup: bool = False,
    skip_sod: bool = False,
    day: date | None = None,
) -> PrepResult:
    day = day or date.today()
    skipped: list[str] = []

    # 1. SOD — only if today's MD doesn't exist (idempotent)
    sod_path = None
    md_path = daily_path(cfg.work_dir, day)
    if skip_sod:
        skipped.append("sod")
    elif md_path.exists() and not force_sod:
        log.info("prep: SOD skipped — today's markdown already exists at %s", md_path)
        sod_path = str(md_path)
    else:
        log.info("prep: running SOD")
        sod_path = str(sod_mod.run(cfg, force=force_sod, day=day))

    # 2. Inbox — always builds fresh (data changes throughout the day)
    inbox_count = 0
    if skip_inbox:
        skipped.append("inbox")
    else:
        log.info("prep: building inbox")
        items = inbox_mod.build(cfg, since_hours=48)
        inbox_count = len(items)
        state.write_daily(cfg.state_dir, "inbox", {
            "items": inbox_mod.to_dict_list(items),
            "count": inbox_count,
        }, day=day)

    # 3. Standup
    standup_path = ""
    standup_text = ""
    if skip_standup:
        skipped.append("standup")
    else:
        log.info("prep: building standup")
        standup_text = standup_mod.run(cfg, day=day)
        standup_dir = cfg.state_dir / "standup"
        standup_dir.mkdir(parents=True, exist_ok=True)
        out = standup_dir / f"{day.isoformat()}.md"
        out.write_text(standup_text, encoding="utf-8")
        standup_path = str(out)

    return PrepResult(
        sod_path=sod_path,
        inbox_count=inbox_count,
        standup_path=standup_path,
        standup_text=standup_text,
        skipped=skipped,
    )


def read_cached_inbox(cfg: Config, day: date | None = None) -> list[dict] | None:
    payload = state.read_daily(cfg.state_dir, "inbox", day=day)
    if not payload:
        return None
    return payload.get("items") or []


def read_cached_standup(cfg: Config, day: date | None = None) -> str | None:
    day = day or date.today()
    p = cfg.state_dir / "standup" / f"{day.isoformat()}.md"
    if not p.exists():
        return None
    try:
        return p.read_text(encoding="utf-8")
    except OSError:
        return None
