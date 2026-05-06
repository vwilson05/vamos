"""UI state — config / profile / board / theme, persisted in NiceGUI's user storage.

`app.storage.user` is per-browser-session and survives reloads. We use it for
the theme toggle, profile selector, and board override. cfg is rebuilt on each
get_cfg() call so .env edits are picked up without restart.
"""
from __future__ import annotations

from nicegui import app

from vamos import config as config_mod
from vamos.core import boards as boards_mod


def get_profile() -> str | None:
    val = app.storage.user.get("profile") if app.storage.user is not None else None
    return val if val in ("personal", "team") else None


def set_profile(value: str | None) -> None:
    app.storage.user["profile"] = value


def get_board() -> str | None:
    val = app.storage.user.get("board") if app.storage.user is not None else None
    return val or None


def set_board(value: str | None) -> None:
    app.storage.user["board"] = value or ""


def get_dark_mode() -> bool:
    return bool(app.storage.user.get("dark_mode", False)) if app.storage.user is not None else False


def set_dark_mode(value: bool) -> None:
    app.storage.user["dark_mode"] = bool(value)


def get_cfg():
    """Reload cfg from .env each call; apply --board override from user storage."""
    cfg = config_mod.load(profile=get_profile())
    board = get_board()
    if board:
        areas, iters = boards_mod.resolve(board)
        if areas:
            cfg.healthcheck_area_path = areas[0] if len(areas) == 1 else areas
            cfg.healthcheck_iteration_path = (
                iters[0] if len(iters) == 1 else iters
            ) if iters else None
            cfg.hygiene_area_path = cfg.healthcheck_area_path
            cfg.hygiene_iteration_path = cfg.healthcheck_iteration_path
    return cfg
