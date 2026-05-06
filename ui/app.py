"""vamos — Streamlit UI home page."""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

from ui import style  # noqa: E402

st.set_page_config(
    page_title="vamos",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)
style.apply()

# --- Sidebar ---
with st.sidebar:
    st.markdown(
        '<div style="padding:8px 0 16px;">'
        '<div style="font-weight:700; font-size:1.25rem; color:var(--text-primary);">vamos</div>'
        '<div style="color:var(--text-muted); font-size:0.75rem;">HaloMD agent suite</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    style.theme_toggle_in_sidebar()

    profile = st.selectbox(
        "Profile",
        options=["(default)", "personal", "team"],
        help="Selects which .env profile to load.",
    )
    profile_arg = None if profile == "(default)" else profile

    # Global board selector — applies to all team agents
    board_arg = style.board_picker_in_sidebar()

    try:
        cfg = style.get_cfg(profile_arg, board=board_arg)
        st.markdown(
            f'<div style="background:var(--success-bg); border:1px solid var(--success-border); '
            f'border-radius:8px; padding:8px 12px; margin-top:8px;">'
            f'<div style="color:var(--success-fg); font-weight:600; font-size:0.75rem; letter-spacing:0.05em;">'
            f'CONNECTED</div>'
            f'<div style="font-size:0.875rem; margin-top:2px; color:var(--text-primary);">{cfg.ado_project}</div>'
            f'<div style="color:var(--text-muted); font-size:0.75rem; margin-top:2px;">'
            f'{cfg.ado_org_url.replace("https://","").rstrip("/")}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    except SystemExit as exc:
        st.error(f"Config error: {exc}")
        st.stop()

    st.session_state["cfg"] = cfg
    st.session_state["profile_arg"] = profile_arg
    st.session_state["board_arg"] = board_arg

    st.markdown("---")
    style.label("Pages")
    st.markdown(
        """
- **My day** — daily flow + markdown editor + standup + quick capture
- **Team status** — metrics, healthcheck, hygiene, trends, customers, at-risk
- **PR queue** — triaged review queue (blocked-on-me first)
- **Inbox** — review requests, comments, mentions, new P1/P2
- **Brief** — 1:1 brief generator + sprint retro
- **Help** — CLI reference, env vars, hygiene rules, what's new
        """
    )

# --- Hero ---
st.markdown(
    '<div style="margin-bottom:2rem;">'
    '<div style="font-size:2.5rem; font-weight:700; letter-spacing:-0.025em; color:var(--text-primary);">'
    'vamos</div>'
    '<div style="color:var(--text-muted); font-size:1.125rem; margin-top:0.25rem;">'
    'HaloMD agent suite — personal flow, team reporting, PR review'
    '</div></div>',
    unsafe_allow_html=True,
)

# --- Quick stats from cached state files (no API hit) ---
style.label("At a glance")

state_dir = cfg.state_dir
hygiene_summary = None
hygiene_files = sorted((state_dir / "hygiene").glob("*.json"), reverse=True) if (state_dir / "hygiene").exists() else []
if hygiene_files:
    try:
        hygiene_summary = json.loads(hygiene_files[0].read_text())
    except (json.JSONDecodeError, OSError):
        pass

c1, c2, c3, c4 = st.columns(4)
with c1:
    has_today = (cfg.work_dir / f"{date.today().isoformat()}.md").exists()
    st.markdown(
        style.kpi("Today's MD", "ready" if has_today else "—",
                  tone="green" if has_today else "slate"),
        unsafe_allow_html=True,
    )
with c2:
    n = (hygiene_summary or {}).get("summary", {}).get("blocker", 0) if hygiene_summary else "—"
    st.markdown(style.kpi("Hygiene blockers", str(n),
                          tone="red" if isinstance(n, int) and n > 0 else "slate"),
                unsafe_allow_html=True)
with c3:
    n = (hygiene_summary or {}).get("summary", {}).get("should-fix", 0) if hygiene_summary else "—"
    st.markdown(style.kpi("Should-fix", str(n),
                          tone="amber" if isinstance(n, int) and n > 0 else "slate"),
                unsafe_allow_html=True)
with c4:
    n = (hygiene_summary or {}).get("summary", {}).get("nit", 0) if hygiene_summary else "—"
    st.markdown(style.kpi("Nits", str(n),
                          tone="indigo" if isinstance(n, int) and n > 0 else "slate"),
                unsafe_allow_html=True)

st.markdown("<div style='margin-top:2rem;'></div>", unsafe_allow_html=True)

# --- Welcome card ---
with st.container(border=True):
    st.markdown(
        """
### Welcome

Pick a page from the sidebar:

- **My day** — view + edit today's markdown, run sod / sync / eod, generate standup, quick-capture meeting notes.
- **Team status** — metrics, healthcheck, hygiene, trends with sparklines, customer breakdown, at-risk scan.
- **PR queue** — triaged queue putting "blocked on me" PRs first; review-load distribution; trigger ad-hoc reviews.
- **Inbox** — every review request, comment, @-mention, and high-priority assignment in one feed.
- **Brief** — 1:1 prep per engineer, sprint retro starter — both copy-pastable.
- **Help** — every CLI command, env var, hygiene rule, plus a What's New changelog.

The "At a glance" tiles above show the latest cached results — no API hit until you click **Run** on a page.
        """
    )

st.markdown("<div style='margin-top:1rem;'></div>", unsafe_allow_html=True)
st.caption(
    f"work_dir: `{cfg.work_dir}`  ·  state_dir: `{cfg.state_dir}`  ·  "
    f"read_only: {cfg.ado_read_only}"
)
