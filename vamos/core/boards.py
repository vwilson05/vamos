"""Board resolution — turn a board name from .ado-metrics.yml into ADO area/iteration paths.

A "board" here is just a named (area_path, iteration_path) pair. Multiple boards
let you point team agents at "Ingestion Engineering" vs "Platform Core" vs
"DevOps" without changing config.

Special name `ALL_BOARDS` ("all"): resolves to every configured board so agents
can run across the whole org's set of teams in one pass.
"""
from __future__ import annotations

from typing import Any

import yaml

from ..config import ROOT

ALL_BOARDS = "(all boards)"


def load_boards() -> list[dict[str, Any]]:
    """Read .ado-metrics.yml and return its `boards` list."""
    p = ROOT / ".ado-metrics.yml"
    if not p.exists():
        return []
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return []
    return data.get("boards", []) or []


def board_names(include_all: bool = True) -> list[str]:
    names = [b["name"] for b in load_boards() if "name" in b]
    if include_all and names:
        return [ALL_BOARDS, *names]
    return names


def default_board_name() -> str | None:
    p = ROOT / ".ado-metrics.yml"
    if not p.exists():
        return None
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return None
    return data.get("default_board")


def resolve(name: str | None) -> tuple[list[str], list[str]]:
    """Map a board name (or ALL_BOARDS / None) to lists of area + iteration paths.

    - `None` or empty → ([], []) — caller falls back to its own defaults
    - `ALL_BOARDS` → every board's paths
    - exact name match → that board's paths in single-element lists
    - unknown name → ([], []) — caller can warn
    """
    if not name:
        return [], []
    boards = load_boards()
    if name == ALL_BOARDS or name.strip().lower() in ("all", "(all)"):
        return (
            [b["area_path"] for b in boards if "area_path" in b],
            [b["iteration_path"] for b in boards if "iteration_path" in b],
        )
    for b in boards:
        if b.get("name") == name:
            return ([b["area_path"]], [b["iteration_path"]])
    return [], []


def is_all(name: str | None) -> bool:
    return bool(name) and (name == ALL_BOARDS or name.strip().lower() in ("all", "(all)"))


def display_path(value: str | list[str] | None) -> str:
    """Render an area/iteration path for human display, handling list-of-paths."""
    if not value:
        return ""
    if isinstance(value, list):
        if len(value) == 1:
            return value[0]
        leaves = [p.split("\\")[-1] for p in value if p]
        return f"{len(value)} boards: {', '.join(leaves)}"
    return value
