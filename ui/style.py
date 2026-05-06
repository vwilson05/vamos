"""Shared styling for the vamos Streamlit UI.

- Light + dark themes via CSS custom properties
- React-style helper components built out of plain HTML+CSS (cards, pills, KPIs)
- No emojis in any default copy
"""
from __future__ import annotations

import json
from typing import Literal

import streamlit as st
import streamlit.components.v1 as components

# ---------------------------------------------------------------------------
# Color tokens
# ---------------------------------------------------------------------------

LIGHT = {
    "bg-app": "#FAFAFA",
    "bg-surface": "#FFFFFF",
    "bg-elevated": "#F8FAFC",
    "bg-input": "#FFFFFF",
    "border": "#E2E8F0",
    "border-hover": "#CBD5E1",
    "text-primary": "#0F172A",
    "text-secondary": "#475569",
    "text-muted": "#64748B",
    "accent": "#6366F1",
    "accent-hover": "#4F46E5",
    "accent-soft": "rgba(99, 102, 241, 0.08)",
    "accent-shadow": "rgba(99, 102, 241, 0.25)",
    "success-bg": "#ECFDF5",
    "success-border": "#A7F3D0",
    "success-fg": "#047857",
    "warn-bg": "#FFFBEB",
    "warn-fg": "#B45309",
    "danger-bg": "#FEF2F2",
    "danger-fg": "#B91C1C",
    "indigo-bg": "#EEF2FF",
    "indigo-fg": "#4338CA",
    "code-bg": "#0F172A",
    "code-fg": "#E2E8F0",
    "shadow-sm": "0 1px 2px rgba(15, 23, 42, 0.04)",
    "shadow-md": "0 4px 12px rgba(15, 23, 42, 0.08)",
}

DARK = {
    "bg-app": "#0B0F1A",
    "bg-surface": "#111827",
    "bg-elevated": "#1F2937",
    "bg-input": "#0F172A",
    "border": "#1F2937",
    "border-hover": "#374151",
    "text-primary": "#F1F5F9",
    "text-secondary": "#CBD5E1",
    "text-muted": "#94A3B8",
    "accent": "#818CF8",
    "accent-hover": "#6366F1",
    "accent-soft": "rgba(129, 140, 248, 0.14)",
    "accent-shadow": "rgba(129, 140, 248, 0.35)",
    "success-bg": "rgba(16, 185, 129, 0.12)",
    "success-border": "rgba(16, 185, 129, 0.4)",
    "success-fg": "#34D399",
    "warn-bg": "rgba(245, 158, 11, 0.12)",
    "warn-fg": "#FBBF24",
    "danger-bg": "rgba(239, 68, 68, 0.12)",
    "danger-fg": "#F87171",
    "indigo-bg": "rgba(99, 102, 241, 0.16)",
    "indigo-fg": "#A5B4FC",
    "code-bg": "#020617",
    "code-fg": "#E2E8F0",
    "shadow-sm": "0 1px 2px rgba(0, 0, 0, 0.4)",
    "shadow-md": "0 4px 12px rgba(0, 0, 0, 0.5)",
}


def _vars(tokens: dict[str, str]) -> str:
    return "\n".join(f"  --{k}: {v};" for k, v in tokens.items())


def _build_css(theme: str) -> str:
    tokens = DARK if theme == "dark" else LIGHT
    return f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

:root {{
{_vars(tokens)}
}}

html, body, [class*="css"] {{
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
  font-feature-settings: 'cv02','cv03','cv04','cv11';
}}
code, pre, .stCode, [data-testid="stCodeBlock"] {{
  font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace !important;
  font-size: 0.875rem !important;
}}

