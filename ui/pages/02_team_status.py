"""Team status — metrics, healthcheck, hygiene, trends, customers, at-risk."""
from __future__ import annotations

import json
import sys
from datetime import date, datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402
import streamlit.components.v1 as components  # noqa: E402

from vamos import healthcheck, hygiene, at_risk as at_risk_mod  # noqa: E402
from vamos.ado import ADOClient  # noqa: E402
from vamos.cleaner import apply_proposal  # noqa: E402
from vamos.core import delivery, state as state_mod  # noqa: E402
from vamos.core import customer as customer_mod, trends as trends_mod, people as people_mod  # noqa: E402
from vamos.core.snapshot import build_snapshot  # noqa: E402
from vamos.hygiene.cleaners import PROPOSERS as HYG_PROPOSERS  # noqa: E402


def _build_one_proposal(cfg, finding, proposer):
    """Helper used by run_with_streaming_logs to surface progress while building."""
    client = ADOClient(cfg.ado_org_url, cfg.ado_project, cfg.ado_pat, read_only=True)
    snap = build_snapshot(
        client,
        area_path=cfg.hygiene_area_path,
        iteration_path=cfg.hygiene_iteration_path,
        repos=cfg.hygiene_repos or None,
    )
    return proposer(finding, snap, cfg)
from vamos.metrics import (  # noqa: E402
    ADOTeamContext,
    ADOBoardMetricsCollector,
    ReportGenerator,
    ReportOptions,
)

from ui import style  # noqa: E402

st.set_page_config(page_title="Team status · vamos", page_icon=None, layout="wide")
style.apply()
style.theme_toggle_in_sidebar()

cfg = style.get_cfg(st.session_state.get("profile_arg"), board=st.session_state.get("board_arg"))
st.session_state["cfg"] = cfg

style.section_header(
    "Team status",
    subtitle="Metrics, healthcheck, hygiene, trends, customers, at-risk",
)

tab_health, tab_hyg, tab_metrics, tab_trends, tab_customers, tab_risk = st.tabs(
    ["Healthcheck", "Hygiene", "Metrics", "Trends", "Customers", "At-risk"]
)

# ============================================================================
# Healthcheck
# ============================================================================
with tab_health:
    col_actions, col_post = st.columns([1, 1])
    with col_actions:
        with st.container(border=True):
            st.markdown('<div style="font-weight:600; margin-bottom:0.5rem;">Generate report</div>',
                        unsafe_allow_html=True)
            if st.button("Run healthcheck now", key="run_health", type="primary",
                         use_container_width=True):
                try:
                    text = style.run_with_streaming_logs(
                        "Running healthcheck",
                        healthcheck.run, cfg, skip_post=True, day=date.today(),
                    )
                    st.session_state["last_healthcheck"] = text
                    st.toast("Healthcheck ready below")
                except Exception as exc:
                    st.error(f"Healthcheck failed: {exc}")
    with col_post:
        with st.container(border=True):
            st.markdown('<div style="font-weight:600; margin-bottom:0.5rem;">Deliver to channel</div>',
                        unsafe_allow_html=True)
            confirm = st.checkbox(f"I want to post to {cfg.connection_option}", key="confirm_health")
            if st.button("Post latest healthcheck", disabled=not confirm,
                         key="post_health", use_container_width=True):
                try:
                    healthcheck.run(cfg, skip_post=False, day=date.today())
                    st.toast(f"Posted to {cfg.connection_option}")
                except Exception as exc:
                    st.error(f"Post failed: {exc}")
    text = st.session_state.get("last_healthcheck")
    if text:
        with st.container(border=True):
            st.markdown(text)
    else:
        style.empty_state("No healthcheck yet", "Click Run healthcheck now to generate one.")

