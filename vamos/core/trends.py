"""Trends — read historical agent snapshots and compute deltas.

Each agent (hygiene, healthcheck, metrics) writes one JSON per day to
state/<agent>/<YYYY-MM-DD>.json. This module reads those files and
extracts time-series so the UI can render sparklines and the manager
can see week-over-week change.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any


def list_snapshots(state_dir: Path, agent: str, days: int = 30) -> list[tuple[date, dict]]:
    """Return [(date, payload), ...] sorted ascending by date, limited to last N days."""
    agent_dir = state_dir / agent
    if not agent_dir.exists():
        return []
    cutoff = date.today() - timedelta(days=days)
    out: list[tuple[date, dict]] = []
    for f in sorted(agent_dir.glob("*.json")):
        if not f.is_file():
            continue
        try:
            d = date.fromisoformat(f.stem)
        except ValueError:
            continue
        if d < cutoff:
            continue
        try:
            payload = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        out.append((d, payload))
    return out


def hygiene_series(state_dir: Path, days: int = 30) -> dict[str, list[tuple[date, int]]]:
    """Return per-severity time series for hygiene.

    Output: {'blocker': [(date, count), ...], 'should-fix': [...], 'nit': [...], 'total': [...]}
    """
    snaps = list_snapshots(state_dir, "hygiene", days)
    series: dict[str, list[tuple[date, int]]] = {
        "blocker": [], "should-fix": [], "nit": [], "total": []
    }
    for d, payload in snaps:
        s = payload.get("summary", {}) or {}
        series["blocker"].append((d, int(s.get("blocker", 0))))
        series["should-fix"].append((d, int(s.get("should-fix", 0))))
        series["nit"].append((d, int(s.get("nit", 0))))
        series["total"].append((d, sum(int(s.get(k, 0)) for k in ("blocker", "should-fix", "nit"))))
    return series


def hygiene_per_engineer(state_dir: Path, days: int = 14) -> dict[str, list[tuple[date, int]]]:
    """Per-engineer finding count over time. Maps engineer name -> [(date, count)]."""
    from .people import canonical

    snaps = list_snapshots(state_dir, "hygiene", days)
    out: dict[str, dict[date, int]] = {}
    for d, payload in snaps:
        for f in payload.get("findings", []) or []:
            eng = f.get("engineer")
            if not eng:
                continue
            key = canonical(eng)
            out.setdefault(key, {}).setdefault(d, 0)
            out[key][d] += 1
    return {
        eng: sorted(by_date.items())
        for eng, by_date in out.items()
    }


def delta(series: list[tuple[date, int]]) -> dict[str, Any]:
    """Compute week-over-week and 7-day-mean change."""
    if not series:
        return {"latest": None, "wow": None, "trend": "flat"}
    latest = series[-1][1]
    week_ago = None
    week_ago_date = series[-1][0] - timedelta(days=7)
    for d, v in series:
        if d <= week_ago_date:
            week_ago = v
    if week_ago is None or week_ago == 0:
        return {"latest": latest, "wow": None, "trend": "flat"}
    diff = latest - week_ago
    pct = (diff / week_ago) * 100
    return {
        "latest": latest,
        "wow": diff,
        "wow_pct": pct,
        "trend": "up" if diff > 0 else ("down" if diff < 0 else "flat"),
    }


def sparkline_unicode(values: list[int], width: int = 30) -> str:
    """Render a unicode bar sparkline. For terminal/Markdown use."""
    if not values:
        return ""
    bars = "▁▂▃▄▅▆▇█"
    lo, hi = min(values), max(values)
    rng = hi - lo or 1
    if len(values) > width:
        # Downsample
        step = len(values) / width
        sampled = [values[int(i * step)] for i in range(width)]
        values = sampled
    return "".join(bars[min(len(bars) - 1, int((v - lo) / rng * (len(bars) - 1)))] for v in values)
