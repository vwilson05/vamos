"""Team status — healthcheck, hygiene (with Clean buttons), metrics, trends, customers, at-risk."""
from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

import yaml
from nicegui import ui

from vamos import healthcheck, hygiene, at_risk as at_risk_mod
from vamos.ado import ADOClient
from vamos.cleaner import apply_proposal
from vamos.core import delivery, state as state_mod_vamos
from vamos.core import customer as customer_mod, trends as trends_mod, people as people_mod
from vamos.core.snapshot import build_snapshot
from vamos.hygiene.cleaners import PROPOSERS as HYG_PROPOSERS
from vamos.metrics import (
    ADOTeamContext, ADOBoardMetricsCollector, ReportGenerator, ReportOptions,
)

from .. import state as state_mod, theme
from ..streaming import run_with_logs

ROOT = Path(__file__).resolve().parent.parent.parent


@ui.page("/team-status")
def team_status_page():
    theme.render_shell(active_route="/team-status")
    cfg = state_mod.get_cfg()

    with ui.column().classes("p-6 max-w-7xl mx-auto w-full gap-4"):
        theme.section_header(
            "Team status",
            subtitle="Metrics, healthcheck, hygiene, trends, customers, at-risk",
        )

        with ui.tabs().classes("w-full") as tabs:
            tab_health = ui.tab("Healthcheck")
            tab_hyg = ui.tab("Hygiene")
            tab_metrics = ui.tab("Metrics")
            tab_trends = ui.tab("Trends")
            tab_customers = ui.tab("Customers")
            tab_risk = ui.tab("At-risk")

        with ui.tab_panels(tabs, value=tab_hyg).classes("w-full"):
            with ui.tab_panel(tab_health):
                _render_healthcheck(cfg)
            with ui.tab_panel(tab_hyg):
                _render_hygiene(cfg)
            with ui.tab_panel(tab_metrics):
                _render_metrics(cfg)
            with ui.tab_panel(tab_trends):
                _render_trends(cfg)
            with ui.tab_panel(tab_customers):
                _render_customers(cfg)
            with ui.tab_panel(tab_risk):
                _render_at_risk(cfg)


# =================================================================
# Healthcheck
# =================================================================


def _render_healthcheck(cfg):
    output = ui.column().classes("w-full mt-4")

    with ui.row().classes("w-full items-end gap-3"):
        run_btn = ui.button("Run healthcheck now", icon="favorite").props("color=primary")
        confirm_post = ui.checkbox(f"Post to {cfg.connection_option}", value=False).classes("ml-3")
        post_btn = ui.button("Post", icon="send").props("outline")

    last: dict = {}

    async def do_run():
        try:
            text = await run_with_logs(
                "Running healthcheck",
                healthcheck.run, cfg, skip_post=True, day=date.today(),
            )
            last["text"] = text
            output.clear()
            with output:
                with ui.card().classes(
                    "p-4 w-full rounded-xl border border-slate-200 dark:border-slate-700 "
                    "bg-white dark:bg-slate-800"
                ):
                    ui.markdown(text).classes("prose dark:prose-invert max-w-none")
        except Exception as exc:
            ui.notify(f"Healthcheck failed: {exc}", color="negative")
    run_btn.on("click", do_run)

    async def do_post():
        if not confirm_post.value:
            ui.notify("Tick the confirm box first.", color="warning")
            return
        try:
            await run_with_logs(
                f"Posting healthcheck to {cfg.connection_option}",
                healthcheck.run, cfg, skip_post=False, day=date.today(),
            )
            ui.notify(f"Posted to {cfg.connection_option}", color="positive")
        except Exception as exc:
            ui.notify(f"Post failed: {exc}", color="negative")
    post_btn.on("click", do_post)


# =================================================================
# Hygiene with inline Clean buttons
# =================================================================