# ============================================================================
# Hygiene
# ============================================================================
with tab_hyg:
    col_actions, col_post = st.columns([1, 1])
    with col_actions:
        with st.container(border=True):
            st.markdown('<div style="font-weight:600; margin-bottom:0.5rem;">Run hygiene check</div>',
                        unsafe_allow_html=True)
            if st.button("Run hygiene now", key="run_hygiene", type="primary",
                         use_container_width=True):
                try:
                    report = style.run_with_streaming_logs(
                        "Running hygiene (snapshot + 7 rules across all repos)",
                        hygiene.run, cfg, skip_post=True, day=date.today(),
                    )
                    st.session_state["last_hygiene"] = report
                    st.toast(f"Done — {len(report.findings)} finding(s)")
                except Exception as exc:
                    st.error(f"Hygiene failed: {exc}")
    with col_post:
        with st.container(border=True):
            st.markdown('<div style="font-weight:600; margin-bottom:0.5rem;">Deliver to channel</div>',
                        unsafe_allow_html=True)
            confirm = st.checkbox(f"I want to post to {cfg.connection_option}", key="confirm_hyg")
            if st.button("Post latest hygiene", disabled=not confirm,
                         key="post_hyg", use_container_width=True):
                report = st.session_state.get("last_hygiene")
                if not report:
                    st.error("Run a hygiene check first.")
                else:
                    try:
                        delivery.post_report(cfg, report)
                        st.toast(f"Posted to {cfg.connection_option}")
                    except Exception as exc:
                        st.error(f"Post failed: {exc}")

    report = st.session_state.get("last_hygiene")
    cached = state_mod.read_daily(cfg.state_dir, "hygiene") if not report else None
    summary = None
    findings_data: list[dict] = []
    if report:
        summary = {s: len(fs) for s, fs in report.by_severity().items()}
        findings_data = [
            {"severity": f.severity, "engineer": f.engineer, "ticket_id": f.ticket_id,
             "ticket_url": f.ticket_url, "ticket_title": f.ticket_title, "message": f.message,
             "rule_id": f.rule_id}
            for f in report.findings
        ]
    elif cached:
        summary = cached.get("summary")
        findings_data = cached.get("findings", []) or []

    if summary:
        st.markdown("<div style='margin-top:1rem;'></div>", unsafe_allow_html=True)
        # Drill-down: clicking a KPI tile filters the list below
        if "hyg_filter_sev" not in st.session_state:
            st.session_state["hyg_filter_sev"] = None

        k1, k2, k3, k4 = st.columns(4)
        for col, sev_key, label, tone in [
            (k1, "blocker", "Blockers", "red"),
            (k2, "should-fix", "Should-fix", "amber"),
            (k3, "nit", "Nits", "indigo"),
            (k4, None, "Total", "slate"),
        ]:
            with col:
                n = sum(summary.values()) if sev_key is None else summary.get(sev_key, 0)
                actual_tone = tone if n else "slate"
                st.markdown(style.kpi(label, str(n), tone=actual_tone), unsafe_allow_html=True)
                if sev_key is not None:
                    if st.button(f"Filter to {label.lower()}", key=f"filter_{sev_key}",
                                 use_container_width=True):
                        st.session_state["hyg_filter_sev"] = sev_key
                else:
                    if st.button("Show all", key="filter_all", use_container_width=True):
                        st.session_state["hyg_filter_sev"] = None

        st.markdown("<div style='margin-top:1rem;'></div>", unsafe_allow_html=True)
        active_filter = st.session_state.get("hyg_filter_sev")
        if active_filter:
            st.markdown(f"_Filtered to:_ {style.pill(active_filter, {'blocker':'red','should-fix':'amber','nit':'indigo'}.get(active_filter,'slate'))}",
                        unsafe_allow_html=True)
            findings_view = [f for f in findings_data if f.get("severity") == active_filter]
        else:
            findings_view = findings_data

        # Build a lookup from (rule_id, ticket_id, message) → Finding for clean actions
        finding_lookup = {}
        if report:
            for ff in report.findings:
                finding_lookup[(ff.rule_id, ff.ticket_id, ff.engineer, ff.message)] = ff

        with st.container(border=True):
            by_eng: dict[str, list] = {}
            for f in findings_view:
                eng = f.get("engineer")
                disp = people_mod.display_name(eng) if eng else "Team-level"
                by_eng.setdefault(disp, []).append(f)
            for eng in sorted(by_eng):
                fs = by_eng[eng]
                sev_counts: dict[str, int] = {}
                for f in fs:
                    sev_counts[f["severity"]] = sev_counts.get(f["severity"], 0) + 1
                pills_html = " ".join(
                    style.pill(
                        f"{n} {s}",
                        {"blocker": "red", "should-fix": "amber", "nit": "indigo"}.get(s, "slate"),
                    )
                    for s, n in sev_counts.items()
                )
                st.markdown(f"##### {eng} {pills_html}", unsafe_allow_html=True)
                for fi, f in enumerate(fs):
                    sev = f.get("severity", "info")
                    tone = {"blocker": "red", "should-fix": "amber", "nit": "indigo"}.get(sev, "slate")
                    tid = f.get("ticket_id")
                    url = f.get("ticket_url")
                    ref = f"[#{tid}]({url})" if tid and url else (f"#{tid}" if tid else "")
                    rule_id = f.get("rule_id", "")
                    cleanable = bool(report) and rule_id in HYG_PROPOSERS

                    cmsg, cbtn = st.columns([8, 1])
                    with cmsg:
                        st.markdown(
                            f"- {style.pill(sev, tone)} {f.get('message','')} {ref}",
                            unsafe_allow_html=True,
                        )
                    with cbtn:
                        if cleanable:
                            slot = f"prop::{eng}::{rule_id}::{tid}::{fi}"
                            current = st.session_state.get(slot)
                            if current is None:
                                if st.button("Clean", key=f"btn_{slot}",
                                             help="Have Claude propose a fix"):
                                    finding_obj = finding_lookup.get(
                                        (rule_id, tid, f.get("engineer"), f.get("message"))
                                    )
                                    if finding_obj:
                                        st.session_state[slot] = ("building", finding_obj)
                                        st.rerun()

                    # Render proposal panel inline below the row
                    slot = f"prop::{eng}::{rule_id}::{tid}::{fi}"
                    cur = st.session_state.get(slot)
                    if isinstance(cur, tuple) and cur[0] == "building":
                        finding_obj = cur[1]
                        try:
                            proposer = HYG_PROPOSERS[rule_id]
                            proposal = style.run_with_streaming_logs(
                                f"Building proposal for #{tid}",
                                _build_one_proposal, cfg, finding_obj, proposer,
                            )
                            st.session_state[slot] = ("ready", proposal)
                            st.rerun()
                        except Exception as exc:
                            st.session_state[slot] = ("error", str(exc))
                            st.error(f"Proposal failed: {exc}")
                    elif isinstance(cur, tuple) and cur[0] == "ready":
                        proposal = cur[1]
                        if proposal is None or getattr(proposal, "is_empty", False):
                            with st.container(border=True):
                                st.caption("No safe auto-fix available for this finding "
                                           "(needs a human).")
                                if st.button("Dismiss", key=f"dismiss_{slot}"):
                                    del st.session_state[slot]
                                    st.rerun()
                        else:
                            with st.container(border=True):
                                tone_p = {"high": "green", "medium": "amber", "low": "red"}.get(
                                    proposal.confidence, "slate"
                                )
                                st.markdown(
                                    f"**Proposal** · confidence "
                                    f"{style.pill(proposal.confidence, tone_p)}",
                                    unsafe_allow_html=True,
                                )
                                st.caption(proposal.rationale)
                                for a in proposal.actions:
                                    st.markdown(f"- `{a.kind}`: {a.describe()}")
                                ap1, ap2, _ = st.columns([1, 1, 4])
                                with ap1:
                                    if st.button("Apply", type="primary",
                                                 key=f"apply_{slot}",
                                                 disabled=not cfg.hygiene_live_mode,
                                                 help=("Set HYGIENE_LIVE_MODE=true in "
                                                       "Settings to enable Apply.")
                                                       if not cfg.hygiene_live_mode else None):
                                        live_client = ADOClient(
                                            cfg.ado_org_url, cfg.ado_project, cfg.ado_pat,
                                            read_only=False,
                                        )
                                        result = apply_proposal(live_client, proposal)
                                        if result.applied:
                                            st.toast("Applied")
                                            st.session_state[slot] = ("applied", result)
                                        else:
                                            st.error(f"Apply failed: {result.error}")
                                        st.rerun()
                                with ap2:
                                    if st.button("Skip", key=f"skip_{slot}"):
                                        del st.session_state[slot]
                                        st.rerun()
                    elif isinstance(cur, tuple) and cur[0] == "applied":
                        st.success("Applied. Re-run hygiene to verify.")
                    elif isinstance(cur, tuple) and cur[0] == "error":
                        st.error(f"Proposal failed: {cur[1]}")
                        if st.button("Reset", key=f"reset_{slot}"):
                            del st.session_state[slot]
                            st.rerun()
                st.markdown("")
    else:
        style.empty_state("No hygiene report yet", "Click Run hygiene now above.")

