"""My day — personal daily flow with editable markdown + EOD copy."""
from __future__ import annotations

import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

from vamos import sod, sync, eod, standup as standup_mod, capture as capture_mod  # noqa: E402
from vamos import inbox as inbox_mod  # noqa: E402
from vamos import prep as prep_mod  # noqa: E402
from vamos.markdown_io import daily_path  # noqa: E402

from ui import style  # noqa: E402

st.set_page_config(page_title="My day · vamos", page_icon=None, layout="wide")
style.apply()
style.theme_toggle_in_sidebar()

cfg = style.get_cfg(st.session_state.get("profile_arg"), board=st.session_state.get("board_arg"))
st.session_state["cfg"] = cfg

today = date.today()
md_path = daily_path(cfg.work_dir, today)

style.section_header(
    f"{today.strftime('%A, %B %d, %Y')}",
    subtitle=f"work/{today.isoformat()}.md  ·  edits saved on Save click",
)

# --- Today's prep: auto-loaded from cache OR build with one click ---
cached_standup = prep_mod.read_cached_standup(cfg, day=today)
cached_inbox = prep_mod.read_cached_inbox(cfg, day=today)

cprep, cprep_btn = st.columns([5, 1])
with cprep:
    style.label("Today's prep")
with cprep_btn:
    if st.button("Run prep", help="Build SOD (if needed), inbox, standup",
                 use_container_width=True, key="run_prep_top"):
        try:
            result = style.run_with_streaming_logs(
                "Morning prep — SOD + inbox + standup",
                prep_mod.run, cfg, day=today,
            )
            st.toast(f"Prep done — {result.inbox_count} inbox item(s)")
            st.rerun()
        except Exception as exc:
            st.error(f"Prep failed: {exc}")

prep_col1, prep_col2 = st.columns(2, gap="medium")

with prep_col1:
    with st.container(border=True):
        st.markdown(
            '<div style="font-weight:700; font-size:1rem; margin-bottom:0.5rem;">'
            'Standup brief</div>',
            unsafe_allow_html=True,
        )
        if cached_standup:
            st.markdown(cached_standup)
            cs1, cs2 = st.columns([1, 4])
            with cs1:
                style.copy_button(cached_standup, button_label="Copy", height=46)
            with cs2:
                st.caption(
                    f"Cached for {today.isoformat()} — re-run prep to refresh."
                )
        else:
            style.empty_state(
                "No standup yet",
                "Click Run prep above (or run `vamos prep` from a terminal).",
            )

with prep_col2:
    with st.container(border=True):
        st.markdown(
            '<div style="font-weight:700; font-size:1rem; margin-bottom:0.5rem;">'
            'Inbox preview</div>',
            unsafe_allow_html=True,
        )
        if cached_inbox is None:
            style.empty_state(
                "No inbox cached",
                "Click Run prep above to build it.",
            )
        elif not cached_inbox:
            st.markdown(
                "<div style='color:var(--text-muted); padding:0.5rem 0;'>"
                "Nothing wants your attention.</div>",
                unsafe_allow_html=True,
            )
        else:
            # Top 6, with kind pill + actor + title link
            for it in cached_inbox[:6]:
                tone = {"mention": "red", "review-request": "amber",
                        "new-assignment": "indigo"}.get(it.get("kind"), "slate")
                kind = it.get("kind", "").replace("-", " ")
                tid = it.get("ticket_id") or it.get("pr_id")
                ref = (
                    f' · <a href="{it.get("url","")}" target="_blank" '
                    f'style="color:var(--accent); text-decoration:none;">'
                    f'{"PR #" if it.get("pr_id") else "#"}{tid}</a>'
                    if tid else ""
                )
                title = (it.get("title") or "")[:90]
                st.markdown(
                    f'<div style="padding:0.4rem 0; border-bottom:1px solid var(--border);">'
                    f'<div style="display:flex; gap:0.5rem; align-items:center;">'
                    f'{style.pill(kind, tone)} '
                    f'<span style="font-weight:500; font-size:0.875rem;">{title}{ref}</span>'
                    f'</div>'
                    f'<div style="color:var(--text-muted); font-size:0.75rem; '
                    f'margin-top:0.125rem;">by {it.get("actor","?")}</div></div>',
                    unsafe_allow_html=True,
                )
            if len(cached_inbox) > 6:
                st.caption(
                    f"... and {len(cached_inbox) - 6} more — open the Inbox page."
                )