def _render_hygiene(cfg):
    findings_container = ui.column().classes("w-full mt-4")

    with ui.row().classes("w-full items-end gap-3"):
        run_btn = ui.button("Run hygiene now", icon="cleaning_services").props("color=primary")
        confirm_post = ui.checkbox(f"Post to {cfg.connection_option}", value=False).classes("ml-3")
        post_btn = ui.button("Post", icon="send").props("outline")

    last_report: dict = {}

    async def do_run():
        try:
            report = await run_with_logs(
                "Running hygiene (snapshot + 7 rules across all repos)",
                hygiene.run, cfg, skip_post=True, day=date.today(),
            )
            last_report["report"] = report
            findings_container.clear()
            _render_hygiene_findings(findings_container, report, cfg)
        except Exception as exc:
            ui.notify(f"Hygiene failed: {exc}", color="negative")
    run_btn.on("click", do_run)

    async def do_post():
        if not confirm_post.value:
            ui.notify("Tick the confirm box first.", color="warning")
            return
        report = last_report.get("report")
        if not report:
            ui.notify("Run hygiene first.", color="warning")
            return
        try:
            delivery.post_report(cfg, report)
            ui.notify(f"Posted to {cfg.connection_option}", color="positive")
        except Exception as exc:
            ui.notify(f"Post failed: {exc}", color="negative")
    post_btn.on("click", do_post)

    # Show cached report on page load (no API hit)
    cached = state_mod_vamos.read_daily(cfg.state_dir, "hygiene")
    if cached:
        with findings_container:
            ui.label(f"Cached report from {cached.get('generated_at', '?')}").classes(
                "text-xs text-slate-500 dark:text-slate-400"
            )
            _render_hygiene_summary_cached(cached)


def _render_hygiene_summary_cached(cached: dict):
    summary = cached.get("summary", {})
    with ui.row().classes("w-full gap-3 flex-wrap"):
        for key, label, tone in [
            ("blocker", "Blockers", "red"),
            ("should-fix", "Should-fix", "amber"),
            ("nit", "Nits", "indigo"),
        ]:
            n = summary.get(key, 0)
            with ui.column().classes("flex-1 min-w-32"):
                theme.kpi(label, str(n), tone=tone if n else "slate")


def _render_hygiene_findings(parent, report, cfg):
    """Render findings grouped by engineer, with a Clean button per cleanable finding."""
    summary = {s: len(fs) for s, fs in report.by_severity().items()}
    SEV_TONES = {"blocker": "red", "should-fix": "amber", "nit": "indigo"}

    with parent:
        with ui.row().classes("w-full gap-3 flex-wrap"):
            for key, label, tone in [
                ("blocker", "Blockers", "red"),
                ("should-fix", "Should-fix", "amber"),
                ("nit", "Nits", "indigo"),
            ]:
                n = summary.get(key, 0)
                with ui.column().classes("flex-1 min-w-32"):
                    theme.kpi(label, str(n), tone=tone if n else "slate")

        by_eng: dict[str, list] = {}
        for f in report.findings:
            disp = people_mod.display_name(f.engineer) if f.engineer else "Team-level"
            by_eng.setdefault(disp, []).append(f)

        for eng in sorted(by_eng):
            fs = by_eng[eng]
            with ui.expansion(f"{eng} ({len(fs)})", icon="person").classes(
                "w-full bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg my-1"
            ):
                for finding in fs:
                    _render_one_finding(finding, cfg)


def _render_one_finding(finding, cfg):
    """One finding row with severity pill + message + Clean button (if cleanable)."""
    SEV_TONES = {"blocker": "red", "should-fix": "amber", "nit": "indigo"}
    cleanable = finding.rule_id in HYG_PROPOSERS

    with ui.row().classes("w-full items-start gap-3 py-2 border-b border-slate-100 dark:border-slate-700 last:border-b-0"):
        theme.pill(finding.severity, SEV_TONES.get(finding.severity, "slate"))
        with ui.column().classes("flex-1 gap-1 min-w-0"):
            ui.label(finding.message).classes("text-sm text-slate-900 dark:text-slate-100")
            if finding.ticket_id and finding.ticket_url:
                ui.link(f"#{finding.ticket_id}", finding.ticket_url, new_tab=True).classes(
                    "text-xs text-indigo-600 dark:text-indigo-400"
                )
        if cleanable:
            clean_btn = ui.button("Clean", icon="auto_fix_high").props("dense outline")
            clean_btn.on("click", lambda f=finding: _kick_clean(f, cfg))