# ============================================================================
# Metrics
# ============================================================================
with tab_metrics:
    metrics_yaml = ROOT / ".ado-metrics.yml"
    boards: list[dict] = []
    default_board_name = None
    if metrics_yaml.exists():
        try:
            mc = yaml.safe_load(metrics_yaml.read_text()) or {}
            boards = mc.get("boards", []) or []
            default_board_name = mc.get("default_board")
        except Exception as exc:
            st.warning(f"Could not parse .ado-metrics.yml: {exc}")

    col_form, col_post = st.columns([2, 1])
    with col_form:
        with st.container(border=True):
            st.markdown(
                '<div style="font-weight:600; margin-bottom:0.5rem;">Generate report</div>',
                unsafe_allow_html=True,
            )
            board_choices = ["(custom paths)"] + [b["name"] for b in boards]
            default_idx = 0
            if default_board_name:
                for i, b in enumerate(boards):
                    if b["name"] == default_board_name:
                        default_idx = i + 1
                        break
            board_choice = st.selectbox("Board", options=board_choices, index=default_idx)
            if board_choice == "(custom paths)":
                area_default = (
                    __import__("os").environ.get("METRICS_AREA_PATH")
                    or cfg.healthcheck_area_path or ""
                )
                iter_default = (
                    __import__("os").environ.get("METRICS_ITERATION_PATH")
                    or cfg.healthcheck_iteration_path or ""
                )
                area_path = st.text_input("Area path", value=area_default)
                iteration_path = st.text_input("Iteration path", value=iter_default)
            else:
                board = next(b for b in boards if b["name"] == board_choice)
                area_path = board["area_path"]
                iteration_path = board["iteration_path"]
                st.caption(f"Area: `{area_path}`  ·  Iteration: `{iteration_path}`")
            fmt = st.radio("Format", options=["html", "markdown", "json"], horizontal=True)
            include_charts = st.checkbox("Include charts (HTML only)", value=True)
            include_achievements = st.checkbox("Include developer achievements", value=True)
            run_btn = st.button("Generate metrics now", type="primary", use_container_width=True)
            if run_btn:
                if not area_path or not iteration_path:
                    st.error("Area path and iteration path are required.")
                else:
                    def _do_metrics():
                        ado_client = ADOClient(
                            cfg.ado_org_url, cfg.ado_project, cfg.ado_pat, read_only=True,
                        )
                        ctx = ADOTeamContext(
                            area_path=area_path,
                            iteration_path=iteration_path,
                            board=(board_choice if board_choice != "(custom paths)" else None),
                            project=cfg.ado_project,
                        )
                        collector = ADOBoardMetricsCollector(ado_client)
                        metrics_data = collector.collect_board_metrics(ctx, [])
                        ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
                        slug = (board_choice if board_choice != "(custom paths)" else "metrics").replace(" ", "_").lower()
                        out_dir = ROOT / "metrics_reports"
                        out_dir.mkdir(exist_ok=True)
                        out_path = out_dir / f"{ts}_{slug}.{fmt}"
                        generator = ReportGenerator()
                        options = ReportOptions(
                            area_path=area_path, iteration_path=iteration_path,
                            format=fmt, output_path=str(out_path),
                            dry_run=True, send_notifications=False,
                            include_charts=include_charts,
                            include_achievements=include_achievements,
                        )
                        result = generator.generate_report(metrics_data, options)
                        return result, metrics_data
                    try:
                        result, metrics_data = style.run_with_streaming_logs(
                            "Collecting metrics across the board", _do_metrics,
                        )
                        st.session_state["last_metrics_path"] = str(result.local_path)
                        st.session_state["last_metrics_format"] = fmt
                        st.session_state["last_metrics_summary"] = {
                            "total": metrics_data.total_work_items,
                            "completed": metrics_data.completed_work_items,
                            "in_progress": metrics_data.in_progress_work_items,
                            "blocked": metrics_data.blocked_work_items,
                            "developers": len(metrics_data.developers),
                        }
                        st.toast(f"Generated  ·  {Path(result.local_path).name}")
                    except Exception as exc:
                        st.error(f"Metrics failed: {exc}")

    with col_post:
        with st.container(border=True):
            st.markdown(
                '<div style="font-weight:600; margin-bottom:0.5rem;">Existing reports</div>',
                unsafe_allow_html=True,
            )
            reports_dir = ROOT / "metrics_reports"
            if reports_dir.exists():
                files = sorted(reports_dir.glob("*"), reverse=True)
                files = [f for f in files if f.is_file() and f.suffix in (".html", ".md", ".json")]
                if files:
                    pick = st.selectbox("Open a previous report",
                                        options=[f.name for f in files], key="prev_metrics_pick")
                    if pick:
                        st.session_state["last_metrics_path"] = str(reports_dir / pick)
                        ext = Path(pick).suffix.lstrip(".")
                        st.session_state["last_metrics_format"] = (
                            "html" if ext == "html" else
                            ("markdown" if ext == "md" else "json")
                        )
                else:
                    st.caption("No reports in metrics_reports/ yet.")
            else:
                st.caption("No metrics_reports/ dir yet.")

    last_path = st.session_state.get("last_metrics_path")
    last_fmt = st.session_state.get("last_metrics_format")
    summary = st.session_state.get("last_metrics_summary")
    if last_path:
        st.markdown("<div style='margin-top:1.5rem;'></div>", unsafe_allow_html=True)
        if summary:
            k1, k2, k3, k4, k5 = st.columns(5)
            k1.markdown(style.kpi("Items", str(summary["total"])), unsafe_allow_html=True)
            k2.markdown(style.kpi("Completed", str(summary["completed"]), tone="green"),
                        unsafe_allow_html=True)
            k3.markdown(style.kpi("In progress", str(summary["in_progress"]), tone="indigo"),
                        unsafe_allow_html=True)
            k4.markdown(style.kpi("Blocked", str(summary["blocked"]),
                                  tone="red" if summary["blocked"] else "slate"),
                        unsafe_allow_html=True)
            k5.markdown(style.kpi("Developers", str(summary["developers"])),
                        unsafe_allow_html=True)
            st.markdown("<div style='margin-top:1rem;'></div>", unsafe_allow_html=True)
        report_path = Path(last_path)
        st.caption(f"Report: `{report_path}`")
        try:
            content = report_path.read_text(encoding="utf-8")
        except OSError as exc:
            st.error(f"Could not read report: {exc}")
            content = ""
        if last_fmt == "html" and content:
            with st.container(border=True):
                components.html(content, height=900, scrolling=True)
        elif last_fmt == "markdown" and content:
            with st.container(border=True):
                st.markdown(content)
        elif last_fmt == "json" and content:
            st.code(content, language="json")
        with st.expander("Download report"):
            st.download_button(
                "Download", data=content, file_name=report_path.name,
                mime={"html": "text/html", "markdown": "text/markdown",
                      "json": "application/json"}.get(last_fmt, "text/plain"),
            )
    else:
        style.empty_state("No metrics report yet",
                          "Pick a board, choose a format, and click Generate.")

