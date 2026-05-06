"""Settings — edit .env files and crons.yml from the browser."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

from vamos import settings as settings_mod  # noqa: E402
from vamos.ado import ADOClient  # noqa: E402

from ui import style  # noqa: E402

st.set_page_config(page_title="Settings · vamos", page_icon=None, layout="wide")
style.apply()
style.theme_toggle_in_sidebar()

cfg = style.get_cfg(st.session_state.get("profile_arg"), board=st.session_state.get("board_arg"))
st.session_state["cfg"] = cfg

style.section_header(
    "Settings",
    subtitle="Edit .env, manage cron schedule, test the ADO connection — no terminal needed.",
)

tab_env, tab_crons = st.tabs([".env / credentials", "Cron schedule"])

# ============================================================================
# .env editor
# ============================================================================
with tab_env:
    profile_choice = st.radio(
        "File to edit",
        options=[".env (baseline)", ".env.personal", ".env.team"],
        horizontal=True,
        help="Profile-specific files overlay the baseline. Pick which file your edits go to.",
        key="settings_profile_radio",
    )
    profile_map = {
        ".env (baseline)": None,
        ".env.personal": "personal",
        ".env.team": "team",
    }
    profile = profile_map[profile_choice]
    target = settings_mod.env_path(profile)
    st.caption(f"Editing: `{target}`  ·  exists: {'yes' if target.exists() else 'no (will be created on save)'}")

    current = settings_mod.read_env(target) if target.exists() else {}

    # Per-section accordion of fields
    schema = settings_mod.schema_by_section()

    # Track edits in session state, keyed by file path so switching profile
    # doesn't lose work (within reason).
    edits_key = f"settings_edits::{target}"
    if edits_key not in st.session_state:
        st.session_state[edits_key] = {}

    show_secrets_key = f"show_secrets::{target}"
    if show_secrets_key not in st.session_state:
        st.session_state[show_secrets_key] = False

    cs1, cs2 = st.columns([3, 1])
    with cs2:
        st.markdown("<div style='height:1.5rem;'></div>", unsafe_allow_html=True)
        st.session_state[show_secrets_key] = st.checkbox(
            "Reveal secrets",
            value=st.session_state[show_secrets_key],
            help="Show actual PAT / webhook values instead of masked dots.",
            key=f"reveal_{target}",
        )

    show_secrets = st.session_state[show_secrets_key]

    for section, fields in schema.items():
        with st.expander(section, expanded=section in ("ADO connection", "Channels")):
            for fd in fields:
                stored = current.get(fd.key, "")
                widget_key = f"setting_{fd.key}_{target}"
                # Render appropriate widget
                if fd.kind == "bool":
                    val_bool = stored.strip().lower() in ("1", "true", "yes")
                    new = st.checkbox(fd.label, value=val_bool, key=widget_key,
                                      help=fd.help)
                    new_str = "true" if new else "false"
                elif fd.kind == "int":
                    try:
                        cur_int = int(stored) if stored else 0
                    except ValueError:
                        cur_int = 0
                    new_int = st.number_input(
                        fd.label, value=cur_int, step=1, key=widget_key, help=fd.help,
                    )
                    new_str = str(int(new_int))
                elif fd.kind == "select":
                    options = fd.options or [""]
                    idx = options.index(stored) if stored in options else 0
                    new_str = st.selectbox(fd.label, options=options, index=idx,
                                           key=widget_key, help=fd.help)
                elif fd.kind == "secret":
                    if show_secrets:
                        new_str = st.text_input(fd.label, value=stored, key=widget_key,
                                                placeholder=fd.placeholder, help=fd.help)
                    else:
                        masked = settings_mod.mask_secret(stored)
                        new_str = st.text_input(
                            fd.label, value=masked, key=widget_key,
                            type="password",
                            help=(fd.help + " (masked — toggle 'Reveal secrets' to edit)").strip(),
                        )
                        # If user typed something other than the mask, treat as new value
                        if new_str and not all(c == "•" for c in new_str.replace(stored[-4:] if len(stored) >= 4 else "", "")):
                            pass  # keep new_str as-is (user typed)
                        else:
                            new_str = stored  # they didn't change it
                else:
                    new_str = st.text_input(fd.label, value=stored, key=widget_key,
                                            placeholder=fd.placeholder, help=fd.help)
                # Track only changed values
                if new_str != stored:
                    st.session_state[edits_key][fd.key] = new_str
                elif fd.key in st.session_state[edits_key]:
                    del st.session_state[edits_key][fd.key]

    edits = st.session_state[edits_key]
    n_edits = len(edits)

    st.markdown("---")
    a1, a2, a3, a4 = st.columns([1, 1, 1, 2])
    with a1:
        save_disabled = n_edits == 0
        if st.button("Save changes", type="primary", disabled=save_disabled,
                     use_container_width=True):
            try:
                settings_mod.write_env(target, edits)
                st.session_state[edits_key] = {}
                st.toast(f"Saved {n_edits} change(s) to {target.name}")
                st.rerun()
            except Exception as exc:
                st.error(f"Save failed: {exc}")
    with a2:
        if st.button("Revert", disabled=save_disabled, use_container_width=True):
            st.session_state[edits_key] = {}
            st.rerun()
    with a3:
        if st.button("Test connection", use_container_width=True):
            try:
                refreshed = style.get_cfg(profile)
                client = ADOClient(refreshed.ado_org_url, refreshed.ado_project,
                                   refreshed.ado_pat, read_only=True)
                ids = client.query_assigned(refreshed.assigned_user_clause)
                st.success(
                    f"OK — auth works. {len(ids)} item(s) assigned to {refreshed.assigned_user_clause}."
                )
            except Exception as exc:
                st.error(f"Connection failed: {exc}")
    with a4:
        if n_edits:
            st.caption(f"{n_edits} unsaved change(s): {', '.join(edits.keys())}")
        else:
            st.caption("No unsaved changes.")

# ============================================================================
# Cron editor
# ============================================================================
with tab_crons:
    st.markdown(
        "Toggle cron entries on/off. After saving, run **Install** to apply to your "
        "system crontab (or copy the rendered block manually)."
    )

    crons = settings_mod.read_crons()
    if not crons:
        style.empty_state("No crons.yml found",
                          "Drop crons.yml.example into crons.yml at the repo root to get started.")
    else:
        edit_key = "settings_crons_edits"
        if edit_key not in st.session_state:
            st.session_state[edit_key] = {c["name"]: dict(c) for c in crons}
        edits = st.session_state[edit_key]

        for c in crons:
            name = c["name"]
            with st.container(border=True):
                top = st.columns([3, 1])
                with top[0]:
                    st.markdown(
                        f"<div style='font-weight:700; font-size:1rem; "
                        f"color:var(--text-primary);'>{name}</div>"
                        f"<div style='color:var(--text-muted); font-size:0.8125rem;'>"
                        f"{c.get('description','')}</div>",
                        unsafe_allow_html=True,
                    )
                with top[1]:
                    enabled_now = bool(edits[name].get("enabled"))
                    new_en = st.toggle("Enabled", value=enabled_now, key=f"toggle_{name}")
                    edits[name]["enabled"] = new_en

                cc1, cc2 = st.columns(2)
                with cc1:
                    new_sched = st.text_input(
                        "Schedule", value=edits[name].get("schedule", ""),
                        key=f"sched_{name}",
                        help="Standard cron expression (`*/30 * * * 1-5`) or `launchd` for daemon-style.",
                    )
                    edits[name]["schedule"] = new_sched
                with cc2:
                    new_cmd = st.text_input(
                        "Command", value=edits[name].get("command", ""),
                        key=f"cmd_{name}",
                    )
                    edits[name]["command"] = new_cmd

        st.markdown("---")
        a1, a2, a3 = st.columns([1, 1, 2])
        with a1:
            if st.button("Save crons.yml", type="primary", use_container_width=True):
                # Preserve original ordering from crons list, with edits applied
                merged = []
                for c in crons:
                    merged.append({**c, **edits.get(c["name"], {})})
                settings_mod.write_crons(merged)
                st.toast("crons.yml saved")
        with a2:
            if st.button("Show current crontab", use_container_width=True):
                from vamos import cron_install as ci
                rendered = ci.render_crontab_block(ROOT)
                st.code(rendered, language="bash")
        with a3:
            st.caption(
                "After saving, run `vamos cron-install` from the terminal to apply. "
                "Streamlit can't modify your system crontab directly."
            )