def _kick_clean(finding, cfg):
    """Open a dialog with the proposal, allowing Apply / Skip."""
    with ui.dialog() as dialog, ui.card().classes(
        "min-w-[480px] max-w-2xl bg-white dark:bg-slate-800"
    ):
        ui.label(f"Clean: {finding.rule_id}").classes(
            "text-lg font-bold text-slate-900 dark:text-slate-50"
        )
        ui.label(finding.message).classes("text-sm text-slate-600 dark:text-slate-400")

        body = ui.column().classes("w-full gap-2 mt-3")

        async def build_and_show():
            body.clear()
            with body:
                spinner = ui.spinner(size="lg").classes("self-center")
            try:
                proposer = HYG_PROPOSERS[finding.rule_id]
                proposal = await _propose_async(cfg, finding, proposer)
            except Exception as exc:
                body.clear()
                with body:
                    ui.label(f"Proposal failed: {exc}").classes("text-rose-600")
                return

            body.clear()
            if not proposal or proposal.is_empty:
                with body:
                    ui.label("No safe auto-fix available — needs a human.").classes(
                        "text-sm text-slate-500"
                    )
                    ui.button("Close", on_click=dialog.close).props("flat")
                return

            CONFIDENCE_TONES = {"high": "green", "medium": "amber", "low": "red"}
            with body:
                with ui.row().classes("items-center gap-2"):
                    ui.label("Confidence").classes("text-xs uppercase tracking-wider text-slate-500")
                    theme.pill(proposal.confidence,
                               CONFIDENCE_TONES.get(proposal.confidence, "slate"))
                ui.label(proposal.rationale).classes(
                    "text-sm text-slate-700 dark:text-slate-300"
                )
                ui.label("Will apply:").classes("text-xs uppercase tracking-wider text-slate-500 mt-2")
                for a in proposal.actions:
                    ui.label(f"• {a.describe()}").classes(
                        "text-xs font-mono text-slate-600 dark:text-slate-400"
                    )

                with ui.row().classes("w-full justify-end gap-2 mt-3"):
                    ui.button("Skip", on_click=dialog.close).props("flat")
                    apply_btn = ui.button("Apply", icon="check").props("color=primary")
                    if not cfg.hygiene_live_mode:
                        apply_btn.disable()
                        ui.label("HYGIENE_LIVE_MODE=false — enable in Settings to apply.").classes(
                            "text-xs text-amber-700 dark:text-amber-400"
                        )

                    def do_apply():
                        live_client = ADOClient(
                            cfg.ado_org_url, cfg.ado_project, cfg.ado_pat, read_only=False,
                        )
                        result = apply_proposal(live_client, proposal)
                        if result.applied:
                            ui.notify("Applied", color="positive")
                            dialog.close()
                        else:
                            ui.notify(f"Failed: {result.error}", color="negative")
                    apply_btn.on("click", do_apply)

        dialog.open()
        ui.timer(0.05, build_and_show, once=True)


async def _propose_async(cfg, finding, proposer):
    import asyncio
    def go():
        client = ADOClient(cfg.ado_org_url, cfg.ado_project, cfg.ado_pat, read_only=True)
        snap = build_snapshot(
            client,
            area_path=cfg.hygiene_area_path,
            iteration_path=cfg.hygiene_iteration_path,
            repos=cfg.hygiene_repos or None,
        )
        return proposer(finding, snap, cfg)
    return await asyncio.to_thread(go)


# =================================================================
# Metrics
# =================================================================