# ============================================================================
# Trends
# ============================================================================
with tab_trends:
    series = trends_mod.hygiene_series(cfg.state_dir, days=30)
    has_data = any(series[k] for k in series)
    if not has_data:
        style.empty_state(
            "No trend history yet",
            "Run hygiene a few times — once per day — and trends will appear here. "
            "Each daily snapshot in state/hygiene/ feeds this view.",
        )
    else:
        # Top KPI row: latest + WoW change for each severity
        st.markdown("<div style='margin-bottom:1rem;'></div>", unsafe_allow_html=True)
        cols = st.columns(4)
        for col, key, label, tone in [
            (cols[0], "blocker", "Blockers", "red"),
            (cols[1], "should-fix", "Should-fix", "amber"),
            (cols[2], "nit", "Nits", "indigo"),
            (cols[3], "total", "Total findings", "slate"),
        ]:
            data = series[key]
            d = trends_mod.delta(data)
            with col:
                if d["latest"] is None:
                    st.markdown(style.kpi(label, "—"), unsafe_allow_html=True)
                    continue
                wow = d.get("wow")
                wow_str = f"{wow:+d}" if wow is not None else "—"
                spark = trends_mod.sparkline_unicode([v for _, v in data])
                st.markdown(
                    f'<div style="background:var(--bg-surface); border:1px solid var(--border); '
                    f'border-radius:12px; padding:1rem 1.25rem; box-shadow:var(--shadow-sm);">'
                    f'<div style="color:var(--text-muted); font-size:0.75rem; font-weight:600; '
                    f'text-transform:uppercase; letter-spacing:0.05em;">{label}</div>'
                    f'<div style="display:flex; justify-content:space-between; align-items:baseline;">'
                    f'<div style="font-size:1.875rem; font-weight:700; line-height:1.1;">{d["latest"]}</div>'
                    f'<div style="font-size:0.875rem; color:var(--text-muted);">WoW {wow_str}</div></div>'
                    f'<div style="font-family:JetBrains Mono,monospace; font-size:0.75rem; '
                    f'color:var(--text-muted); margin-top:0.5rem;">{spark}</div></div>',
                    unsafe_allow_html=True,
                )
        st.markdown("<div style='margin-top:1.5rem;'></div>", unsafe_allow_html=True)

        # Per-engineer trend (last 14 days)
        per_eng = trends_mod.hygiene_per_engineer(cfg.state_dir, days=14)
        if per_eng:
            st.markdown("##### Per-engineer hygiene findings (last 14 days)")
            with st.container(border=True):
                for canon, points in sorted(per_eng.items()):
                    name = people_mod.display_name(canon)
                    values = [v for _, v in points]
                    spark = trends_mod.sparkline_unicode(values, width=18)
                    total = sum(values)
                    days_clean = sum(1 for v in values if v == 0)
                    st.markdown(
                        f'<div style="display:flex; justify-content:space-between; '
                        f'padding:0.4rem 0; border-bottom:1px solid var(--border);">'
                        f'<div style="font-weight:500;">{name}</div>'
                        f'<div style="font-family:JetBrains Mono,monospace; '
                        f'color:var(--text-muted);">'
                        f'{spark}  ·  {total} total  ·  {days_clean} clean day(s)</div></div>',
                        unsafe_allow_html=True,
                    )

