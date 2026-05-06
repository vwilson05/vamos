"""PR queue — triaged review queue (blocked-on-me, role-aware, buddy-routing)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

from vamos.pr_review import runner as pr_runner, queue as pr_queue  # noqa: E402

from ui import style  # noqa: E402

st.set_page_config(page_title="PR queue · vamos", page_icon=None, layout="wide")
style.apply()
style.theme_toggle_in_sidebar()

cfg = style.get_cfg(st.session_state.get("profile_arg"), board=st.session_state.get("board_arg"))
st.session_state["cfg"] = cfg

style.section_header(
    "PR queue",
    subtitle="Triaged review queue across all repos  ·  blocked-on-me first  ·  trigger ad-hoc reviews",
)


def _render_card(q):
    """Render one PR card (used in multiple sections of the queue tab)."""
    tags = []
    if q.blocked_on_me:
        tags.append(style.pill("BLOCKED ON ME", "red"))
    role_tone = {"author": "indigo", "reviewer": "amber", "both": "indigo"}.get(q.role, "slate")
    tags.append(style.pill(q.role.upper(), role_tone))
    if q.is_draft:
        tags.append(style.pill("DRAFT", "slate"))
    if q.buddy_skipped:
        tags.append(style.pill(f"BUDDY SKIPPED · {q.buddy_skipped}", "amber"))
    age_tone = "red" if q.age_days > 5 else ("amber" if q.age_days > 2 else "slate")
    tags.append(style.pill(f"{q.age_days}d old", age_tone))

    st.markdown(
        f'<div style="background:var(--bg-surface); border:1px solid var(--border); '
        f'border-radius:8px; padding:0.75rem 1rem; margin-bottom:0.5rem;">'
        f'<div style="display:flex; justify-content:space-between; align-items:start; gap:1rem;">'
        f'<div style="flex:1;">'
        f'<div style="font-weight:600; font-size:0.9375rem; color:var(--text-primary);">'
        f'<a href="{q.url}" target="_blank" '
        f'style="color:var(--text-primary); text-decoration:none;">'
        f'#{q.pr_id} — {q.title}</a></div>'
        f'<div style="color:var(--text-muted); font-size:0.8125rem; margin-top:0.25rem;">'
        f'<code>{q.repo}</code>  ·  by {q.author}  ·  '
        f'<code style="font-size:0.75rem;">{q.source_branch}</code> '
        f'→ <code style="font-size:0.75rem;">{q.target_branch}</code></div>'
        f'</div>'
        f'<div style="text-align:right; min-width:200px; line-height:2;">'
        f'{" ".join(tags)}</div></div></div>',
        unsafe_allow_html=True,
    )


tab_queue, tab_load, tab_review = st.tabs(["Triaged queue", "Review load", "Run review"])

# ----------------------------------------------------------------------------
# Tab 1: triaged queue
# ----------------------------------------------------------------------------
with tab_queue:
    cc1, cc2, cc3 = st.columns([2, 1, 1])
    with cc1:
        repo_input = st.text_input(
            "Repo (blank = all repos in project)",
            value=st.session_state.get("pr_repo", ""),
            key="pr_repo",
        )
    with cc2:
        st.markdown("<div style='height:1.7rem;'></div>", unsafe_allow_html=True)
        if st.button("Refresh queue", use_container_width=True, type="primary"):
            try:
                items = style.run_with_streaming_logs(
                    "Building triaged review queue across all repos",
                    pr_queue.build_queue, cfg, repo=(repo_input.strip() or None),
                )
                st.session_state["pr_queue_items"] = items
                st.toast(f"{len(items)} PR(s)")
            except Exception as exc:
                st.error(f"Queue build failed: {exc}")
    with cc3:
        st.markdown("<div style='height:1.7rem;'></div>", unsafe_allow_html=True)
        items = st.session_state.get("pr_queue_items", [])
        if items:
            blocked_me = sum(1 for q in items if q.blocked_on_me)
            mine = sum(1 for q in items if q.role in ("author", "reviewer", "both"))
            st.markdown(
                f'<div style="text-align:right; padding-top:0.25rem;">'
                f'{style.pill(f"{blocked_me} blocked on me", "red" if blocked_me else "slate")}  '
                f'{style.pill(f"{mine} mine", "indigo")}  '
                f'{style.pill(f"{len(items)} total", "slate")}</div>',
                unsafe_allow_html=True,
            )

    items = st.session_state.get("pr_queue_items", [])
    if not items:
        style.empty_state("No PRs loaded", "Click Refresh queue above.")
    else:
        # Section: blocked-on-me
        bom = [q for q in items if q.blocked_on_me]
        if bom:
            st.markdown("##### Blocked on me")
            for q in bom:
                _render_card(q)

        # Section: assigned (author/reviewer) but not blocked-on-me
        mine = [q for q in items if not q.blocked_on_me and q.role in ("author", "reviewer", "both")]
        if mine:
            st.markdown("##### Mine — author or reviewer")
            for q in mine:
                _render_card(q)

        # Section: everyone else
        rest = [q for q in items if not q.blocked_on_me and q.role == "observer"]
        if rest:
            with st.expander(f"All other active PRs ({len(rest)})"):
                for q in rest:
                    _render_card(q)


# ----------------------------------------------------------------------------
# Tab 2: review load
# ----------------------------------------------------------------------------
with tab_load:
    if st.button("Compute review load across all repos", type="primary"):
        try:
            loads = style.run_with_streaming_logs(
                "Counting reviewer assignments across every repo",
                pr_queue.review_load, cfg,
            )
            st.session_state["pr_load"] = loads
            st.toast(f"Counted {sum(loads.values())} reviewer slots across {len(loads)} people")
        except Exception as exc:
            st.error(f"Load computation failed: {exc}")
    loads = st.session_state.get("pr_load")
    if loads:
        with st.container(border=True):
            for name, n in loads.items():
                width = min(100, int(n / max(loads.values()) * 100)) if max(loads.values()) else 0
                st.markdown(
                    f'<div style="display:flex; justify-content:space-between; '
                    f'align-items:center; padding:0.4rem 0; '
                    f'border-bottom:1px solid var(--border);">'
                    f'<div style="flex:1; font-weight:500;">{name}</div>'
                    f'<div style="flex:2; padding:0 1rem;">'
                    f'<div style="background:var(--accent-soft); border-radius:6px; '
                    f'height:8px; width:{width}%;"></div></div>'
                    f'<div style="font-family:JetBrains Mono,monospace; '
                    f'color:var(--text-secondary);">{n}</div></div>',
                    unsafe_allow_html=True,
                )
    else:
        style.empty_state(
            "No load data yet",
            "Click the button above to count active-PR reviewer assignments per person.",
        )

# ----------------------------------------------------------------------------
# Tab 3: trigger an ad-hoc review
# ----------------------------------------------------------------------------
with tab_review:
    with st.container(border=True):
        st.markdown(
            '<div style="font-weight:700; font-size:1rem; margin-bottom:0.75rem;">Run review</div>',
            unsafe_allow_html=True,
        )
        col1, col2 = st.columns(2)
        with col1:
            pr_id_input = st.number_input("PR id", min_value=1, value=1, step=1)
            review_repo = st.text_input(
                "Repo (optional)", value="",
                help="Leave blank to auto-search all repos for this PR id",
            )
        with col2:
            no_post = st.checkbox("Don't post (local only)", value=True)
            st.markdown("<div style='height:0.5rem;'></div>", unsafe_allow_html=True)
            if st.button("Review PR", type="primary", use_container_width=True):
                try:
                    code = style.run_with_streaming_logs(
                        f"Reviewing PR #{int(pr_id_input)}",
                        pr_runner.run, cfg,
                        pr_id=int(pr_id_input),
                        repo=(review_repo.strip() or None),
                        interactive=False,
                        no_post=no_post,
                        watch=False,
                    )
                    if code == 0:
                        st.toast(f"Review complete (exit {code})")
                    else:
                        st.warning(f"Review exited with code {code}.")
                except Exception as exc:
                    st.error(f"Review failed: {exc}")
        st.caption(
            "Reviews are saved to `state/pr-review/logs/`. "
            "Comments include `<!-- vamos:pr-review -->` so re-runs never double-post."
        )
