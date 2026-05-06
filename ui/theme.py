"""Theme — dark/light mode + reusable component helpers.

NiceGUI uses Quasar under the hood, so dark mode is essentially free
(`ui.dark_mode().enable()`). We layer Tailwind utility classes on top for the
custom look, plus a few small Python factories for KPI tiles, pills, and
empty-states so they look identical to what we had in Streamlit.
"""
from __future__ import annotations

from typing import Literal

from nicegui import ui

# Tailwind class palette — used by the helpers so all components share tokens.
PILL_CLASSES = {
    "indigo": "bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-300",
    "green": "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400",
    "amber": "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300",
    "red": "bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-400",
    "slate": "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300",
}

KPI_TONE_CLASSES = {
    "indigo": "text-indigo-600 dark:text-indigo-400",
    "green": "text-emerald-600 dark:text-emerald-400",
    "amber": "text-amber-600 dark:text-amber-400",
    "red": "text-rose-600 dark:text-rose-400",
    "slate": "text-slate-900 dark:text-slate-100",
}


def pill(text: str, tone: Literal["indigo", "green", "amber", "red", "slate"] = "slate") -> ui.element:
    """Render a small colored pill. Use as `pill('UNSAVED', 'amber')` inline in a row."""
    return ui.label(text).classes(
        f"px-2.5 py-0.5 rounded-full text-xs font-semibold tracking-wide "
        f"{PILL_CLASSES[tone]}"
    )


def kpi(label: str, value: str | int, tone: str = "slate") -> ui.element:
    """KPI tile — used in dashboards. Returns the wrapping card so callers can
    classes() further (e.g. add a width)."""
    with ui.card().classes(
        "p-4 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 "
        "bg-white dark:bg-slate-800 w-full"
    ) as card:
        ui.label(label).classes(
            "text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400"
        )
        ui.label(str(value)).classes(
            f"text-3xl font-bold leading-tight mt-1 {KPI_TONE_CLASSES.get(tone, KPI_TONE_CLASSES['slate'])}"
        )
    return card


def empty_state(title: str, body: str) -> ui.element:
    """Dashed-border empty card with title + body."""
    with ui.card().classes(
        "w-full p-12 rounded-xl border border-dashed border-slate-300 dark:border-slate-700 "
        "bg-white dark:bg-slate-800 text-center"
    ) as card:
        ui.label(title).classes(
            "text-lg font-semibold text-slate-900 dark:text-slate-100"
        )
        ui.label(body).classes(
            "text-sm text-slate-500 dark:text-slate-400 mt-1"
        )
    return card


def section_header(title: str, subtitle: str | None = None) -> None:
    """Page header — title + optional subtitle."""
    with ui.column().classes("w-full mb-4 gap-1"):
        ui.label(title).classes(
            "text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-50"
        )
        if subtitle:
            ui.label(subtitle).classes(
                "text-sm text-slate-600 dark:text-slate-400"
            )


def small_label(text: str) -> ui.element:
    """Small uppercase label — use to introduce a row of widgets."""
    return ui.label(text).classes(
        "text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400"
    )


def copy_button(text: str, label: str = "Copy") -> ui.element:
    """Real one-click clipboard button (uses navigator.clipboard via NiceGUI's run_javascript)."""
    btn = ui.button(label, icon="content_copy")
    btn.classes(
        "bg-indigo-600 text-white hover:bg-indigo-500 rounded-lg "
        "shadow-sm font-medium text-sm"
    )

    def do_copy():
        # ui.run_javascript executes the snippet in the user's browser; the
        # JSON-escaped payload travels safely.
        import json as _json
        ui.run_javascript(
            f"navigator.clipboard.writeText({_json.dumps(text)})"
        )
        ui.notify("Copied to clipboard", color="positive", position="top")

    btn.on("click", do_copy)
    return btn


# ---------------------------------------------------------------------------
# Top-level layout shell — header + drawer applied to every page
# ---------------------------------------------------------------------------


def _apply_dark_class(is_dark: bool) -> None:
    """Flip body--dark on body, then trigger the global JS theming pass that
    sets inline background-color !important on every card/header/drawer.
    Inline styles win against Tailwind's bg-white regardless of specificity.
    """
    flag = "true" if is_dark else "false"
    ui.run_javascript(f"""
    (function() {{
      var apply = function() {{
        if (!document.body) return;
        document.body.classList.toggle('body--dark', {flag});
        document.body.classList.toggle('body--light', !{flag});
        document.documentElement.classList.toggle('dark', {flag});
        if (window.__vamosApplyTheme) window.__vamosApplyTheme();
      }};
      if (document.body) apply();
      else document.addEventListener('DOMContentLoaded', apply);
    }})();
    """)