st.markdown("<div style='margin-top:1.5rem;'></div>", unsafe_allow_html=True)

col_main, col_actions = st.columns([3, 1], gap="large")

# --- Main: editable markdown ---
with col_main:
    if not md_path.exists():
        style.empty_state(
            f"No markdown for {today.isoformat()}",
            "Click Run SOD in the Actions panel to pull today's assigned tickets.",
        )
    else:
        cache_key = f"md_content::{md_path}"
        if cache_key not in st.session_state:
            st.session_state[cache_key] = md_path.read_text(encoding="utf-8")

        tab_edit, tab_preview = st.tabs(["Edit", "Preview"])

        with tab_edit:
            new_text = st.text_area(
                "Markdown source",
                value=st.session_state[cache_key],
                height=600,
                key=f"editor::{md_path}",
                label_visibility="collapsed",
            )

            row1, row2, row3 = st.columns([1, 1, 4])
            with row1:
                if st.button("Save", type="primary", use_container_width=True):
                    md_path.write_text(new_text, encoding="utf-8")
                    st.session_state[cache_key] = new_text
                    st.toast(f"Saved {md_path.name}")
            with row2:
                if st.button("Reload", use_container_width=True,
                             help="Reload from disk (discards unsaved edits)"):
                    st.session_state[cache_key] = md_path.read_text(encoding="utf-8")
                    st.rerun()
            with row3:
                changed = new_text != st.session_state[cache_key]
                if changed:
                    st.markdown(
                        f'<div style="padding-top:0.5rem;">{style.pill("UNSAVED", "amber")}</div>',
                        unsafe_allow_html=True,
                    )
                else:
                    mtime = datetime.fromtimestamp(md_path.stat().st_mtime).strftime("%H:%M:%S")
                    st.markdown(
                        f'<div style="padding-top:0.5rem; color:var(--text-muted); font-size:0.75rem;">'
                        f'last saved {mtime}</div>',
                        unsafe_allow_html=True,
                    )

        with tab_preview:
            st.markdown(st.session_state[cache_key])