/* Hide chrome (but keep the sidebar collapse/expand control visible!) */
#MainMenu, footer, [data-testid="stDecoration"] {{ visibility: hidden; }}
[data-testid="stToolbar"] {{ visibility: hidden; pointer-events: none; }}
[data-testid="stHeader"] {{
  background: transparent !important;
  /* The collapsed-sidebar reveal arrow lives in the header — make sure it's reachable */
  pointer-events: auto !important;
}}
[data-testid="collapsedControl"],
[data-testid="stSidebarCollapsedControl"] {{
  visibility: visible !important;
  display: flex !important;
  pointer-events: auto !important;
  background: var(--bg-surface) !important;
  border: 1px solid var(--border) !important;
  border-radius: 6px !important;
  padding: 4px !important;
  z-index: 1000 !important;
  margin: 8px;
}}
[data-testid="collapsedControl"] svg,
[data-testid="stSidebarCollapsedControl"] svg {{
  color: var(--text-primary) !important;
  fill: var(--text-primary) !important;
}}
[data-testid="collapsedControl"]:hover,
[data-testid="stSidebarCollapsedControl"]:hover {{
  border-color: var(--accent) !important;
}}
[data-testid="collapsedControl"]:hover svg,
[data-testid="stSidebarCollapsedControl"]:hover svg {{
  color: var(--accent) !important;
  fill: var(--accent) !important;
}}

/* App + container */
.stApp, .main {{ background: var(--bg-app) !important; color: var(--text-primary) !important; }}
.main .block-container {{ padding-top: 2rem; padding-bottom: 4rem; max-width: 1200px; }}

/* Headings + body text */
h1, h2, h3, h4, h5, h6,
.stMarkdown h1, .stMarkdown h2, .stMarkdown h3, .stMarkdown h4 {{
  letter-spacing: -0.02em;
  font-weight: 700 !important;
  color: var(--text-primary) !important;
}}
h1, .stMarkdown h1 {{ font-size: 2rem !important; }}
h2, .stMarkdown h2 {{ font-size: 1.5rem !important; margin-top: 1.5rem !important; }}
h3, .stMarkdown h3 {{ font-size: 1.125rem !important; }}

.stMarkdown p, .stMarkdown li, .stMarkdown span, .stMarkdown strong, .stMarkdown em,
.stCaption, [data-testid="stCaptionContainer"] {{
  color: var(--text-primary) !important;
}}
.stMarkdown a {{ color: var(--accent) !important; }}
.stMarkdown table {{ border-color: var(--border) !important; }}
.stMarkdown th {{ background: var(--bg-elevated) !important; color: var(--text-primary) !important; }}
.stMarkdown td {{ color: var(--text-primary) !important; }}

/* Cards (st.container border=True) */
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"]) {{
  background: var(--bg-surface) !important;
  border: 1px solid var(--border) !important;
  border-radius: 12px !important;
  padding: 1rem 1.25rem !important;
  box-shadow: var(--shadow-sm);
}}

/* Buttons (default) — themed surface bg, primary text */
.stButton > button,
.stDownloadButton > button,
[data-testid="stFormSubmitButton"] > button {{
  border-radius: 8px !important;
  font-weight: 500 !important;
  font-size: 0.875rem !important;
  border: 1px solid var(--border) !important;
  background: var(--bg-surface) !important;
  background-color: var(--bg-surface) !important;
  color: var(--text-primary) !important;
  padding: 0.5rem 1rem !important;
  transition: all 0.15s ease;
  box-shadow: var(--shadow-sm);
}}
.stButton > button *,
.stDownloadButton > button *,
[data-testid="stFormSubmitButton"] > button * {{
  color: var(--text-primary) !important;
}}
.stButton > button:hover,
.stDownloadButton > button:hover,
[data-testid="stFormSubmitButton"] > button:hover {{
  border-color: var(--accent) !important;
  color: var(--accent) !important;
  transform: translateY(-1px);
  box-shadow: 0 2px 8px var(--accent-shadow);
}}
.stButton > button:hover *,
.stDownloadButton > button:hover *,
[data-testid="stFormSubmitButton"] > button:hover * {{
  color: var(--accent) !important;
}}

