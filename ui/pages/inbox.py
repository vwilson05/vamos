"""Inbox — unified attention feed."""
from __future__ import annotations

from nicegui import ui

from vamos import inbox as inbox_mod

from .. import state as state_mod, theme
from ..streaming import run_with_logs


@ui.page("/inbox")
def inbox_page():
    theme.render_shell(active_route="/inbox")
    cfg = state_mod.get_cfg()

    with ui.column().classes("p-6 max-w-7xl mx-auto w-full gap-4"):
        theme.section_header(
            "Inbox",
            subtitle="Things wanting your attention — review requests, comments, mentions, new P1/P2",
        )

        with ui.row().classes("w-full items-end gap-3"):
            hours = ui.number("Look-back (hours)", value=48, min=4, max=336, step=4).props(
                "outlined dense"
            ).classes("w-48")
            refresh_btn = ui.button("Refresh", icon="refresh").props("color=primary")
            ui.space()
            stats_label = ui.label("").classes("text-sm text-slate-500 dark:text-slate-400")

        results_container = ui.column().classes("w-full gap-3 mt-4")

        async def do_refresh():
            results_container.clear()
            try:
                items = await run_with_logs(
                    f"Building inbox (last {int(hours.value)}h, all repos)",
                    inbox_mod.build, cfg, since_hours=int(hours.value),
                )
                stats_label.set_text(f"{len(items)} item(s)")
                _render_items(results_container, items)
            except Exception as exc:
                ui.notify(f"Inbox failed: {exc}", color="negative")
        refresh_btn.on("click", do_refresh)


def _render_items(parent, items):
    KIND_LABEL = {
        "mention": "Mentions",
        "review-request": "Review requests",
        "new-assignment": "New high-priority assignments",
        "pr-comment": "PR comments",
        "ticket-comment": "Ticket comments",
    }
    KIND_TONE = {
        "mention": "red", "review-request": "amber",
        "new-assignment": "indigo", "pr-comment": "slate", "ticket-comment": "slate",
    }

    if not items:
        with parent:
            theme.empty_state("Inbox empty", "Nothing wants your attention right now.")
        return

    by_kind: dict[str, list] = {}
    for it in items:
        by_kind.setdefault(it.kind, []).append(it)

    for kind in ["mention", "review-request", "new-assignment", "pr-comment", "ticket-comment"]:
        group = by_kind.get(kind, [])
        if not group:
            continue
        with parent:
            with ui.row().classes("items-center gap-2 mt-3 mb-1"):
                ui.label(KIND_LABEL[kind]).classes(
                    "font-bold text-base text-slate-900 dark:text-slate-50"
                )
                theme.pill(str(len(group)), KIND_TONE[kind])

            for it in group[:25]:
                with ui.card().classes(
                    "p-3 rounded-lg border border-slate-200 dark:border-slate-700 "
                    "bg-white dark:bg-slate-800 w-full"
                ):
                    title = (it.title or "")[:140]
                    tid = it.ticket_id or it.pr_id
                    when_str = it.when.strftime("%a %m-%d %H:%M") if hasattr(it.when, "strftime") else str(it.when)

                    with ui.row().classes("items-baseline gap-2 w-full"):
                        ui.label(title).classes(
                            "text-sm font-semibold text-slate-900 dark:text-slate-100 flex-1"
                        )
                        if tid and it.url:
                            link_label = f"PR #{it.pr_id}" if it.pr_id else f"#{it.ticket_id}"
                            ui.link(link_label, it.url, new_tab=True).classes(
                                "text-xs text-indigo-600 dark:text-indigo-400"
                            )
                    ui.label(f"{when_str} · by {it.actor}").classes(
                        "text-xs text-slate-500 dark:text-slate-400"
                    )
                    if it.summary:
                        ui.label(it.summary).classes(
                            "text-sm text-slate-700 dark:text-slate-300 mt-1"
                        )
            if len(group) > 25:
                with parent:
                    ui.label(f"...and {len(group) - 25} more in this category.").classes(
                        "text-xs text-slate-500 dark:text-slate-400"
                    )