# ============================================================================
# Customers
# ============================================================================
with tab_customers:
    if st.button("Refresh customer breakdown", type="primary"):
        def _build_cust_snap():
            client = ADOClient(cfg.ado_org_url, cfg.ado_project, cfg.ado_pat, read_only=True)
            return build_snapshot(
                client,
                area_path=cfg.hygiene_area_path,
                iteration_path=cfg.hygiene_iteration_path,
                repos=[],
            )
        try:
            snap = style.run_with_streaming_logs(
                "Building team snapshot for customer breakdown", _build_cust_snap,
            )
            st.session_state["customer_snap"] = snap
            st.toast(f"{len(snap.work_items)} item(s) loaded")
        except Exception as exc:
            st.error(f"Failed: {exc}")

    snap = st.session_state.get("customer_snap")
    if not snap:
        style.empty_state(
            "No customer data yet",
            "Click Refresh customer breakdown to scan ADO. "
            "vamos extracts customer prefixes from ticket titles "
            "(Vituity, UHC, MEMS, …) using a heuristic.",
        )
    else:
        grouped = customer_mod.group_by_customer(snap.work_items, title_attr="title")
        # Top KPI: number of customers
        n_customers = len([k for k in grouped if k != "(no customer)"])
        n_unmatched = len(grouped.get("(no customer)", []))
        c1, c2, c3 = st.columns(3)
        c1.markdown(style.kpi("Customers", str(n_customers), tone="indigo"),
                    unsafe_allow_html=True)
        c2.markdown(style.kpi("Items overall", str(len(snap.work_items))),
                    unsafe_allow_html=True)
        c3.markdown(style.kpi("Unmatched", str(n_unmatched),
                              tone="amber" if n_unmatched else "slate"),
                    unsafe_allow_html=True)
        st.markdown("<div style='margin-top:1rem;'></div>", unsafe_allow_html=True)

        # Per-customer card
        sorted_customers = sorted(grouped.items(), key=lambda kv: -len(kv[1]))
        for cust, items in sorted_customers:
            if cust == "(no customer)":
                continue
            blocked_n = sum(1 for w in items if w.state in ("Blocked", "Waiting"))
            active_n = sum(1 for w in items if w.state in ("Active", "Doing", "In Progress"))
            with st.container(border=True):
                st.markdown(
                    f'<div style="display:flex; justify-content:space-between; align-items:baseline;">'
                    f'<div style="font-weight:700; font-size:1rem;">{cust}</div>'
                    f'<div>{style.pill(f"{len(items)} items", "indigo")}  '
                    f'{style.pill(f"{active_n} active", "slate")}  '
                    f'{style.pill(f"{blocked_n} blocked", "red" if blocked_n else "slate")}</div></div>',
                    unsafe_allow_html=True,
                )
                with st.expander(f"Show {cust} tickets"):
                    for w in items[:50]:
                        st.markdown(
                            f"- [{w.state}] [#{w.id}]({w.url}) {w.title}  ·  "
                            f"_{w.assigned_to or 'unassigned'}_"
                        )
                    if len(items) > 50:
                        st.caption(f"...and {len(items) - 50} more.")

