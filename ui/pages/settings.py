"""Settings — edit .env files and crons.yml from the browser."""
from __future__ import annotations

from nicegui import ui

from vamos import settings as settings_mod
from vamos.ado import ADOClient

from .. import state as state_mod, theme


@ui.page("/settings")
def settings_page():
    theme.render_shell(active_route="/settings")

    with ui.column().classes("p-6 max-w-6xl mx-auto w-full gap-4"):
        theme.section_header(
            "Settings",
            subtitle="Edit .env, manage cron schedule, test the ADO connection — no terminal needed.",
        )

        with ui.tabs().classes("w-full") as tabs:
            tab_env = ui.tab(".env / credentials", icon="vpn_key")
            tab_crons = ui.tab("Cron schedule", icon="schedule")

        with ui.tab_panels(tabs, value=tab_env).classes("w-full"):
            with ui.tab_panel(tab_env):
                _render_env_editor()
            with ui.tab_panel(tab_crons):
                _render_cron_editor()


def _render_env_editor():
    profile_select = ui.toggle(
        {None: ".env (baseline)", "personal": ".env.personal", "team": ".env.team"},
        value=None,
    ).classes("w-full")

    container = ui.column().classes("w-full mt-3")

    def render_for_profile():
        container.clear()
        target = settings_mod.env_path(profile_select.value)
        current = settings_mod.read_env(target) if target.exists() else {}
        edits: dict[str, str] = {}

        with container:
            ui.label(f"Editing: {target}").classes(
                "text-xs text-slate-500 dark:text-slate-400"
            )
            reveal_secrets = ui.checkbox("Reveal secrets", value=False)

            schema = settings_mod.schema_by_section()
            for section, fields in schema.items():
                with ui.expansion(
                    section,
                    icon="folder",
                    value=section in ("ADO connection", "Channels"),
                ).classes(
                    "w-full bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg my-1"
                ):
                    for fd in fields:
                        stored = current.get(fd.key, "")
                        if fd.kind == "bool":
                            val = stored.strip().lower() in ("1", "true", "yes")
                            cb = ui.checkbox(fd.label, value=val)
                            if fd.help:
                                with cb:
                                    ui.tooltip(fd.help)
                            cb.on("update:model-value",
                                  lambda e, k=fd.key: edits.update({k: "true" if e.args else "false"}))
                        elif fd.kind == "int":
                            try:
                                cur_int = int(stored) if stored else 0
                            except ValueError:
                                cur_int = 0
                            n = ui.number(fd.label, value=cur_int, step=1).props("outlined dense").classes("w-full")
                            n.on("update:model-value",
                                 lambda e, k=fd.key: edits.update({k: str(int(e.args)) if e.args is not None else ""}))
                        elif fd.kind == "select":
                            opts = fd.options or [""]
                            sel = ui.select(opts, value=stored if stored in opts else opts[0], label=fd.label).props(
                                "outlined dense"
                            ).classes("w-full")
                            sel.on("update:model-value",
                                   lambda e, k=fd.key: edits.update({k: e.args or ""}))
                        elif fd.kind == "secret":
                            if reveal_secrets.value:
                                inp = ui.input(label=fd.label, value=stored,
                                               placeholder=fd.placeholder).props("outlined dense").classes("w-full")
                            else:
                                inp = ui.input(
                                    label=fd.label,
                                    value=settings_mod.mask_secret(stored),
                                    password=True,
                                    placeholder=fd.placeholder,
                                ).props("outlined dense").classes("w-full")
                            inp.on("update:model-value",
                                   lambda e, k=fd.key, prev=stored: (
                                       edits.update({k: e.args}) if e.args != settings_mod.mask_secret(prev) else None
                                   ))
                        else:
                            inp = ui.input(label=fd.label, value=stored,
                                           placeholder=fd.placeholder).props("outlined dense").classes("w-full")
                            inp.on("update:model-value",
                                   lambda e, k=fd.key: edits.update({k: e.args or ""}))
                        if fd.help and fd.kind != "bool":
                            ui.label(fd.help).classes("text-xs text-slate-500 dark:text-slate-400")

            ui.separator().classes("my-3")
            with ui.row().classes("gap-2 w-full items-center"):
                save_btn = ui.button("Save changes", icon="save").props("color=primary")
                test_btn = ui.button("Test connection", icon="cable").props("outline")
                ui.space()
                status = ui.label("").classes("text-xs text-slate-500 dark:text-slate-400")

                def do_save():
                    if not edits:
                        ui.notify("No changes to save", color="info")
                        return
                    try:
                        settings_mod.write_env(target, edits)
                        ui.notify(f"Saved {len(edits)} change(s)", color="positive")
                        edits.clear()
                        render_for_profile()  # re-render with fresh values
                    except Exception as exc:
                        ui.notify(f"Save failed: {exc}", color="negative")
                save_btn.on("click", do_save)

                def do_test():
                    try:
                        cfg = state_mod.get_cfg()
                        client = ADOClient(cfg.ado_org_url, cfg.ado_project,
                                           cfg.ado_pat, read_only=True)
                        ids = client.query_assigned(cfg.assigned_user_clause)
                        ui.notify(
                            f"OK — {len(ids)} item(s) assigned to {cfg.assigned_user_clause}",
                            color="positive",
                        )
                    except Exception as exc:
                        ui.notify(f"Connection failed: {exc}", color="negative")
                test_btn.on("click", do_test)

    profile_select.on("update:model-value", lambda _: render_for_profile())
    render_for_profile()


def _render_cron_editor():
    crons = settings_mod.read_crons()
    if not crons:
        theme.empty_state(
            "No crons.yml found",
            "Drop crons.yml.example into crons.yml at the repo root to get started.",
        )
        return

    edits = {c["name"]: dict(c) for c in crons}

    for c in crons:
        name = c["name"]
        with ui.card().classes(
            "p-3 w-full rounded-lg border border-slate-200 dark:border-slate-700 "
            "bg-white dark:bg-slate-800"
        ):
            with ui.row().classes("items-center w-full"):
                with ui.column().classes("flex-1 gap-0"):
                    ui.label(name).classes("font-bold text-sm text-slate-900 dark:text-slate-100")
                    ui.label(c.get("description", "")).classes(
                        "text-xs text-slate-500 dark:text-slate-400"
                    )
                ui.switch(
                    "Enabled", value=bool(c.get("enabled")),
                ).on("update:model-value",
                     lambda e, n=name: edits[n].update({"enabled": bool(e.args)}))

            with ui.row().classes("w-full gap-2 mt-2"):
                sched = ui.input(label="Schedule", value=c.get("schedule", "")).props(
                    "outlined dense"
                ).classes("w-48")
                cmd = ui.input(label="Command", value=c.get("command", "")).props(
                    "outlined dense"
                ).classes("flex-1")
                sched.on("update:model-value",
                         lambda e, n=name: edits[n].update({"schedule": e.args}))
                cmd.on("update:model-value",
                       lambda e, n=name: edits[n].update({"command": e.args}))

    ui.separator().classes("my-3")
    with ui.row().classes("gap-2"):
        save_btn = ui.button("Save crons.yml", icon="save").props("color=primary")
        ui.label(
            "After saving, run `vamos cron-install` from a terminal to apply."
        ).classes("text-xs text-slate-500 dark:text-slate-400 self-center")

    def do_save():
        merged = []
        for c in crons:
            merged.append({**c, **edits.get(c["name"], {})})
        settings_mod.write_crons(merged)
        ui.notify("crons.yml saved", color="positive")
    save_btn.on("click", do_save)