NAV_LINKS = [
    ("/", "Home", "home"),
    ("/my-day", "My day", "wb_sunny"),
    ("/inbox", "Inbox", "inbox"),
    ("/team-status", "Team status", "groups"),
    ("/pr-queue", "PR queue", "rate_review"),
    ("/brief", "Brief", "person"),
    ("/settings", "Settings", "settings"),
    ("/help", "Help", "help_outline"),
]


def render_shell(active_route: str = "/") -> None:
    """Render the header + left drawer. Called at the top of every @ui.page handler."""
    from . import state as state_mod
    from vamos.core import boards as boards_mod

    # Apply dark mode. We toggle Quasar's body--dark class explicitly via JS
    # because ui.dark_mode().enable()/disable() doesn't reliably flip it in
    # NiceGUI 2.x — and that class is what every CSS rule in main.py keys off.
    is_dark = state_mod.get_dark_mode()
    dark = ui.dark_mode(value=is_dark)
    _apply_dark_class(is_dark)

    # --- Header ---
    with ui.header(elevated=False).classes(
        "bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 "
        "items-center px-4 py-2"
    ):
        with ui.row().classes("items-center gap-3 flex-grow"):
            ui.icon("rocket_launch").classes("text-indigo-600 dark:text-indigo-400 text-2xl")
            ui.label("vamos").classes(
                "text-lg font-bold tracking-tight text-slate-900 dark:text-slate-50"
            )
            ui.label("HaloMD agent suite").classes(
                "text-xs text-slate-500 dark:text-slate-400 ml-1"
            )

        with ui.row().classes("items-center gap-2"):
            # Profile selector
            profile_select = ui.select(
                options={"": "(default)", "personal": "personal", "team": "team"},
                value=state_mod.get_profile() or "",
                label="Profile",
            ).classes("w-32")
            profile_select.on("update:model-value",
                              lambda e: state_mod.set_profile(e.args or None))

            # Board selector
            try:
                board_options = {"": "(use .env paths)"}
                for n in boards_mod.board_names(include_all=True):
                    board_options[n] = n
            except Exception:
                board_options = {"": "(use .env paths)"}
            board_select = ui.select(
                options=board_options,
                value=state_mod.get_board() or "",
                label="Board",
            ).classes("w-48")
            board_select.on("update:model-value",
                            lambda e: state_mod.set_board(e.args or None))

            # Dark-mode toggle — flips body--dark on body via JS so our CSS
            # rules in main.py (which key off body--dark) actually fire.
            def toggle_dark():
                new_val = not state_mod.get_dark_mode()
                state_mod.set_dark_mode(new_val)
                if new_val:
                    dark.enable()
                else:
                    dark.disable()
                _apply_dark_class(new_val)
            ui.button(icon="dark_mode", on_click=toggle_dark).props("flat round").classes(
                "text-slate-600 dark:text-slate-300"
            )

    # --- Left drawer (nav) ---
    with ui.left_drawer(value=True, fixed=True, bordered=True).classes(
        "bg-slate-50 dark:bg-slate-900 p-2"
    ):
        for path, label, icon in NAV_LINKS:
            is_active = path == active_route
            classes = (
                "w-full justify-start gap-3 px-3 py-2 rounded-lg text-sm font-medium "
                + ("bg-indigo-50 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-300"
                   if is_active else
                   "text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800")
            )
            ui.link(label, path).classes(classes)

        # Connection status pill
        ui.separator().classes("my-3")
        try:
            cfg = state_mod.get_cfg()
            with ui.column().classes("gap-1 px-3 py-2 rounded-lg "
                                     "bg-emerald-50 dark:bg-emerald-900/20 "
                                     "border border-emerald-200 dark:border-emerald-800"):
                ui.label("CONNECTED").classes(
                    "text-xs font-bold tracking-wider text-emerald-700 dark:text-emerald-400"
                )
                ui.label(cfg.ado_project).classes(
                    "text-sm text-slate-900 dark:text-slate-100"
                )
                ui.label(cfg.ado_org_url.replace("https://", "").rstrip("/")).classes(
                    "text-xs text-slate-500 dark:text-slate-400"
                )
        except SystemExit:
            with ui.column().classes("gap-1 px-3 py-2 rounded-lg "
                                     "bg-rose-50 dark:bg-rose-900/20 "
                                     "border border-rose-200 dark:border-rose-800"):
                ui.label("CONFIG ERROR").classes(
                    "text-xs font-bold tracking-wider text-rose-700 dark:text-rose-400"
                )
                ui.label("Check .env / Settings").classes(
                    "text-xs text-slate-600 dark:text-slate-400"
                )