def _render_metrics(cfg):
    metrics_yaml = ROOT / ".ado-metrics.yml"
    boards: list[dict] = []
    default_board_name = None
    if metrics_yaml.exists():
        try:
            mc = yaml.safe_load(metrics_yaml.read_text()) or {}
            boards = mc.get("boards", []) or []
            default_board_name = mc.get("default_board")
        except Exception:
            pass

    output = ui.column().classes("w-full mt-4")

    with ui.row().classes("w-full items-end gap-3 flex-wrap"):
        board_options = {"(custom paths)": "(custom paths)"}
        for b in boards:
            board_options[b["name"]] = b["name"]
        default_value = default_board_name if default_board_name in board_options else "(custom paths)"
        board_select = ui.select(
            board_options, value=default_value, label="Board",
        ).props("outlined dense").classes("w-64")
        format_select = ui.select(
            ["html", "markdown", "json"], value="html", label="Format",
        ).props("outlined dense").classes("w-32")
        gen_btn = ui.button("Generate", icon="auto_awesome").props("color=primary")

    async def do_generate():
        chosen = board_select.value
        if chosen == "(custom paths)":
            area = cfg.healthcheck_area_path or ""
            iteration = cfg.healthcheck_iteration_path or ""
        else:
            board = next(b for b in boards if b["name"] == chosen)
            area = board["area_path"]
            iteration = board["iteration_path"]

        if not area or not iteration:
            ui.notify("Area + iteration paths required.", color="warning")
            return

        async def go():
            ado_client = ADOClient(
                cfg.ado_org_url, cfg.ado_project, cfg.ado_pat, read_only=True,
            )
            ctx = ADOTeamContext(
                area_path=area, iteration_path=iteration,
                board=(chosen if chosen != "(custom paths)" else None),
                project=cfg.ado_project,
            )
            collector = ADOBoardMetricsCollector(ado_client)
            metrics_data = collector.collect_board_metrics(ctx, [])
            ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
            slug = (chosen if chosen != "(custom paths)" else "metrics").replace(" ", "_").lower()
            out_dir = ROOT / "metrics_reports"
            out_dir.mkdir(exist_ok=True)
            out_path = out_dir / f"{ts}_{slug}.{format_select.value}"
            generator = ReportGenerator()
            options = ReportOptions(
                area_path=area, iteration_path=iteration,
                format=format_select.value, output_path=str(out_path),
                dry_run=True, send_notifications=False,
                include_charts=True, include_achievements=True,
            )
            return generator.generate_report(metrics_data, options), metrics_data

        try:
            (result, metrics_data) = await run_with_logs(
                "Collecting metrics", lambda: None,  # placeholder
            ) if False else await __import__("asyncio").to_thread(go)
            # ^ direct to_thread; run_with_logs wrapper above is for reference only
            output.clear()
            with output:
                with ui.row().classes("w-full gap-3 flex-wrap"):
                    for label, value, tone in [
                        ("Items", str(metrics_data.total_work_items), "slate"),
                        ("Completed", str(metrics_data.completed_work_items), "green"),
                        ("In progress", str(metrics_data.in_progress_work_items), "indigo"),
                        ("Blocked", str(metrics_data.blocked_work_items),
                         "red" if metrics_data.blocked_work_items else "slate"),
                        ("Developers", str(len(metrics_data.developers)), "slate"),
                    ]:
                        with ui.column().classes("flex-1 min-w-32"):
                            theme.kpi(label, value, tone=tone)
                ui.label(f"Saved to: {result.local_path}").classes(
                    "text-xs text-slate-500 dark:text-slate-400"
                )
                content = Path(result.local_path).read_text(encoding="utf-8")
                if format_select.value == "markdown":
                    with ui.card().classes("w-full p-4"):
                        ui.markdown(content).classes("prose dark:prose-invert max-w-none")
                elif format_select.value == "json":
                    ui.code(content, language="json").classes("max-h-96 overflow-auto")
                else:  # html
                    # NiceGUI doesn't sandbox HTML by default; use html.add to inject
                    ui.html(content).classes("w-full")
        except Exception as exc:
            ui.notify(f"Metrics failed: {exc}", color="negative")
    gen_btn.on("click", do_generate)