# ============================================================================
# At-risk
# ============================================================================
with tab_risk:
    col_actions, col_post = st.columns([1, 1])
    with col_actions:
        with st.container(border=True):
            st.markdown('<div style="font-weight:600; margin-bottom:0.5rem;">Run at-risk scan</div>',
                        unsafe_allow_html=True)
            if st.button("Run at-risk now", type="primary", key="run_atrisk",
                         use_container_width=True):
                try:
                    report = style.run_with_streaming_logs(
                        "Scanning at-risk (past-target, blocked P1s, aging items, aging PRs)",
                        at_risk_mod.run, cfg, skip_post=True, day=date.today(),
                    )
                    st.session_state["last_atrisk"] = report
                    st.toast(f"{len(report.findings)} risk(s) found")
                except Exception as exc:
                    st.error(f"At-risk failed: {exc}")
    with col_post:
        with st.container(border=True):
            st.markdown('<div style="font-weight:600; margin-bottom:0.5rem;">Deliver to channel</div>',
                        unsafe_allow_html=True)
            confirm = st.checkbox(f"I want to post to {cfg.connection_option}", key="confirm_atrisk")
            if st.button("Post latest at-risk", disabled=not confirm,
                         key="post_atrisk", use_container_width=True):
                report = st.session_state.get("last_atrisk")
                if not report:
                    st.error("Run at-risk first.")
                else:
                    try:
                        delivery.post_report(cfg, report)
                        st.toast(f"Posted to {cfg.connection_option}")
                    except Exception as exc:
                        st.error(f"Post failed: {exc}")

    report = st.session_state.get("last_atrisk")
    cached = state_mod.read_daily(cfg.state_dir, "at-risk") if not report else None
    if report:
        st.markdown("<div style='margin-top:1rem;'></div>", unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown(report.to_markdown())
    elif cached:
        st.caption(f"Cached at-risk report from {cached.get('generated_at','?')}")
        with st.container(border=True):
            for f in cached.get("findings", []):
                sev = f.get("severity", "info")
                tone = {"blocker": "red", "should-fix": "amber"}.get(sev, "slate")
                tid = f.get("ticket_id")
                url = f.get("ticket_url")
                ref = f"[#{tid}]({url})" if tid and url else ""
                st.markdown(
                    f"- {style.pill(sev, tone)} {f.get('message','')}  "
                    f"{ref}  ·  _{f.get('engineer') or 'team'}_",
                    unsafe_allow_html=True,
                )
    else:
        style.empty_state("No at-risk report yet",
                          "Click Run at-risk now to scan.")