# --- Right column: actions ---
with col_actions:
    with st.container(border=True):
        st.markdown(
            '<div style="font-weight:700; font-size:1rem; margin-bottom:0.75rem; '
            'color:var(--text-primary);">Actions</div>',
            unsafe_allow_html=True,
        )

        if st.button("Run SOD", use_container_width=True,
                     help="Pull today's assigned tickets"):
            try:
                path = style.run_with_streaming_logs(
                    "Pulling assigned tickets (SOD)",
                    sod.run, cfg, force=False, day=today,
                )
                cache_key = f"md_content::{md_path}"
                if md_path.exists():
                    st.session_state[cache_key] = md_path.read_text(encoding="utf-8")
                st.toast(f"Wrote {Path(path).name}")
                st.rerun()
            except Exception as exc:
                st.error(f"SOD failed: {exc}")

        st.markdown("<div style='height:0.5rem;'></div>", unsafe_allow_html=True)
        style.label("Sync")

        if st.button("Dry-run sync", use_container_width=True,
                     help="Preview what sync would change"):
            try:
                result = style.run_with_streaming_logs(
                    "Running dry-run sync (claude -p, no writes)",
                    sync.run, cfg, dry_run=True, day=today,
                )
                st.success(
                    f"Proposed: {result.actions_proposed}  ·  Failed: {result.actions_failed}"
                )
                if result.summary:
                    st.markdown(result.summary)
            except Exception as exc:
                st.error(f"Sync failed: {exc}")

        if st.button("Apply sync", type="primary", use_container_width=True,
                     help="Commit changes to ADO"):
            try:
                result = style.run_with_streaming_logs(
                    "Syncing to ADO (claude -p, live writes)",
                    sync.run, cfg, dry_run=False, day=today,
                )
                st.success(
                    f"Executed: {result.actions_executed}  ·  Failed: {result.actions_failed}"
                )
            except Exception as exc:
                st.error(f"Sync failed: {exc}")

        st.markdown("<div style='height:0.5rem;'></div>", unsafe_allow_html=True)
        style.label("End of day")
        skip_post = st.checkbox(
            "Don't post (just generate)", value=True,
            help="Generates the EOD locally but doesn't send to Teams/Slack",
        )
        if st.button("Run EOD", use_container_width=True):
            try:
                text = style.run_with_streaming_logs(
                    "Generating EOD (final sync + summary)",
                    eod.run, cfg, dry_run=False, skip_sync=False,
                    skip_post=skip_post, skip_slack=skip_post, day=today,
                )
                st.session_state["last_eod"] = text
                st.toast("EOD ready below")
            except Exception as exc:
                st.error(f"EOD failed: {exc}")

        st.markdown("<div style='height:0.5rem;'></div>", unsafe_allow_html=True)
        style.label("Standup")
        if st.button("Generate standup", use_container_width=True,
                     help="Auto-draft yesterday/today/blockers"):
            try:
                text = style.run_with_streaming_logs(
                    "Building standup brief", standup_mod.run, cfg, day=today,
                )
                st.session_state["last_standup"] = text
                st.toast("Standup ready below")
            except Exception as exc:
                st.error(f"Standup failed: {exc}")

        st.markdown("<div style='height:0.5rem;'></div>", unsafe_allow_html=True)
        style.label("Quick capture")
        cap_text = st.text_area(
            "Capture a thought", value="", height=80, key="capture_text",
            label_visibility="collapsed",
            placeholder="Paste a meeting note, idea, or bug — first line becomes the [NEW] title.",
        )
        cap_cust = st.text_input("Customer (optional)", value="", key="capture_customer")
        if st.button("Append [NEW] to today's MD", use_container_width=True):
            if not cap_text.strip():
                st.warning("Type something to capture.")
            else:
                try:
                    capture_mod.run(cfg, text=cap_text, customer=(cap_cust or None), day=today)
                    cache_key = f"md_content::{md_path}"
                    if md_path.exists():
                        st.session_state[cache_key] = md_path.read_text(encoding="utf-8")
                    st.session_state["capture_text"] = ""
                    st.toast("Captured")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Capture failed: {exc}")

# --- Standup output ---
last_standup = st.session_state.get("last_standup")
if last_standup:
    st.markdown("<div style='margin-top:2rem;'></div>", unsafe_allow_html=True)
    style.section_header("Standup brief", subtitle="Yesterday · today · blockers — paste into Slack")
    cs1, cs2 = st.columns([1, 4])
    with cs1:
        style.copy_button(last_standup, button_label="Copy standup", height=50)
    with cs2:
        st.caption("Yesterday/today/blockers, auto-built from your MD + closed tickets.")
    with st.container(border=True):
        st.markdown(last_standup)
    with st.expander("Raw markdown source"):
        st.code(last_standup, language="markdown")

# --- EOD output ---
last_eod = st.session_state.get("last_eod")
if last_eod:
    st.markdown("<div style='margin-top:2rem;'></div>", unsafe_allow_html=True)
    style.section_header(
        "End-of-day summary",
        subtitle="Click Copy to put it on your clipboard — paste into Slack/Teams "
                 "if the webhook isn't wired",
    )

    cc1, cc2 = st.columns([1, 4])
    with cc1:
        style.copy_button(last_eod, button_label="Copy EOD", height=50)
    with cc2:
        st.caption("Rendered preview below; raw markdown after that.")

    with st.container(border=True):
        st.markdown(last_eod)

    with st.expander("Show raw markdown source"):
        st.code(last_eod, language="markdown")