# =================================================================
# Trends
# =================================================================


def _render_trends(cfg):
    series = trends_mod.hygiene_series(cfg.state_dir, days=30)
    has_data = any(series[k] for k in series)
    if not has_data:
        theme.empty_state(
            "No trend history yet",
            "Run hygiene a few times — once per day — and trends will appear here.",
        )
        return

    with ui.row().classes("w-full gap-3 flex-wrap"):
        for key, label, tone in [
            ("blocker", "Blockers", "red"),
            ("should-fix", "Should-fix", "amber"),
            ("nit", "Nits", "indigo"),
            ("total", "Total findings", "slate"),
        ]:
            data = series[key]
            d = trends_mod.delta(data)
            with ui.column().classes("flex-1 min-w-48"):
                with ui.card().classes(
                    "p-4 rounded-xl border border-slate-200 dark:border-slate-700 "
                    "bg-white dark:bg-slate-800 w-full"
                ):
                    ui.label(label).classes(
                        "text-xs uppercase tracking-wider text-slate-500 dark:text-slate-400"
                    )
                    if d["latest"] is None:
                        ui.label("—").classes("text-3xl font-bold")
                        continue
                    with ui.row().classes("items-baseline justify-between w-full"):
                        ui.label(str(d["latest"])).classes(
                            f"text-3xl font-bold {theme.KPI_TONE_CLASSES.get(tone, theme.KPI_TONE_CLASSES['slate'])}"
                        )
                        wow = d.get("wow")
                        wow_str = f"WoW {wow:+d}" if wow is not None else "—"
                        ui.label(wow_str).classes("text-sm text-slate-500 dark:text-slate-400")
                    spark = trends_mod.sparkline_unicode([v for _, v in data])
                    ui.label(spark).classes(
                        "font-mono text-xs text-slate-500 dark:text-slate-400 mt-2"
                    )

    per_eng = trends_mod.hygiene_per_engineer(cfg.state_dir, days=14)
    if per_eng:
        ui.label("Per-engineer hygiene findings (last 14 days)").classes(
            "font-bold text-base text-slate-900 dark:text-slate-50 mt-4"
        )
        with ui.card().classes(
            "w-full p-4 rounded-xl border border-slate-200 dark:border-slate-700 "
            "bg-white dark:bg-slate-800"
        ):
            for canon, points in sorted(per_eng.items()):
                name = people_mod.display_name(canon)
                values = [v for _, v in points]
                spark = trends_mod.sparkline_unicode(values, width=18)
                total = sum(values)
                clean = sum(1 for v in values if v == 0)
                with ui.row().classes(
                    "py-2 w-full items-center justify-between border-b border-slate-100 dark:border-slate-700 last:border-b-0"
                ):
                    ui.label(name).classes("text-sm font-medium text-slate-900 dark:text-slate-100")
                    ui.label(f"{spark}  ·  {total} total  ·  {clean} clean day(s)").classes(
                        "font-mono text-xs text-slate-500 dark:text-slate-400"
                    )


# =================================================================
# Customers
# =================================================================


def _render_customers(cfg):
    output = ui.column().classes("w-full mt-4")
    last_snap = {}

    refresh_btn = ui.button("Refresh customer breakdown", icon="refresh").props("color=primary")

    async def do_refresh():
        try:
            def go():
                client = ADOClient(cfg.ado_org_url, cfg.ado_project, cfg.ado_pat, read_only=True)
                return build_snapshot(
                    client,
                    area_path=cfg.hygiene_area_path,
                    iteration_path=cfg.hygiene_iteration_path,
                    repos=[],
                )
            snap = await run_with_logs("Building team snapshot for customer breakdown", go)
            last_snap["snap"] = snap
            output.clear()
            with output:
                _render_customer_panels(snap)
        except Exception as exc:
            ui.notify(f"Failed: {exc}", color="negative")
    refresh_btn.on("click", do_refresh)


