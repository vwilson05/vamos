"""Brief — 1:1 brief generator + sprint retro starter."""
from __future__ import annotations

from nicegui import ui

from vamos import brief as brief_mod, retro as retro_mod

from .. import state as state_mod, theme
from ..streaming import run_with_logs


@ui.page("/brief")
def brief_page():
    theme.render_shell(active_route="/brief")
    cfg = state_mod.get_cfg()

    with ui.column().classes("p-6 max-w-6xl mx-auto w-full gap-4"):
        theme.section_header(
            "Manager briefs",
            subtitle="1:1 prep per engineer · sprint retro starter",
        )

        with ui.tabs().classes("w-full") as tabs:
            tab_oneonone = ui.tab("1:1 brief", icon="person")
            tab_retro = ui.tab("Sprint retro", icon="event_note")

        with ui.tab_panels(tabs, value=tab_oneonone).classes("w-full"):
            # =========================================================
            # 1:1 brief tab
            # =========================================================
            with ui.tab_panel(tab_oneonone):
                with ui.row().classes("w-full items-end gap-3"):
                    engineer_input = ui.input(
                        label="Engineer name or email",
                        placeholder="Victor Wilson",
                    ).props("outlined dense").classes("flex-1 min-w-64")
                    weeks = ui.number("Weeks", value=1, min=1, max=12).props(
                        "outlined dense"
                    ).classes("w-32")
                    load_btn = ui.button("Load engineer list", icon="download").props("outline")
                    gen_btn = ui.button("Generate brief", icon="auto_awesome").props("color=primary")

                output_container = ui.column().classes("w-full mt-4")

                async def do_load_engineers():
                    try:
                        engineers = await run_with_logs(
                            "Loading engineer list", brief_mod.list_engineers, cfg,
                        )
                        ui.notify(f"{len(engineers)} engineer(s) loaded", color="positive")
                        engineer_input._props["suggestions"] = engineers
                        engineer_input.update()
                    except Exception as exc:
                        ui.notify(f"List failed: {exc}", color="negative")
                load_btn.on("click", do_load_engineers)

                async def do_generate():
                    if not engineer_input.value:
                        ui.notify("Pick an engineer first.", color="warning")
                        return
                    output_container.clear()
                    try:
                        text = await run_with_logs(
                            f"Building 1:1 brief for {engineer_input.value}",
                            brief_mod.run, cfg,
                            engineer=engineer_input.value, weeks=int(weeks.value),
                        )
                        with output_container:
                            with ui.row().classes("items-center gap-3"):
                                theme.copy_button(text, label="Copy brief")
                                ui.label("Paste into your 1:1 doc.").classes(
                                    "text-sm text-slate-500 dark:text-slate-400"
                                )
                            with ui.card().classes(
                                "p-4 rounded-xl border border-slate-200 dark:border-slate-700 "
                                "bg-white dark:bg-slate-800 w-full mt-2"
                            ):
                                ui.markdown(text).classes(
                                    "prose dark:prose-invert max-w-none"
                                )
                            with ui.expansion("Raw markdown").classes("w-full"):
                                ui.code(text, language="markdown")
                    except Exception as exc:
                        ui.notify(f"Brief failed: {exc}", color="negative")
                gen_btn.on("click", do_generate)

            # =========================================================
            # Retro tab
            # =========================================================
            with ui.tab_panel(tab_retro):
                with ui.row().classes("w-full items-end gap-3"):
                    iter_input = ui.input(
                        label="Iteration path (blank = HYGIENE_ITERATION_PATH)",
                    ).props("outlined dense").classes("flex-1")
                    retro_weeks = ui.number("Weeks", value=2, min=1, max=8).props(
                        "outlined dense"
                    ).classes("w-32")
                    retro_btn = ui.button("Generate retro", icon="auto_awesome").props("color=primary")

                retro_container = ui.column().classes("w-full mt-4")

                async def do_retro():
                    retro_container.clear()
                    try:
                        text = await run_with_logs(
                            "Building retro starter",
                            retro_mod.run, cfg,
                            iteration_path=(iter_input.value or None),
                            weeks=int(retro_weeks.value),
                        )
                        with retro_container:
                            with ui.row().classes("items-center gap-3"):
                                theme.copy_button(text, label="Copy retro")
                            with ui.card().classes(
                                "p-4 rounded-xl border border-slate-200 dark:border-slate-700 "
                                "bg-white dark:bg-slate-800 w-full mt-2"
                            ):
                                ui.markdown(text).classes(
                                    "prose dark:prose-invert max-w-none"
                                )
                    except Exception as exc:
                        ui.notify(f"Retro failed: {exc}", color="negative")
                retro_btn.on("click", do_retro)
