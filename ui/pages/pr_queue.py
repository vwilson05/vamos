"""PR queue — triaged review queue with blocked-on-me grouping."""
from __future__ import annotations

from nicegui import ui

from vamos.pr_review import runner as pr_runner, queue as pr_queue

from .. import state as state_mod, theme
from ..streaming import run_with_logs


@ui.page("/pr-queue")
def pr_queue_page():
    theme.render_shell(active_route="/pr-queue")
    cfg = state_mod.get_cfg()

    with ui.column().classes("p-6 max-w-7xl mx-auto w-full gap-4"):
        theme.section_header(
            "PR queue",
            subtitle="Triaged across all repos · blocked-on-me first · trigger ad-hoc reviews",
        )

        with ui.tabs().classes("w-full") as tabs:
            tab_queue = ui.tab("Triaged queue", icon="rate_review")
            tab_load = ui.tab("Review load", icon="bar_chart")
            tab_review = ui.tab("Run review", icon="play_arrow")

        with ui.tab_panels(tabs, value=tab_queue).classes("w-full"):
            with ui.tab_panel(tab_queue):
                _render_queue(cfg)
            with ui.tab_panel(tab_load):
                _render_load(cfg)
            with ui.tab_panel(tab_review):
                _render_review_form(cfg)


def _render_queue(cfg):
    output = ui.column().classes("w-full mt-4")

    with ui.row().classes("w-full items-end gap-3"):
        repo_input = ui.input(
            label="Repo (blank = all repos)",
        ).props("outlined dense").classes("flex-1")
        refresh_btn = ui.button("Refresh queue", icon="refresh").props("color=primary")

    async def do_refresh():
        try:
            items = await run_with_logs(
                "Building triaged review queue",
                pr_queue.build_queue, cfg, repo=(repo_input.value or None),
            )
            output.clear()
            _render_queue_items(output, items)
        except Exception as exc:
            ui.notify(f"Queue failed: {exc}", color="negative")
    refresh_btn.on("click", do_refresh)


def _render_queue_items(parent, items):
    with parent:
        if not items:
            theme.empty_state("No PRs loaded", "Click Refresh queue above.")
            return

        bom = [q for q in items if q.blocked_on_me]
        mine = [q for q in items if not q.blocked_on_me and q.role in ("author", "reviewer", "both")]
        rest = [q for q in items if not q.blocked_on_me and q.role == "observer"]

        if bom:
            ui.label("Blocked on me").classes(
                "font-bold text-base text-slate-900 dark:text-slate-50 mt-4"
            )
            for q in bom:
                _render_pr_card(q)
        if mine:
            ui.label("Mine — author or reviewer").classes(
                "font-bold text-base text-slate-900 dark:text-slate-50 mt-4"
            )
            for q in mine:
                _render_pr_card(q)
        if rest:
            with ui.expansion(f"All other active PRs ({len(rest)})").classes("w-full"):
                for q in rest:
                    _render_pr_card(q)


def _render_pr_card(q):
    age_tone = "red" if q.age_days > 5 else ("amber" if q.age_days > 2 else "slate")
    role_tone = {"author": "indigo", "reviewer": "amber", "both": "indigo"}.get(q.role, "slate")
    with ui.card().classes(
        "p-3 rounded-lg border border-slate-200 dark:border-slate-700 "
        "bg-white dark:bg-slate-800 w-full mb-2"
    ):
        with ui.row().classes("w-full items-start justify-between"):
            with ui.column().classes("flex-1 min-w-0 gap-1"):
                ui.link(f"#{q.pr_id} — {q.title}", q.url, new_tab=True).classes(
                    "text-sm font-semibold text-slate-900 dark:text-slate-100 truncate"
                )
                ui.label(
                    f"{q.repo}  ·  by {q.author}  ·  {q.source_branch} → {q.target_branch}"
                ).classes("text-xs text-slate-500 dark:text-slate-400")
            with ui.row().classes("gap-1 flex-wrap items-start"):
                if q.blocked_on_me:
                    theme.pill("BLOCKED ON ME", "red")
                theme.pill(q.role.upper(), role_tone)
                if q.is_draft:
                    theme.pill("DRAFT", "slate")
                if q.buddy_skipped:
                    theme.pill(f"BUDDY SKIPPED · {q.buddy_skipped}", "amber")
                theme.pill(f"{q.age_days}d", age_tone)


def _render_load(cfg):
    output = ui.column().classes("w-full mt-4")
    btn = ui.button("Compute review load", icon="bar_chart").props("color=primary")

    async def do_compute():
        try:
            loads = await run_with_logs(
                "Counting reviewer assignments across every repo",
                pr_queue.review_load, cfg,
            )
            output.clear()
            with output:
                if not loads:
                    theme.empty_state("No data", "No active PRs found.")
                    return
                max_n = max(loads.values())
                with ui.card().classes(
                    "p-4 w-full rounded-xl border border-slate-200 dark:border-slate-700 "
                    "bg-white dark:bg-slate-800"
                ):
                    for name, n in loads.items():
                        with ui.row().classes(
                            "py-2 w-full items-center border-b border-slate-100 dark:border-slate-700 last:border-b-0"
                        ):
                            ui.label(name).classes("text-sm flex-1 text-slate-900 dark:text-slate-100")
                            with ui.element("div").classes(
                                "flex-2 mx-2 h-2 rounded-full bg-slate-200 dark:bg-slate-700 relative w-full"
                            ).style(f"max-width: 320px"):
                                ui.element("div").classes(
                                    "absolute top-0 left-0 h-2 rounded-full bg-indigo-500"
                                ).style(f"width: {(n / max_n) * 100}%")
                            ui.label(str(n)).classes("text-xs font-mono text-slate-500 dark:text-slate-400 w-8 text-right")
        except Exception as exc:
            ui.notify(f"Load failed: {exc}", color="negative")
    btn.on("click", do_compute)


def _render_review_form(cfg):
    with ui.card().classes(
        "p-4 w-full rounded-xl border border-slate-200 dark:border-slate-700 "
        "bg-white dark:bg-slate-800"
    ):
        with ui.row().classes("w-full items-end gap-3 flex-wrap"):
            pr_id_input = ui.number("PR id", value=1, min=1, step=1).props(
                "outlined dense"
            ).classes("w-32")
            repo_input = ui.input(
                label="Repo (optional)",
            ).props("outlined dense").classes("flex-1 min-w-48")
            no_post = ui.checkbox("Don't post (local only)", value=True)
            review_btn = ui.button("Review PR", icon="reviews").props("color=primary")

        async def do_review():
            try:
                code = await run_with_logs(
                    f"Reviewing PR #{int(pr_id_input.value)}",
                    pr_runner.run, cfg,
                    pr_id=int(pr_id_input.value),
                    repo=(repo_input.value or None),
                    interactive=False, no_post=no_post.value, watch=False,
                )
                if code == 0:
                    ui.notify("Review complete", color="positive")
                else:
                    ui.notify(f"Review exited with code {code}", color="warning")
            except Exception as exc:
                ui.notify(f"Review failed: {exc}", color="negative")
        review_btn.on("click", do_review)

        ui.label(
            "Reviews saved to state/pr-review/logs/. "
            "Comments include <!-- vamos:pr-review --> so re-runs never double-post."
        ).classes("text-xs text-slate-500 dark:text-slate-400 mt-3")