def _render_customer_panels(snap):
    grouped = customer_mod.group_by_customer(snap.work_items, title_attr="title")
    n_customers = len([k for k in grouped if k != "(no customer)"])
    n_unmatched = len(grouped.get("(no customer)", []))

    with ui.row().classes("w-full gap-3 flex-wrap"):
        with ui.column().classes("flex-1 min-w-32"):
            theme.kpi("Customers", str(n_customers), tone="indigo")
        with ui.column().classes("flex-1 min-w-32"):
            theme.kpi("Items overall", str(len(snap.work_items)))
        with ui.column().classes("flex-1 min-w-32"):
            theme.kpi("Unmatched", str(n_unmatched), tone="amber" if n_unmatched else "slate")

    sorted_customers = sorted(grouped.items(), key=lambda kv: -len(kv[1]))
    for cust, items in sorted_customers:
        if cust == "(no customer)":
            continue
        blocked_n = sum(1 for w in items if w.state in ("Blocked", "Waiting"))
        active_n = sum(1 for w in items if w.state in ("Active", "Doing", "In Progress"))
        with ui.expansion(cust, icon="business").classes(
            "w-full bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg my-1"
        ):
            with ui.row().classes("gap-2"):
                theme.pill(f"{len(items)} items", "indigo")
                theme.pill(f"{active_n} active", "slate")
                theme.pill(f"{blocked_n} blocked", "red" if blocked_n else "slate")
            for w in items[:50]:
                with ui.row().classes("py-1 w-full items-center"):
                    ui.label(f"[{w.state}]").classes(
                        "text-xs font-mono text-slate-500 dark:text-slate-400 w-32"
                    )
                    ui.link(f"#{w.id}", w.url, new_tab=True).classes(
                        "text-xs text-indigo-600 dark:text-indigo-400 w-16"
                    )
                    ui.label(w.title).classes(
                        "text-sm text-slate-700 dark:text-slate-300 flex-1"
                    )
                    ui.label(w.assigned_to or "unassigned").classes(
                        "text-xs text-slate-500 dark:text-slate-400 w-48"
                    )
            if len(items) > 50:
                ui.label(f"...and {len(items) - 50} more.").classes(
                    "text-xs text-slate-500 dark:text-slate-400"
                )


# =================================================================
# At-risk
# =================================================================


def _render_at_risk(cfg):
    output = ui.column().classes("w-full mt-4")

    with ui.row().classes("w-full items-end gap-3"):
        run_btn = ui.button("Run at-risk now", icon="warning").props("color=primary")
        confirm = ui.checkbox(f"Post to {cfg.connection_option}", value=False)
        post_btn = ui.button("Post", icon="send").props("outline")

    last_report: dict = {}

    async def do_run():
        try:
            report = await run_with_logs(
                "Scanning at-risk",
                at_risk_mod.run, cfg, skip_post=True, day=date.today(),
            )
            last_report["report"] = report
            output.clear()
            with output:
                with ui.card().classes(
                    "p-4 w-full rounded-xl border border-slate-200 dark:border-slate-700 "
                    "bg-white dark:bg-slate-800"
                ):
                    ui.markdown(report.to_markdown()).classes(
                        "prose dark:prose-invert max-w-none"
                    )
        except Exception as exc:
            ui.notify(f"At-risk failed: {exc}", color="negative")
    run_btn.on("click", do_run)

    async def do_post():
        if not confirm.value:
            ui.notify("Tick the confirm box first.", color="warning")
            return
        report = last_report.get("report")
        if not report:
            ui.notify("Run at-risk first.", color="warning")
            return
        try:
            delivery.post_report(cfg, report)
            ui.notify(f"Posted to {cfg.connection_option}", color="positive")
        except Exception as exc:
            ui.notify(f"Post failed: {exc}", color="negative")
    post_btn.on("click", do_post)
