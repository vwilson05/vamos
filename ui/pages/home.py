"""Home — at-a-glance KPIs + welcome card."""
from __future__ import annotations

import json
from datetime import date

from nicegui import ui

from .. import state as state_mod, theme


@ui.page("/")
def home_page():
    theme.render_shell(active_route="/")
    cfg = state_mod.get_cfg()

    with ui.column().classes("p-6 max-w-6xl mx-auto w-full gap-4"):
        ui.label("vamos").classes(
            "text-4xl font-bold tracking-tight text-slate-900 dark:text-slate-50"
        )
        ui.label("HaloMD agent suite — personal flow, team reporting, PR review").classes(
            "text-base text-slate-600 dark:text-slate-400"
        )

        theme.small_label("At a glance")

        # Pull the latest cached hygiene summary if present
        hygiene_summary: dict[str, int] = {}
        hygiene_dir = cfg.state_dir / "hygiene"
        if hygiene_dir.exists():
            files = sorted(hygiene_dir.glob("*.json"), reverse=True)
            if files:
                try:
                    payload = json.loads(files[0].read_text())
                    hygiene_summary = payload.get("summary", {}) or {}
                except (json.JSONDecodeError, OSError):
                    pass

        has_today = (cfg.work_dir / f"{date.today().isoformat()}.md").exists()

        with ui.row().classes("w-full gap-4 flex-wrap"):
            with ui.column().classes("flex-1 min-w-48"):
                theme.kpi(
                    "Today's MD",
                    "ready" if has_today else "—",
                    tone="green" if has_today else "slate",
                )
            with ui.column().classes("flex-1 min-w-48"):
                n = hygiene_summary.get("blocker", 0)
                theme.kpi("Hygiene blockers", str(n) if n else "—",
                          tone="red" if n else "slate")
            with ui.column().classes("flex-1 min-w-48"):
                n = hygiene_summary.get("should-fix", 0)
                theme.kpi("Should-fix", str(n) if n else "—",
                          tone="amber" if n else "slate")
            with ui.column().classes("flex-1 min-w-48"):
                n = hygiene_summary.get("nit", 0)
                theme.kpi("Nits", str(n) if n else "—",
                          tone="indigo" if n else "slate")

        with ui.card().classes(
            "mt-4 p-6 w-full border border-slate-200 dark:border-slate-700 "
            "bg-white dark:bg-slate-800 rounded-xl"
        ):
            ui.label("Welcome").classes(
                "text-xl font-bold text-slate-900 dark:text-slate-50"
            )
            ui.markdown("""
- **My day** — view + edit today's markdown, run sod / sync / eod, generate standup, quick-capture meeting notes.
- **Team status** — metrics, healthcheck, hygiene (with AI-assisted **Clean** buttons), trends, customer breakdown, at-risk scan.
- **PR queue** — triaged queue with "blocked on me" first; review-load distribution; trigger ad-hoc reviews.
- **Inbox** — review requests, comments, mentions, P1/P2 assignments — all in one feed.
- **Brief** — 1:1 prep per engineer, sprint retro starter — copy-pastable.
- **Settings** — edit `.env` + `crons.yml` here in the browser.
- **Help** — every CLI command, env var, hygiene rule, plus a What's new changelog.
            """).classes("text-sm text-slate-700 dark:text-slate-300")

        ui.label(
            f"work_dir: {cfg.work_dir}  ·  state_dir: {cfg.state_dir}  ·  "
            f"read_only: {cfg.ado_read_only}"
        ).classes("text-xs text-slate-500 dark:text-slate-400 mt-4")