/* Primary buttons — indigo bg + white text in BOTH themes */
.stButton > button[kind="primary"],
.stDownloadButton > button[kind="primary"],
[data-testid="stFormSubmitButton"] > button[kind="primary"] {{
  background: var(--accent) !important;
  background-color: var(--accent) !important;
  border-color: var(--accent) !important;
  color: #FFFFFF !important;
}}
.stButton > button[kind="primary"] *,
.stDownloadButton > button[kind="primary"] *,
[data-testid="stFormSubmitButton"] > button[kind="primary"] * {{
  color: #FFFFFF !important;
}}
.stButton > button[kind="primary"]:hover,
.stDownloadButton > button[kind="primary"]:hover,
[data-testid="stFormSubmitButton"] > button[kind="primary"]:hover {{
  background: var(--accent-hover) !important;
  background-color: var(--accent-hover) !important;
  border-color: var(--accent-hover) !important;
  color: #FFFFFF !important;
  box-shadow: 0 4px 12px var(--accent-shadow);
}}
.stButton > button[kind="primary"]:hover * {{ color: #FFFFFF !important; }}

/* Disabled buttons */
.stButton > button:disabled,
.stDownloadButton > button:disabled {{
  opacity: 0.5;
  cursor: not-allowed;
  color: var(--text-muted) !important;
}}
.stButton > button:disabled * {{ color: var(--text-muted) !important; }}

/* Number-input +/- step buttons (used by st.number_input) */
[data-testid="stNumberInput"] button,
[data-baseweb="input-spinner"] button {{
  background: var(--bg-elevated) !important;
  background-color: var(--bg-elevated) !important;
  color: var(--text-primary) !important;
  border-color: var(--border) !important;
}}
[data-testid="stNumberInput"] button:hover {{
  background: var(--accent-soft) !important;
  color: var(--accent) !important;
}}

/* Selectbox dropdown panel + options */
[data-baseweb="popover"], [data-baseweb="menu"], [role="listbox"] {{
  background: var(--bg-surface) !important;
  background-color: var(--bg-surface) !important;
  border-color: var(--border) !important;
}}
[role="option"], [data-baseweb="menu"] li {{
  background: var(--bg-surface) !important;
  background-color: var(--bg-surface) !important;
  color: var(--text-primary) !important;
}}
[role="option"]:hover,
[role="option"][aria-selected="true"],
[data-baseweb="menu"] li:hover {{
  background: var(--accent-soft) !important;
  background-color: var(--accent-soft) !important;
  color: var(--accent) !important;
}}

/* Radio (used by theme toggle + format radio) */
.stRadio [role="radiogroup"] {{
  background: transparent !important;
}}
.stRadio label, .stRadio label > div {{
  color: var(--text-primary) !important;
}}
[data-baseweb="radio"] [data-checked="true"] {{
  border-color: var(--accent) !important;
}}

/* Checkbox */
[data-baseweb="checkbox"] [data-checked="true"] {{
  background: var(--accent) !important;
  border-color: var(--accent) !important;
}}
[data-baseweb="checkbox"] svg {{
  fill: #FFFFFF !important;
  color: #FFFFFF !important;
}}

/* Expander header */
[data-testid="stExpander"] details summary,
[data-testid="stExpander"] details summary * {{
  background: var(--bg-surface) !important;
  color: var(--text-primary) !important;
}}
[data-testid="stExpander"] details summary:hover {{
  color: var(--accent) !important;
}}

/* Toast (st.toast) */
[data-testid="stToast"], [data-testid="stToast"] * {{
  background: var(--bg-surface) !important;
  color: var(--text-primary) !important;
  border-color: var(--border) !important;
}}

/* File uploader / camera input button */
[data-testid="stFileUploader"] button,
[data-testid="stCameraInput"] button {{
  background: var(--bg-surface) !important;
  color: var(--text-primary) !important;
  border-color: var(--border) !important;
}}

/* --- Dark-mode catch-all for any button-like element we haven't targeted ---
   Streamlit's underlying theme is light (per config.toml base="light"), so
   widgets we don't explicitly style fall through to the light defaults — which
   in dark mode means white text on white bg. This block forces every button
   inside .stApp to themed colors unless it's a primary or a tab. */
.stApp button:not([kind="primary"]):not([data-baseweb="tab"]):not([data-testid="StyledFullScreenButton"]),
.stApp [role="button"]:not([kind="primary"]):not([data-baseweb="tab"]),
.stApp [data-baseweb="button"]:not([kind="primary"]) {{
  background-color: var(--bg-surface) !important;
  color: var(--text-primary) !important;
  border-color: var(--border) !important;
}}
.stApp button:not([kind="primary"]):not([data-baseweb="tab"]) *:not(svg):not(path),
.stApp [role="button"]:not([kind="primary"]):not([data-baseweb="tab"]) *:not(svg):not(path) {{
  color: var(--text-primary) !important;
}}
.stApp button[kind="primary"],
.stApp button[kind="primary"] * {{
  background-color: var(--accent) !important;
  color: #FFFFFF !important;
}}
.stApp button[kind="primary"]:hover {{
  background-color: var(--accent-hover) !important;
}}
.stApp button:disabled, .stApp [role="button"][aria-disabled="true"] {{
  opacity: 0.55 !important;
  color: var(--text-muted) !important;
}}

/* Inputs (text, textarea, number, select) */
.stTextInput > div > div, .stTextArea > div > div,
.stNumberInput > div > div, .stSelectbox > div > div,
[data-baseweb="input"], [data-baseweb="textarea"], [data-baseweb="select"] {{
  border-radius: 8px !important;
  border-color: var(--border) !important;
  background: var(--bg-input) !important;
}}
.stTextInput input, .stTextArea textarea, .stNumberInput input,
[data-baseweb="input"] input, [data-baseweb="textarea"] textarea {{
  background: var(--bg-input) !important;
  color: var(--text-primary) !important;
}}
.stTextInput input:focus, .stTextArea textarea:focus, .stNumberInput input:focus {{
  border-color: var(--accent) !important;
  box-shadow: 0 0 0 3px var(--accent-soft) !important;
}}
input::placeholder, textarea::placeholder {{ color: var(--text-muted) !important; }}

label, .stTextInput label, .stTextArea label, .stSelectbox label, .stNumberInput label,
.stCheckbox label, .stRadio label {{
  color: var(--text-secondary) !important;
}}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {{
  gap: 4px;
  border-bottom: 1px solid var(--border);
  background: transparent !important;
}}
.stTabs [data-baseweb="tab"] {{
  border-radius: 8px 8px 0 0;
  padding: 8px 16px;
  font-weight: 500;
  color: var(--text-muted) !important;
  background: transparent !important;
}}
.stTabs [aria-selected="true"] {{
  color: var(--accent) !important;
  background: var(--accent-soft) !important;
}}

/* Sidebar */
[data-testid="stSidebar"] {{
  background: var(--bg-surface) !important;
  border-right: 1px solid var(--border);
}}
[data-testid="stSidebar"] * {{ color: var(--text-primary); }}
[data-testid="stSidebar"] .stMarkdown {{ padding: 0 0.5rem; }}

/* Alerts */
[data-testid="stAlert"] {{ border-radius: 10px !important; background: var(--bg-elevated) !important; }}
[data-testid="stAlert"] * {{ color: var(--text-primary) !important; }}

/* Code blocks */
[data-testid="stCodeBlock"] pre {{
  background: var(--code-bg) !important;
  border-radius: 10px !important;
  padding: 1rem !important;
}}
[data-testid="stCodeBlock"] code {{ color: var(--code-fg) !important; }}

/* Dataframes */
[data-testid="stDataFrame"] {{
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid var(--border);
  background: var(--bg-surface);
}}

/* Checkbox + radio */
.stCheckbox label > div, .stRadio label > div {{ color: var(--text-primary) !important; }}

/* Toast */
[data-testid="stToast"] {{ background: var(--bg-surface) !important; color: var(--text-primary) !important; }}

/* Scrollbars */
::-webkit-scrollbar {{ width: 10px; height: 10px; }}
::-webkit-scrollbar-thumb {{ background: var(--border-hover); border-radius: 6px; }}
::-webkit-scrollbar-thumb:hover {{ background: var(--text-muted); }}

/* Spinner */
.stSpinner > div {{ border-color: var(--accent) transparent var(--accent) transparent !important; }}
</style>
"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def current_theme() -> str:
    return st.session_state.get("vamos_theme", "light")


def apply() -> None:
    """Inject themed CSS. Call once at the top of every page (after set_page_config)."""
    theme = current_theme()
    st.markdown(_build_css(theme), unsafe_allow_html=True)


def theme_toggle_in_sidebar() -> None:
    """Render a Light / Dark segmented control in the sidebar."""
    current = current_theme()
    choice = st.sidebar.radio(
        "Theme",
        options=["Light", "Dark"],
        horizontal=True,
        index=0 if current == "light" else 1,
        label_visibility="visible",
        key="vamos_theme_radio",
    )
    new = "dark" if choice == "Dark" else "light"
    if new != current:
        st.session_state["vamos_theme"] = new
        st.rerun()


# ---------------------------------------------------------------------------
# Component helpers (HTML, theme-aware via CSS vars)
# ---------------------------------------------------------------------------

_PILL_TONES = {
    "indigo": ("var(--indigo-bg)", "var(--indigo-fg)"),
    "green": ("var(--success-bg)", "var(--success-fg)"),
    "amber": ("var(--warn-bg)", "var(--warn-fg)"),
    "red": ("var(--danger-bg)", "var(--danger-fg)"),
    "slate": ("var(--bg-elevated)", "var(--text-secondary)"),
}


def pill(text: str, tone: Literal["indigo", "green", "amber", "red", "slate"] = "slate") -> str:
    bg, fg = _PILL_TONES[tone]
    return (
        f'<span style="display:inline-block; padding:2px 10px; border-radius:999px; '
        f'background:{bg}; color:{fg}; font-size:0.75rem; font-weight:600; '
        f'letter-spacing:0.02em; line-height:1.4;">{text}</span>'
    )


def kpi(label: str, value: str, tone: str = "slate") -> str:
    color_map = {
        "indigo": "var(--accent)",
        "green": "var(--success-fg)",
        "amber": "var(--warn-fg)",
        "red": "var(--danger-fg)",
        "slate": "var(--text-primary)",
    }
    color = color_map.get(tone, "var(--text-primary)")
    return f"""
<div style="background:var(--bg-surface); border:1px solid var(--border); border-radius:12px;
            padding:1rem 1.25rem; box-shadow:var(--shadow-sm);">
  <div style="color:var(--text-muted); font-size:0.75rem; font-weight:600;
              text-transform:uppercase; letter-spacing:0.05em;">{label}</div>
  <div style="color:{color}; font-size:1.875rem; font-weight:700;
              margin-top:0.25rem; line-height:1.1;">{value}</div>
</div>
"""


def section_header(title: str, subtitle: str | None = None) -> None:
    sub = (
        f'<div style="color:var(--text-muted); font-size:0.875rem; margin-top:0.25rem;">{subtitle}</div>'
        if subtitle else ""
    )
    st.markdown(
        f'<div style="margin-bottom:1rem;">'
        f'<div style="font-size:1.5rem; font-weight:700; letter-spacing:-0.02em; '
        f'color:var(--text-primary);">{title}</div>{sub}</div>',
        unsafe_allow_html=True,
    )


def empty_state(title: str, body: str) -> None:
    st.markdown(
        f"""
<div style="text-align:center; padding:3rem 1rem; background:var(--bg-surface);
            border:1px dashed var(--border-hover); border-radius:12px;
            color:var(--text-muted);">
  <div style="font-size:1.125rem; font-weight:600; color:var(--text-primary);">{title}</div>
  <div style="font-size:0.875rem; margin-top:0.25rem;">{body}</div>
</div>
""",
        unsafe_allow_html=True,
    )


def label(text: str) -> None:
    """Small uppercase section label (style for KPI rows / form sections)."""
    st.markdown(
        f'<div style="color:var(--text-muted); font-size:0.75rem; font-weight:600; '
        f'text-transform:uppercase; letter-spacing:0.05em; margin-bottom:0.5rem;">{text}</div>',
        unsafe_allow_html=True,
    )


def copy_button(text: str, button_label: str = "Copy to clipboard", height: int = 60) -> None:
    """A real one-click clipboard button via components.html iframe."""
    payload = json.dumps(text)
    bg = "#6366F1" if current_theme() == "light" else "#818CF8"
    bg_active = "#10B981"
    html = f"""
<div style="font-family:'Inter',sans-serif;">
  <button id="vamos-copy-btn"
          onclick='
            navigator.clipboard.writeText({payload}).then(() => {{
              const b = document.getElementById("vamos-copy-btn");
              b.innerText = "Copied";
              b.style.background = "{bg_active}";
              b.style.borderColor = "{bg_active}";
              setTimeout(() => {{
                b.innerText = "{button_label}";
                b.style.background = "{bg}";
                b.style.borderColor = "{bg}";
              }}, 1500);
            }});
          '
          style="background:{bg}; color:white; border:1px solid {bg};
                 padding:0.5rem 1rem; border-radius:8px; font-size:0.875rem;
                 font-weight:500; cursor:pointer; transition:all 0.15s;
                 box-shadow:0 2px 8px rgba(99,102,241,0.25);">
    {button_label}
  </button>
</div>
"""
    components.html(html, height=height)


def get_cfg(profile_arg=None, board: str | None = None):
    """Always reload cfg from .env, then apply optional --board override.

    `board` is a name from .ado-metrics.yml or `boards.ALL_BOARDS`. When set,
    cfg's healthcheck/hygiene area + iteration paths are overridden so every
    team agent on the page picks up the new scope.
    """
    from vamos import config as config_mod
    from vamos.core import boards as boards_mod

    cfg = config_mod.load(profile=profile_arg)
    if board:
        areas, iters = boards_mod.resolve(board)
        if areas:
            area_val = areas[0] if len(areas) == 1 else areas
            iter_val = (iters[0] if len(iters) == 1 else iters) if iters else None
            cfg.healthcheck_area_path = area_val
            cfg.healthcheck_iteration_path = iter_val
            cfg.hygiene_area_path = area_val
            cfg.hygiene_iteration_path = iter_val
    return cfg


def board_picker_in_sidebar() -> str | None:
    """Render the global board picker. Returns the selected board name (or None)."""
    from vamos.core import boards as boards_mod
    names = boards_mod.board_names(include_all=True)
    if not names:
        return None
    default_name = boards_mod.default_board_name()
    options = ["(use .env paths)", *names]
    # Pick a reasonable default: ALL on first load
    current = st.session_state.get("vamos_board") or boards_mod.ALL_BOARDS
    try:
        idx = options.index(current)
    except ValueError:
        idx = 1 if len(options) > 1 else 0
    choice = st.sidebar.selectbox("Board", options=options, index=idx,
                                  help="Scope for team agents (healthcheck, hygiene, at-risk, brief, customers).")
    selected: str | None
    if choice == "(use .env paths)":
        selected = None
    else:
        selected = choice
    if selected != st.session_state.get("vamos_board"):
        st.session_state["vamos_board"] = selected
    return selected


# ---------------------------------------------------------------------------
# Streaming log capture for long-running agent calls
# ---------------------------------------------------------------------------


def run_with_streaming_logs(label: str, fn, *args, log_namespace: str = "vamos",
                            level: str = "INFO", expanded_after: bool = False, **kwargs):
    """Run `fn(*args, **kwargs)` while streaming its log output into a Streamlit
    status block. Captures every record from the given log namespace and shows
    them as they arrive (running in a daemon thread; main loop drains a queue).

    Returns whatever `fn` returns. Re-raises any exception `fn` raised, after
    marking the status block as "failed".
    """
    import logging
    import queue
    import threading
    import time

    log_queue: queue.Queue = queue.Queue()
    result_box: dict = {}

    class QueueHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            try:
                ts = time.strftime("%H:%M:%S", time.localtime(record.created))
                msg = f"{ts}  {record.levelname[:4]:>4}  {record.getMessage()}"
                log_queue.put(msg)
            except Exception:
                pass

    handler = QueueHandler()
    target_logger = logging.getLogger(log_namespace)
    prev_level = target_logger.level
    handler.setLevel(getattr(logging, level, logging.INFO))
    target_logger.addHandler(handler)
    target_logger.setLevel(getattr(logging, level, logging.INFO))

    def worker() -> None:
        try:
            result_box["value"] = fn(*args, **kwargs)
        except Exception as exc:
            result_box["error"] = exc
        finally:
            log_queue.put(None)

    thread = threading.Thread(target=worker, daemon=True)

    with st.status(label, expanded=True) as status:
        placeholder = st.empty()
        thread.start()
        lines: list[str] = []
        try:
            while True:
                try:
                    msg = log_queue.get(timeout=0.3)
                except queue.Empty:
                    continue
                if msg is None:
                    break
                lines.append(msg)
                # Last 50 lines, monospace, code-block style
                placeholder.code("\n".join(lines[-50:]), language=None)
            thread.join(timeout=2)
        finally:
            target_logger.removeHandler(handler)
            target_logger.setLevel(prev_level)

        if "error" in result_box:
            status.update(label=f"{label} — failed", state="error", expanded=True)
            raise result_box["error"]
        status.update(
            label=f"{label} — done ({len(lines)} log line(s))",
            state="complete",
            expanded=expanded_after,
        )

    return result_box.get("value")
