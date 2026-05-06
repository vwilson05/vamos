"""Windows Task Scheduler bridge for vamos cron-install / cron-list / cron-uninstall.

Translates the cron expressions in `crons.yml` to `schtasks.exe` invocations.
Supports the patterns we ship in crons.yml.example:
  - `*/N * * * 1-5`   → weekly Mon-Fri, repeat every N minutes (8h duration)
  - `0 H * * 1-5`     → weekly Mon-Fri at HH:00
  - `0 H * * MON`     → weekly on the named day at HH:00
  - `0 H * * *`       → daily at HH:00
  - `*/N * * * *`     → every N minutes
  - `launchd`         → run-on-startup keep-alive task

Patterns outside this set log a warning and are skipped.

All vamos-managed tasks share the prefix `vamos-` and a description starting
with `[vamos]` so we can clean them up cleanly.
"""
from __future__ import annotations

import logging
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Iterable

log = logging.getLogger(__name__)

VAMOS_TASK_PREFIX = "vamos-"
VAMOS_TASK_DESC = "[vamos] managed task — see crons.yml"

DAY_NAMES = {
    "0": "SUN", "1": "MON", "2": "TUE", "3": "WED",
    "4": "THU", "5": "FRI", "6": "SAT",
    "MON": "MON", "TUE": "TUE", "WED": "WED", "THU": "THU",
    "FRI": "FRI", "SAT": "SAT", "SUN": "SUN",
}


@dataclass
class TaskSpec:
    """Internal representation of a translated cron expression for schtasks."""
    schedule: str  # MINUTE | HOURLY | DAILY | WEEKLY | ONSTART
    start_time: str | None = None  # HH:MM
    days: list[str] | None = None  # MON,TUE,...
    interval_min: int | None = None  # /ri
    duration: str | None = None  # HH:MM (/du)


def has_schtasks() -> bool:
    return sys.platform == "win32" and shutil.which("schtasks.exe") is not None


def translate_cron(expr: str) -> TaskSpec | None:
    """Translate a cron expression to a TaskSpec. Returns None for unsupported patterns."""
    if expr.strip().lower() in ("launchd", "onstart"):
        return TaskSpec(schedule="ONSTART")

    parts = expr.split()
    if len(parts) != 5:
        log.warning("translate_cron: expected 5 fields, got %d in %r", len(parts), expr)
        return None
    minute, hour, _dom, _mon, dow = parts

    # Normalize day-of-week → schtasks day list
    dow_norm = _normalize_dow(dow)

    # Pattern: */N * * * <dow>  — every N minutes
    m_repeat = re.match(r"^\*/(\d+)$", minute)
    if m_repeat and hour == "*":
        interval = int(m_repeat.group(1))
        if dow_norm:
            # weekly on chosen days, repeating every N min for ~13h
            return TaskSpec(
                schedule="WEEKLY", start_time="07:00", days=dow_norm,
                interval_min=interval, duration="13:00",
            )
        # Every-day every-N-min — use MINUTE schedule
        return TaskSpec(schedule="MINUTE", interval_min=interval)

    # Pattern: 0 H * * <dow> — single fire at HH:00 on day(s)
    m_hour = re.match(r"^(\d{1,2})$", hour)
    m_min = re.match(r"^(\d{1,2})$", minute)
    if m_hour and m_min:
        st = f"{int(m_hour.group(1)):02d}:{int(m_min.group(1)):02d}"
        if dow_norm:
            return TaskSpec(schedule="WEEKLY", start_time=st, days=dow_norm)
        return TaskSpec(schedule="DAILY", start_time=st)

    log.warning("translate_cron: unsupported pattern %r", expr)
    return None


def _normalize_dow(dow: str) -> list[str] | None:
    """Convert cron DOW field (e.g. '1-5', 'MON', '0,6') to schtasks day names."""
    if not dow or dow == "*":
        return None
    out: list[str] = []
    for piece in dow.split(","):
        piece = piece.strip().upper()
        if "-" in piece:
            lo, hi = piece.split("-", 1)
            try:
                lo_n = _dow_to_num(lo)
                hi_n = _dow_to_num(hi)
            except ValueError:
                return None
            if lo_n is None or hi_n is None:
                return None
            for n in range(lo_n, hi_n + 1):
                name = DAY_NAMES.get(str(n))
                if name and name not in out:
                    out.append(name)
        else:
            name = DAY_NAMES.get(piece)
            if name and name not in out:
                out.append(name)
    return out or None


def _dow_to_num(piece: str) -> int | None:
    if piece.isdigit():
        return int(piece)
    return {"SUN": 0, "MON": 1, "TUE": 2, "WED": 3, "THU": 4, "FRI": 5, "SAT": 6}.get(piece)


def install_task(name: str, command: str, expr: str, working_dir: str) -> tuple[bool, str]:
    """Install or replace a Task Scheduler entry. Returns (success, message)."""
    spec = translate_cron(expr)
    if not spec:
        return False, f"unsupported cron expression: {expr!r}"
    full_name = f"{VAMOS_TASK_PREFIX}{name}" if not name.startswith(VAMOS_TASK_PREFIX) else name

    # Wrap the command so it runs in the project dir with logs piped to a file
    log_dir = f"{working_dir}\\logs"
    log_file = f"{log_dir}\\{name}.log"
    wrapped_cmd = (
        f'cmd.exe /c "if not exist \\"{log_dir}\\" mkdir \\"{log_dir}\\" && '
        f'cd /d \\"{working_dir}\\" && {command} >> \\"{log_file}\\" 2>&1"'
    )

    args = ["schtasks.exe", "/create", "/f", "/tn", full_name, "/tr", wrapped_cmd]

    if spec.schedule == "ONSTART":
        args += ["/sc", "ONSTART", "/ru", "SYSTEM"]
    elif spec.schedule == "MINUTE":
        args += ["/sc", "MINUTE", "/mo", str(spec.interval_min or 30)]
    elif spec.schedule == "DAILY":
        args += ["/sc", "DAILY", "/st", spec.start_time or "08:00"]
    elif spec.schedule == "WEEKLY":
        args += ["/sc", "WEEKLY", "/d", ",".join(spec.days or []),
                 "/st", spec.start_time or "08:00"]
        if spec.interval_min:
            args += ["/ri", str(spec.interval_min), "/du", spec.duration or "08:00"]

    proc = subprocess.run(args, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        return False, proc.stderr.strip() or proc.stdout.strip()
    return True, f"installed {full_name}"


def uninstall_all() -> tuple[int, list[str]]:
    """Remove every scheduled task whose name starts with the vamos prefix."""
    listed = list_tasks()
    removed: list[str] = []
    for name in listed:
        proc = subprocess.run(
            ["schtasks.exe", "/delete", "/f", "/tn", name],
            capture_output=True, text=True, check=False,
        )
        if proc.returncode == 0:
            removed.append(name)
    return len(removed), removed


def list_tasks() -> list[str]:
    """Return names of installed vamos-* scheduled tasks."""
    proc = subprocess.run(
        ["schtasks.exe", "/query", "/fo", "csv"],
        capture_output=True, text=True, check=False,
    )
    if proc.returncode != 0:
        return []
    out: list[str] = []
    for line in proc.stdout.splitlines()[1:]:  # skip header
        cols = [c.strip().strip('"') for c in line.split(",")]
        if not cols:
            continue
        # First column is the task path: \name or \folder\name
        path = cols[0]
        leaf = path.split("\\")[-1]
        if leaf.startswith(VAMOS_TASK_PREFIX) and leaf not in out:
            out.append(leaf)
    return out
