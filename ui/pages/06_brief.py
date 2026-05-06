"""Brief — 1:1 brief generator for managers."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

from vamos import brief as brief_mod  # noqa: E402
from vamos import retro as retro_mod  # noqa: E402

from ui import style  # noqa: E402

st.set_page_config(page_title="Brief · vamos", page_icon=None, layout="wide")
style.apply()
style.theme_toggle_in_sidebar()

cfg = style.get_cfg(st.session_state.get("profile_arg"), board=st.session_state.get("board_arg"))
st.session_state["cfg"] = cfg

style.section_header(
    "Manager briefs",
    subtitle="1:1 prep per engineer · sprint retro starter",
)

tab_oneonone, tab_retro = st.tabs(["1:1 brief", "Sprint retro"])

# ---- 1:1 brief ----
with tab_oneonone:
    if "engineer_list" not in st.session_state:
        st.session_state["engineer_list"] = []

    cc1, cc2, cc3 = st.columns([2, 1, 1])
    with cc1:
        if st.button("Load engineer list from current snapshot",
                     help="Pulls everyone with assigned items in the configured area path"):
            try:
                st.session_state["engineer_list"] = style.run_with_streaming_logs(
                    "Loading engineer list from snapshot", brief_mod.list_engineers, cfg,
                )
                st.toast(f"{len(st.session_state['engineer_list'])} engineer(s)")
            except Exception as exc:
                st.error(f"List failed: {exc}")

        engineers = st.session_state.get("engineer_list", [])
        if engineers:
            engineer = st.selectbox("Engineer", engineers, key="brief_engineer_select")
        else:
            engineer = st.text_input(
                "Engineer name or email",
                value=st.session_state.get("brief_engineer_text", ""),
                key="brief_engineer_text",
            )

    with cc2:
        weeks = st.number_input("Window (weeks)", min_value=1, max_value=12, value=1)

    with cc3:
        st.markdown("<div style='height:1.7rem;'></div>", unsafe_allow_html=True)
        if st.button("Generate brief", type="primary", use_container_width=True):
            if not engineer:
                st.error("Pick an engineer first.")
            else:
                try:
                    text = style.run_with_streaming_logs(
                        f"Building 1:1 brief for {engineer}",
                        brief_mod.run, cfg, engineer=engineer, weeks=int(weeks),
                    )
                    st.session_state["last_brief"] = text
                    st.session_state["last_brief_engineer"] = engineer
                    st.toast("Brief ready")
                except Exception as exc:
                    st.error(f"Brief failed: {exc}")

    last_brief = st.session_state.get("last_brief")
    if last_brief:
        cb1, cb2 = st.columns([1, 4])
        with cb1:
            style.copy_button(last_brief, button_label="Copy brief", height=50)
        with cb2:
            st.caption("Paste into your 1:1 doc.")
        with st.container(border=True):
            st.markdown(last_brief)
        with st.expander("Raw markdown"):
            st.code(last_brief, language="markdown")
    else:
        style.empty_state(
            "No brief yet",
            "Pick an engineer and a window, then click Generate brief.",
        )

# ---- Retro ----
with tab_retro:
    cr1, cr2, cr3 = st.columns([2, 1, 1])
    with cr1:
        iter_input = st.text_input(
            "Iteration path (blank = HYGIENE_ITERATION_PATH)",
            value=st.session_state.get("retro_iter_input", ""),
            key="retro_iter_input",
        )
    with cr2:
        retro_weeks = st.number_input("Window (weeks)", min_value=1, max_value=8, value=2,
                                      key="retro_weeks")
    with cr3:
        st.markdown("<div style='height:1.7rem;'></div>", unsafe_allow_html=True)
        if st.button("Generate retro starter", type="primary", use_container_width=True):
            try:
                text = style.run_with_streaming_logs(
                    "Building retro starter (shipped, missed, themes, customers)",
                    retro_mod.run, cfg,
                    iteration_path=(iter_input.strip() or None),
                    weeks=int(retro_weeks),
                )
                st.session_state["last_retro"] = text
                st.toast("Retro draft ready")
            except Exception as exc:
                st.error(f"Retro failed: {exc}")

    last_retro = st.session_state.get("last_retro")
    if last_retro:
        cb1, cb2 = st.columns([1, 4])
        with cb1:
            style.copy_button(last_retro, button_label="Copy retro", height=50)
        with cb2:
            st.caption("Paste into your retro doc and edit.")
        with st.container(border=True):
            st.markdown(last_retro)
        with st.expander("Raw markdown"):
            st.code(last_retro, language="markdown")
    else:
        style.empty_state(
            "No retro yet",
            "Pick a window (default last 2 weeks) and click Generate.",
        )
