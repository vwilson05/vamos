"""My day — daily flow + editable markdown + EOD copy + standup + quick capture."""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from nicegui import ui

from vamos import sod, sync, eod, standup as standup_mod, capture as capture_mod
from vamos import prep as prep_mod
from vamos.markdown_io import daily_path

from .. import state as state_mod, theme
from ..streaming import run_with_logs


@ui.page("/my-day")
def my_day_page():
    theme.render_shell(active_route="/")
    cfg = state_mod.get_cfg()
    today = date.today()
    md_path = daily_path(cfg.work_dir, today)

    with ui.column().classes("p-6 max-w-7xl mx-auto w-full gap-4"):
        theme.section_header(
            today.strftime("%A, %B %d, %Y"),
            subtitle=f"work/{today.isoformat()}.md  ·  edits saved on Save click",
        )

        # ============================================================
        # Today's prep
        # ============================================================
        with ui.row().classes("w-full items-center"):
            theme.small_label("Today's prep")
            ui.space()
            prep_btn = ui.button("Run prep", icon="auto_awesome").props("outline")

        prep_container = ui.column().classes("w-full")

        async def do_prep():
            try:
                await run_with_logs(
                    "Morning prep — SOD + inbox + standup",
                    prep_mod.run, cfg, day=today,
                )
                ui.notify("Prep done", color="positive")
                ui.navigate.reload()
            except Exception as exc:
                ui.notify(f"Prep failed: {exc}", color="negative")

        prep_btn.on("click", do_prep)

        cached_standup = prep_mod.read_cached_standup(cfg, day=today)
        cached_inbox = prep_mod.read_cached_inbox(cfg, day=today)

        with ui.row().classes("w-full gap-4 flex-wrap"):
            # Standup card
            with ui.card().classes(
                "flex-1 min-w-96 p-4 rounded-xl border border-slate-200 dark:border-slate-700 "
                "bg-white dark:bg-slate-800"
            ):
                ui.label("Standup brief").classes(
                    "font-bold text-slate-900 dark:text-slate-50 mb-2"
                )
                if cached_standup:
                    ui.markdown(cached_standup).classes(
                        "text-sm text-slate-700 dark:text-slate-300"
                    )
                    with ui.row().classes("items-center mt-2 gap-3"):
                        theme.copy_button(cached_standup, label="Copy")
                        ui.label(f"Cached for {today.isoformat()}").classes(
                            "text-xs text-slate-500 dark:text-slate-400"
                        )
                else:
                    theme.empty_state(
                        "No standup yet",
                        "Click Run prep above (or run `vamos prep` from a terminal).",
                    )

            # Inbox preview card
            with ui.card().classes(
                "flex-1 min-w-96 p-4 rounded-xl border border-slate-200 dark:border-slate-700 "
                "bg-white dark:bg-slate-800"
            ):
                ui.label("Inbox preview").classes(
                    "font-bold text-slate-900 dark:text-slate-50 mb-2"
                )
                if cached_inbox is None:
                    theme.empty_state(
                        "No inbox cached",
                        "Click Run prep above to build it.",
                    )
                elif not cached_inbox:
                    ui.label("Nothing wants your attention.").classes(
                        "text-sm text-slate-500 dark:text-slate-400"
                    )
                else:
                    KIND_TONES = {
                        "mention": "red", "review-request": "amber",
                        "new-assignment": "indigo",
                    }
                    for it in cached_inbox[:6]:
                        with ui.row().classes(
                            "py-2 border-b border-slate-100 dark:border-slate-700 "
                            "last:border-b-0 w-full items-start gap-2"
                        ):
                            tone = KIND_TONES.get(it.get("kind"), "slate")
                            theme.pill(it.get("kind", "").replace("-", " "), tone)
                            with ui.column().classes("flex-1 gap-0"):
                                title = (it.get("title") or "")[:90]
                                ui.label(title).classes(
                                    "text-sm font-medium text-slate-900 dark:text-slate-100"
                                )
                                ui.label(f"by {it.get('actor', '?')}").classes(
                                    "text-xs text-slate-500 dark:text-slate-400"
                                )
                    if len(cached_inbox) > 6:
                        ui.label(
                            f"... and {len(cached_inbox) - 6} more — open the Inbox page."
                        ).classes("text-xs text-slate-500 dark:text-slate-400 mt-2")

        ui.separator().classes("my-2")

        # ============================================================
        # Editor + actions side-by-side
        # ============================================================
        with ui.row().classes("w-full gap-4"):
            # Editor
            with ui.column().classes("flex-1 min-w-0 gap-2"):
                if not md_path.exists():
                    theme.empty_state(
                        f"No markdown for {today.isoformat()}",
                        "Click Run SOD in the Actions panel.",
                    )
                else:
                    initial = md_path.read_text(encoding="utf-8")
                    with ui.tabs().classes("w-full") as tabs:
                        tab_edit = ui.tab("Edit")
                        tab_preview = ui.tab("Preview")

                    with ui.tab_panels(tabs, value=tab_edit).classes("w-full"):
                        with ui.tab_panel(tab_edit):
                            editor = ui.textarea(value=initial).props("outlined").classes(
                                "w-full font-mono text-sm"
                            )
                            editor._props["input-style"] = "min-height: 500px"
                            editor.update()

                            with ui.row().classes("items-center gap-2 mt-2"):
                                save_btn = ui.button("Save", icon="save").props("color=primary")
                                reload_btn = ui.button("Reload", icon="refresh").props("outline")
                                status_label = ui.label(
                                    f"last saved {datetime.fromtimestamp(md_path.stat().st_mtime).strftime('%H:%M:%S')}"
                                ).classes("text-xs text-slate-500 dark:text-slate-400 ml-2")

                            def do_save():
                                md_path.write_text(editor.value, encoding="utf-8")
                                ui.notify(f"Saved {md_path.name}", color="positive")
                                status_label.set_text(
                                    f"last saved {datetime.now().strftime('%H:%M:%S')}"
                                )

                            def do_reload():
                                editor.value = md_path.read_text(encoding="utf-8")
                                editor.update()

                            save_btn.on("click", do_save)
                            reload_btn.on("click", do_reload)

                        with ui.tab_panel(tab_preview):
                            preview = ui.markdown(initial).classes("prose dark:prose-invert max-w-none")

                            def refresh_preview():
                                preview.set_content(editor.value)

                            tabs.on("update:model-value",
                                    lambda e: refresh_preview() if e.args == "Preview" else None)

            # Actions panel
            with ui.column().classes("w-80 gap-3"):
                with ui.card().classes(
                    "p-4 rounded-xl border border-slate-200 dark:border-slate-700 "
                    "bg-white dark:bg-slate-800 w-full"
                ):
                    ui.label("Actions").classes("font-bold text-base text-slate-900 dark:text-slate-50")

                    sod_btn = ui.button("Run SOD", icon="wb_sunny").classes("w-full")

                    async def do_sod():
                        try:
                            await run_with_logs(
                                "Pulling assigned tickets (SOD)",
                                sod.run, cfg, force=False, day=today,
                            )
                            ui.notify(f"Wrote {md_path.name}", color="positive")
                            ui.navigate.reload()
                        except Exception as exc:
                            ui.notify(f"SOD failed: {exc}", color="negative")
                    sod_btn.on("click", do_sod)

                    theme.small_label("Sync")

                    async def do_sync(dry: bool):
                        try:
                            result = await run_with_logs(
                                f"Sync ({'dry-run' if dry else 'live'})",
                                sync.run, cfg, dry_run=dry, day=today,
                            )
                            ui.notify(
                                f"Proposed {result.actions_proposed} · Failed {result.actions_failed}",
                                color="positive" if result.actions_failed == 0 else "warning",
                            )
                        except Exception as exc:
                            ui.notify(f"Sync failed: {exc}", color="negative")

                    ui.button("Dry-run sync", icon="search",
                              on_click=lambda: do_sync(True)).props("outline").classes("w-full")
                    ui.button("Apply sync", icon="sync",
                              on_click=lambda: do_sync(False)).props("color=primary").classes("w-full")

                    theme.small_label("End of day")
                    skip_post = ui.checkbox("Don't post (just generate)", value=True).classes("text-sm")

                    async def do_eod():
                        try:
                            text = await run_with_logs(
                                "Generating EOD",
                                eod.run, cfg, dry_run=False, skip_sync=False,
                                skip_post=skip_post.value, skip_slack=skip_post.value, day=today,
                            )
                            # Stash in user storage — show inline below
                            from nicegui import app as nicegui_app
                            nicegui_app.storage.user["last_eod"] = text
                            ui.notify("EOD ready below", color="positive")
                            ui.navigate.reload()
                        except Exception as exc:
                            ui.notify(f"EOD failed: {exc}", color="negative")
                    ui.button("Run EOD", icon="nights_stay", on_click=do_eod).classes("w-full")

                    theme.small_label("Standup")
                    async def do_standup():
                        try:
                            text = await run_with_logs(
                                "Building standup", standup_mod.run, cfg, day=today,
                            )
                            cfg.state_dir.joinpath("standup").mkdir(parents=True, exist_ok=True)
                            (cfg.state_dir / "standup" / f"{today.isoformat()}.md").write_text(text, encoding="utf-8")
                            ui.notify("Standup saved — refresh to see it", color="positive")
                            ui.navigate.reload()
                        except Exception as exc:
                            ui.notify(f"Standup failed: {exc}", color="negative")
                    ui.button("Generate standup", icon="record_voice_over",
                              on_click=do_standup).props("outline").classes("w-full")

                    theme.small_label("Quick capture")
                    cap_text = ui.textarea(label="Capture", placeholder="Paste a thought…").props("outlined").classes("w-full")
                    cap_text._props["input-style"] = "min-height: 80px"
                    cap_customer = ui.input(label="Customer (optional)").props("outlined").classes("w-full")

                    def do_capture():
                        if not (cap_text.value or "").strip():
                            ui.notify("Type something to capture", color="warning")
                            return
                        try:
                            capture_mod.run(
                                cfg, text=cap_text.value,
                                customer=(cap_customer.value or None), day=today,
                            )
                            cap_text.value = ""
                            cap_text.update()
                            ui.notify("Captured — refresh to see [NEW] section", color="positive")
                            ui.navigate.reload()
                        except Exception as exc:
                            ui.notify(f"Capture failed: {exc}", color="negative")
                    ui.button("Append [NEW]", icon="add",
                              on_click=do_capture).props("outline").classes("w-full")

        # ============================================================
        # EOD output (if generated)
        # ============================================================
        from nicegui import app as nicegui_app
        last_eod = nicegui_app.storage.user.get("last_eod") if nicegui_app.storage.user else None
        if last_eod:
            ui.separator().classes("my-2")
            theme.section_header(
                "End-of-day summary",
                subtitle="Click Copy to put it on your clipboard — paste anywhere.",
            )
            with ui.row().classes("items-center gap-3"):
                theme.copy_button(last_eod, label="Copy EOD")
                ui.label("Rendered below; raw markdown after.").classes(
                    "text-xs text-slate-500 dark:text-slate-400"
                )
            with ui.card().classes(
                "p-4 rounded-xl border border-slate-200 dark:border-slate-700 "
                "bg-white dark:bg-slate-800 w-full"
            ):
                ui.markdown(last_eod).classes("prose dark:prose-invert max-w-none")
            with ui.expansion("Show raw markdown source").classes("w-full"):
                ui.code(last_eod, language="markdown")
