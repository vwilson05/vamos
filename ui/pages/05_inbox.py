"""Inbox — engineer's unified attention feed."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

from vamos import inbox as inbox_mod  # noqa: E402

from ui import style  # noqa: E402

st.set_page_config(page_title="Inbox · vamos", page_icon=None, layout="wide")
style.apply()
style.theme_toggle_in_sidebar()

cfg = style.get_cfg(st.session_state.get("profile_arg"), board=st.session_state.get("board_arg"))
st.session_state["cfg"] = cfg

style.section_header(
    "Inbox",
    subtitle="Things wanting your attention — review requests, comments, mentions, new P1/P2",
)

cc1, cc2, cc3 = st.columns([1, 1, 3])
with cc1:
    hours = st.number_input("Look-back (hours)", min_value=4, max_value=336, value=48, step=4)
with cc2:
    st.markdown("<div style='height:1.7rem;'></div>", unsafe_allow_html=True)
    if st.button("Refresh", type="primary", use_container_width=True):
        try:
            items = style.run_with_streaming_logs(
                f"Building inbox (last {int(hours)}h, across all project repos)",
                inbox_mod.build, cfg, since_hours=int(hours),
            )
            st.session_state["inbox_items"] = items
            st.toast(f"{len(items)} item(s)")
        except Exception as exc:
            st.error(f"Inbox failed: {exc}")
with cc3:
    st.markdown("<div style='height:1.7rem;'></div>", unsafe_allow_html=True)
    items = st.session_state.get("inbox_items", [])
    if items:
        kinds: dict[str, int] = {}
        for it in items:
            kinds[it.kind] = kinds.get(it.kind, 0) + 1
        pills = " ".join(
            style.pill(f"{n} {k.replace('-', ' ')}",
                       {"mention": "red", "review-request": "amber",
                        "new-assignment": "indigo"}.get(k, "slate"))
            for k, n in kinds.items()
        )
        st.markdown(
            f'<div style="text-align:right; padding-top:0.25rem;">{pills}</div>',
            unsafe_allow_html=True,
        )

items = st.session_state.get("inbox_items", [])
if not items:
    style.empty_state("Inbox empty (or not loaded)", "Click Refresh to scan ADO.")
else:
    KIND_LABEL = {
        "mention": "Mentions",
        "review-request": "Review requests",
        "new-assignment": "New high-priority assignments",
        "pr-comment": "PR comments",
        "ticket-comment": "Ticket comments",
    }
    KIND_TONE = {
        "mention": "red",
        "review-request": "amber",
        "new-assignment": "indigo",
        "pr-comment": "slate",
        "ticket-comment": "slate",
    }
    by_kind: dict[str, list] = {}
    for it in items:
        by_kind.setdefault(it.kind, []).append(it)

    for kind in ["mention", "review-request", "new-assignment", "pr-comment", "ticket-comment"]:
        group = by_kind.get(kind, [])
        if not group:
            continue
        st.markdown(
            f'<div style="margin-top:1.25rem; margin-bottom:0.5rem;">'
            f'<span style="font-weight:700; font-size:1rem;">{KIND_LABEL[kind]}</span>  '
            f'{style.pill(str(len(group)), KIND_TONE[kind])}</div>',
            unsafe_allow_html=True,
        )
        for it in group[:25]:
            ref = (
                f' · <a href="{it.url}" target="_blank" '
                f'style="color:var(--accent); text-decoration:none;">'
                f'{"PR #" if it.pr_id else "#"}{it.pr_id or it.ticket_id}</a>'
                if (it.pr_id or it.ticket_id) else ""
            )
            when_str = it.when.strftime("%a %m-%d %H:%M") if hasattr(it.when, "strftime") else str(it.when)
            st.markdown(
                f'<div style="background:var(--bg-surface); border:1px solid var(--border); '
                f'border-radius:8px; padding:0.625rem 1rem; margin-bottom:0.4rem;">'
                f'<div style="font-weight:600; color:var(--text-primary); font-size:0.9375rem;">'
                f'{it.title[:120]}{ref}</div>'
                f'<div style="color:var(--text-muted); font-size:0.75rem; margin-top:0.125rem;">'
                f'{when_str} · by {it.actor}</div>'
                f'<div style="color:var(--text-secondary); font-size:0.875rem; margin-top:0.375rem;">'
                f'{it.summary or ""}</div></div>',
                unsafe_allow_html=True,
            )
        if len(group) > 25:
            st.caption(f"...and {len(group) - 25} more in this category.")
