"""My day — three sections that mirror the real workflow:

  1. Stand-up brief (DSU) — auto-drafted from yesterday + today + blockers.
  2. Today's tickets (SOD) — editable markdown of your assigned items.
  3. End of day (EOD) — final summary, copy button, post action.

Inbox preview sits next to the stand-up so you can scan attention items at the
same time you scan your status. Quick capture sits under SOD as a small card.
"""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from nicegui import ui, app

from vamos import sod, sync, eod, standup as standup_mod, capture as capture_mod
from vamos import prep as prep_mod
from vamos.markdown_io import daily_path

from .. import state as state_mod, theme
from ..streaming import run_with_logs


@ui.page("/my-day")
def my_day_page():
    theme.render_shell(active_route="/my-day")
    cfg = state_mod.get_cfg()
    today = date.today()
    md_path = daily_path(cfg.work_dir, today)

    with ui.column().classes("p-6 max-w-7xl mx-auto w-full gap-6"):

        # ── Page header ─────────────────────────────────────────
        with ui.row().classes("w-full items-end justify-between gap-3"):
            with ui.column().classes("gap-1"):
                ui.label(today.strftime("%A, %B %d, %Y")).classes(
                    "text-3xl font-bold tracking-tight text-slate-900 dark:text-slate-50"
                )
                ui.label(f"work/{today.isoformat()}.md").classes(
                    "text-sm text-slate-500 dark:text-slate-400 font-mono"
                )
            prep_btn = ui.button("Run prep (SOD + inbox + standup)",
                                 icon="auto_awesome").props("color=primary")

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

        # ── Section 1: STAND-UP + INBOX (top of day) ─────────────
        theme.small_label("Stand-up brief")
        with ui.row().classes("w-full gap-4 flex-wrap items-stretch"):
            # Stand-up card
            with ui.card().classes(
                "flex-1 min-w-96 p-5 rounded-xl border border-slate-200 dark:border-slate-700 "
                "bg-white dark:bg-slate-800"
            ):
                with ui.row().classes("items-center justify-between w-full mb-2"):
                    ui.label("Yesterday / Today / Blockers").classes(
                        "text-base font-bold text-slate-900 dark:text-slate-50"
                    )
                    if cached_standup:
                        theme.copy_button(cached_standup, label="Copy")

                if cached_standup:
                    ui.markdown(cached_standup).classes(
                        "prose dark:prose-invert max-w-none text-sm"
                    )
                else:
                    theme.empty_state(
                        "No stand-up yet",
                        "Click Run prep above, or run `vamos standup` from a terminal.",
                    )

                async def do_standup():
                    try:
                        text = await run_with_logs(
                            "Building stand-up", standup_mod.run, cfg, day=today,
                        )
                        cfg.state_dir.joinpath("standup").mkdir(parents=True, exist_ok=True)
                        (cfg.state_dir / "standup" / f"{today.isoformat()}.md").write_text(
                            text, encoding="utf-8"
                        )
                        ui.notify("Stand-up regenerated", color="positive")
                        ui.navigate.reload()
                    except Exception as exc:
                        ui.notify(f"Stand-up failed: {exc}", color="negative")
                ui.button(
                    "Regenerate", icon="refresh",
                    on_click=do_standup,
                ).props("flat dense").classes("self-start mt-2")

            # Inbox preview card
            with ui.card().classes(
                "flex-1 min-w-80 p-5 rounded-xl border border-slate-200 dark:border-slate-700 "
                "bg-white dark:bg-slate-800"
            ):
                with ui.row().classes("items-center justify-between w-full mb-2"):
                    ui.label("Inbox preview").classes(
                        "text-base font-bold text-slate-900 dark:text-slate-50"
                    )
                    ui.link("Open inbox →", "/inbox").classes(
                        "text-xs text-indigo-600 dark:text-indigo-400 no-underline"
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
                    for it in cached_inbox[:5]:
                        with ui.row().classes(
                            "py-2 border-b border-slate-100 dark:border-slate-700 "
                            "last:border-b-0 w-full items-start gap-2 flex-nowrap"
                        ):
                            tone = KIND_TONES.get(it.get("kind"), "slate")
                            theme.pill(it.get("kind", "").replace("-", " "), tone)
                            with ui.column().classes(
                                "flex-1 gap-0 min-w-0 overflow-hidden"
                            ):
                                title = it.get("title") or ""
                                ui.label(title).classes(
                                    "text-sm font-medium text-slate-900 "
                                    "dark:text-slate-100 w-full"
                                ).style(
                                    "white-space: normal; overflow-wrap: anywhere;"
                                )
                                ui.label(f"by {it.get('actor', '?')}").classes(
                                    "text-xs text-slate-500 dark:text-slate-400"
                                )
                    if len(cached_inbox) > 5:
                        ui.label(
                            f"... and {len(cached_inbox) - 5} more"
                        ).classes("text-xs text-slate-500 dark:text-slate-400 mt-2 italic")

        # ── Section 2: TODAY'S TICKETS (SOD) ─────────────────────
        theme.small_label("Today's tickets")
        with ui.card().classes(
            "w-full p-5 rounded-xl border border-slate-200 dark:border-slate-700 "
            "bg-white dark:bg-slate-800"
        ):
            with ui.row().classes("w-full items-center justify-between mb-3"):
                ui.label("Markdown — edit your status, paste notes, mark items closed").classes(
                    "text-base font-bold text-slate-900 dark:text-slate-50"
                )
                # Inline action row for SOD
                with ui.row().classes("items-center gap-2"):
                    sod_btn = ui.button("Run SOD", icon="wb_sunny").props("outline dense")
                    ui.button("Dry-run sync", icon="search",
                              on_click=lambda: do_sync(True)).props("outline dense")
                    ui.button("Apply sync", icon="sync",
                              on_click=lambda: do_sync(False)).props("color=primary dense")

            async def do_sod():
                try:
                    path = await run_with_logs(
                        "Pulling assigned tickets (SOD)",
                        sod.run, cfg, force=False, day=today,
                    )
                    ui.notify(f"Wrote {Path(path).name}", color="positive")
                    ui.navigate.reload()
                except Exception as exc:
                    ui.notify(f"SOD failed: {exc}", color="negative")
            sod_btn.on("click", do_sod)

            async def do_sync(dry: bool):
                try:
                    result = await run_with_logs(
                        f"Sync ({'dry-run' if dry else 'live'})",
                        sync.run, cfg, dry_run=dry, day=today,
                    )
                    ui.notify(
                        f"Proposed {result.actions_proposed} · "
                        f"Executed {result.actions_executed} · Failed {result.actions_failed}",
                        color="positive" if result.actions_failed == 0 else "warning",
                    )
                except Exception as exc:
                    ui.notify(f"Sync failed: {exc}", color="negative")

            if not md_path.exists():
                theme.empty_state(
                    f"No markdown for {today.isoformat()} yet",
                    "Click Run SOD to pull today's assigned tickets from ADO.",
                )
            else:
                initial = md_path.read_text(encoding="utf-8")
                with ui.tabs().classes("w-full") as tabs:
                    tab_edit = ui.tab("Edit", icon="edit")
                    tab_preview = ui.tab("Preview", icon="visibility")

                with ui.tab_panels(tabs, value=tab_edit).classes("w-full"):
                    with ui.tab_panel(tab_edit):
                        editor = ui.textarea(value=initial).props("outlined").classes(
                            "w-full font-mono text-sm"
                        )
                        editor._props["input-style"] = "min-height: 480px"
                        editor.update()

                        with ui.row().classes("items-center gap-2 mt-2"):
                            save_btn = ui.button("Save", icon="save").props("color=primary dense")
                            reload_btn = ui.button("Reload from disk", icon="refresh").props("outline dense")
                            status_label = ui.label(
                                f"Last saved {datetime.fromtimestamp(md_path.stat().st_mtime).strftime('%H:%M:%S')}"
                            ).classes("text-xs text-slate-500 dark:text-slate-400 ml-2")

                        def do_save():
                            md_path.write_text(editor.value, encoding="utf-8")
                            ui.notify(f"Saved {md_path.name}", color="positive")
                            status_label.set_text(
                                f"Last saved {datetime.now().strftime('%H:%M:%S')}"
                            )

                        def do_reload():
                            editor.value = md_path.read_text(encoding="utf-8")
                            editor.update()

                        save_btn.on("click", do_save)
                        reload_btn.on("click", do_reload)

                    with ui.tab_panel(tab_preview):
                        preview = ui.markdown(initial).classes(
                            "prose dark:prose-invert max-w-none"
                        )
                        tabs.on(
                            "update:model-value",
                            lambda e: preview.set_content(editor.value)
                            if e.args == "Preview" else None,
                        )

        # ── Quick capture (small, under SOD) ────────────────────
        with ui.expansion("Quick capture — drop a thought into today's MD",
                          icon="add_circle_outline").classes(
            "w-full bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 "
            "rounded-xl"
        ):
            cap_text = ui.textarea(
                label="Capture",
                placeholder="Paste a meeting note, idea, or bug — first line becomes the [NEW] title.",
            ).props("outlined").classes("w-full")
            cap_text._props["input-style"] = "min-height: 80px"
            with ui.row().classes("w-full gap-2 items-center mt-2"):
                cap_customer = ui.input(label="Customer (optional)",
                                        placeholder="Vituity, UHC, ...").props(
                    "outlined dense"
                ).classes("flex-1 max-w-64")
                ui.button("Append [NEW]", icon="add",
                          on_click=lambda: do_capture()).props("color=primary")

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
                    ui.notify("Captured — refreshing", color="positive")
                    ui.navigate.reload()
                except Exception as exc:
                    ui.notify(f"Capture failed: {exc}", color="negative")

        # ── Section 3: END OF DAY (EOD) ──────────────────────────
        theme.small_label("End of day")
        last_eod = app.storage.user.get("last_eod") if app.storage.user is not None else None
        with ui.card().classes(
            "w-full p-5 rounded-xl border border-slate-200 dark:border-slate-700 "
            "bg-white dark:bg-slate-800"
        ):
            with ui.row().classes("w-full items-center justify-between mb-3"):
                ui.label("Daily summary — final sync, post to Teams/Slack").classes(
                    "text-base font-bold text-slate-900 dark:text-slate-50"
                )
                with ui.row().classes("items-center gap-2"):
                    skip_post = ui.checkbox(
                        "Don't post (just generate)", value=True,
                    ).classes("text-sm")
                    eod_btn = ui.button("Run EOD", icon="nights_stay").props("color=primary")
                    if last_eod:
                        theme.copy_button(last_eod, label="Copy EOD")

            async def do_eod():
                try:
                    text = await run_with_logs(
                        "Generating EOD",
                        eod.run, cfg, dry_run=False, skip_sync=False,
                        skip_post=skip_post.value, skip_slack=skip_post.value, day=today,
                    )
                    app.storage.user["last_eod"] = text
                    ui.notify("EOD ready", color="positive")
                    ui.navigate.reload()
                except Exception as exc:
                    ui.notify(f"EOD failed: {exc}", color="negative")
            eod_btn.on("click", do_eod)

            if last_eod:
                ui.markdown(last_eod).classes(
                    "prose dark:prose-invert max-w-none text-sm"
                )
                with ui.expansion("Show raw markdown source",
                                  icon="code").classes("w-full mt-3"):
                    ui.code(last_eod, language="markdown")
            else:
                theme.empty_state(
                    "No EOD yet today",
                    "Click Run EOD to generate the end-of-day summary. "
                    "Tick \"Don't post\" to keep it local.",
                )
