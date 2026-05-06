"""vamos UI entry point — boots NiceGUI/uvicorn.

`vamos ui` calls `run_app(port=...)` here. Pages register their routes via
`@ui.page` decorators on import.
"""
from __future__ import annotations

from nicegui import ui

# Importing this module registers every @ui.page route as a side effect.
from . import pages  # noqa: F401


# --- Dark-mode bridge ---------------------------------------------------------
# Mirrors Quasar's `body--dark` class onto the html element so Tailwind's
# `dark:` variants also fire (Tailwind looks for `<html class="dark">`).
_DARK_BRIDGE = """
<script>
(function() {
  // Color tokens for dark vs light. Adjust here if you want different shades.
  var DARK = {
    'q-card':           { bg: '#1e293b', fg: '#f1f5f9' },
    'nicegui-card':     { bg: '#1e293b', fg: '#f1f5f9' },
    'q-header':         { bg: '#0f172a', fg: '#f1f5f9' },
    'q-drawer':         { bg: '#0b1120', fg: '#e2e8f0' },
    'q-expansion-item': { bg: '#1e293b', fg: '#e2e8f0' },
    'q-dialog__inner':  { bg: '#1e293b', fg: '#f1f5f9' },
  };

  function applyForElement(el, isDark) {
    var cls = el.className || '';
    if (typeof cls !== 'string' && cls.baseVal) cls = cls.baseVal;
    var matched = null;
    for (var key in DARK) {
      if (cls.indexOf(key) !== -1) { matched = DARK[key]; break; }
    }
    if (!matched) return;
    if (isDark) {
      el.style.setProperty('background-color', matched.bg, 'important');
      el.style.setProperty('color', matched.fg, 'important');
    } else {
      el.style.removeProperty('background-color');
      el.style.removeProperty('color');
    }
  }

  function applyTheme() {
    if (!document.body) return;
    var isDark = document.body.classList.contains('body--dark');
    document.documentElement.classList.toggle('dark', !!isDark);

    var sel = '.q-card, .nicegui-card, .q-header, .q-drawer, .q-expansion-item, .q-dialog__inner';
    document.querySelectorAll(sel).forEach(function(el) { applyForElement(el, isDark); });
  }

  // Throttle for the mutation observer (Vue inserts elements rapidly on first render)
  var throttleTimer = null;
  function scheduleApply() {
    if (throttleTimer) return;
    throttleTimer = setTimeout(function() {
      throttleTimer = null;
      applyTheme();
    }, 50);
  }

  function start() {
    applyTheme();
    // Watch for Vue inserting new cards/headers/drawers
    var obs = new MutationObserver(scheduleApply);
    obs.observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ['class'] });
    // Expose so the dark toggle can trigger immediately
    window.__vamosApplyTheme = applyTheme;
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start);
  } else {
    start();
  }
})();
</script>
"""

ui.add_head_html(_DARK_BRIDGE, shared=True)


# --- Defeat Tailwind colors on Quasar widgets in dark mode -------------------
# The bug: Tailwind utility classes like `bg-white` on `<q-card>` win over
# Quasar's own dark theming because they're on the same element and Tailwind's
# specificity beats Quasar's `body--dark .q-card` cascade.
#
# Fix: when body--dark is on, force Quasar widgets to ignore Tailwind bg/text
# overrides and use Quasar-native dark colors. This works without us touching
# the existing class strings on every page.
_DARK_CSS = """
/* === Step 1: when body--dark is on, neutralize Tailwind backgrounds on
   Quasar widgets so Quasar's own theming can show through === */
.body--dark .q-card,
.body--dark .q-card.bg-white,
.body--dark .q-card.bg-slate-50,
.body--dark .q-card.bg-slate-100,
.body--dark .q-card.bg-stone-100 {
  background-color: #1e293b !important;
  color: #f1f5f9 !important;
}
.body--dark .q-header,
.body--dark .q-header.bg-white,
.body--dark .q-header.bg-slate-50 {
  background-color: #0f172a !important;
  color: #f1f5f9 !important;
}
.body--dark .q-drawer,
.body--dark .q-drawer.bg-stone-100,
.body--dark .q-drawer.bg-slate-50,
.body--dark .q-drawer.bg-slate-100 {
  background-color: #0b1120 !important;
  color: #e2e8f0 !important;
}
.body--dark .q-expansion-item,
.body--dark .q-expansion-item__container,
.body--dark .q-expansion-item.bg-white,
.body--dark .q-expansion-item.bg-slate-100 {
  background-color: #1e293b !important;
  color: #e2e8f0 !important;
}
.body--dark .q-tab-panels,
.body--dark .q-tab-panel,
.body--dark .q-tab-panel.bg-white {
  background-color: transparent !important;
}
.body--dark .q-dialog__inner > .q-card {
  background-color: #1e293b !important;
}

/* === Step 2: text colors on Quasar text classes === */
.body--dark .q-tab__label  { color: #94a3b8; }
.body--dark .q-tab--active .q-tab__label,
.body--dark .q-tab--active .q-tab__icon { color: #818cf8 !important; }
.body--dark .q-field__label,
.body--dark .q-field__bottom { color: #94a3b8 !important; }
.body--dark .q-field__native,
.body--dark .q-field__input { color: #f1f5f9 !important; }
.body--dark .q-toggle__label,
.body--dark .q-checkbox__label,
.body--dark .q-radio__label { color: #e2e8f0 !important; }

/* === Step 3: text-slate-* utility overrides on plain elements === */
.body--dark .text-slate-900 { color: #f1f5f9 !important; }
.body--dark .text-slate-800 { color: #e2e8f0 !important; }
.body--dark .text-slate-700 { color: #cbd5e1 !important; }
.body--dark .text-slate-600 { color: #cbd5e1 !important; }
.body--dark .text-slate-500 { color: #94a3b8 !important; }
.body--dark .text-slate-400 { color: #94a3b8 !important; }
.body--dark .text-slate-50  { color: #f1f5f9 !important; }

/* === Step 4: borders === */
.body--dark .border-slate-200 { border-color: #334155 !important; }
.body--dark .border-slate-100 { border-color: #1f2937 !important; }
.body--dark .border-slate-300 { border-color: #475569 !important; }

/* === Step 5: tinted accents (status pills + connection card) === */
.body--dark .bg-emerald-50      { background-color: rgba(16, 185, 129, 0.14) !important; }
.body--dark .bg-emerald-100     { background-color: rgba(16, 185, 129, 0.18) !important; }
.body--dark .border-emerald-200 { border-color: rgba(16, 185, 129, 0.5) !important; }
.body--dark .text-emerald-700   { color: #34d399 !important; }
.body--dark .text-emerald-600   { color: #34d399 !important; }
.body--dark .bg-rose-50         { background-color: rgba(244, 63, 94, 0.14) !important; }
.body--dark .border-rose-200    { border-color: rgba(244, 63, 94, 0.5) !important; }
.body--dark .text-rose-700      { color: #fda4af !important; }
.body--dark .bg-amber-50        { background-color: rgba(245, 158, 11, 0.14) !important; }
.body--dark .text-amber-700     { color: #fbbf24 !important; }
.body--dark .bg-indigo-50       { background-color: rgba(99, 102, 241, 0.16) !important; }
.body--dark .bg-indigo-100      { background-color: rgba(99, 102, 241, 0.20) !important; }
.body--dark .text-indigo-700    { color: #a5b4fc !important; }
.body--dark .text-indigo-600    { color: #a5b4fc !important; }

/* === Step 6: bare Tailwind backgrounds we want to flip to dark surface === */
.body--dark .bg-white,
.body--dark .bg-slate-50,
.body--dark .bg-slate-100,
.body--dark .bg-stone-100 {
  background-color: #1e293b !important;
}

/* === Step 7: markdown rendered output === */
.body--dark .prose,
.body--dark .prose * { color: #e2e8f0; }
.body--dark .prose h1,
.body--dark .prose h2,
.body--dark .prose h3,
.body--dark .prose h4,
.body--dark .prose strong { color: #f1f5f9 !important; }
.body--dark .prose code   { background-color: #0f172a; color: #fbbf24; }
.body--dark .prose pre    { background-color: #020617 !important; }
.body--dark .prose a      { color: #818cf8 !important; }
.body--dark .prose blockquote { border-color: #475569; color: #cbd5e1; }
.body--dark .prose table th { background-color: #0f172a; }
.body--dark .prose table th,
.body--dark .prose table td { border-color: #334155; }
"""

ui.add_head_html(f"<style>{_DARK_CSS}</style>", shared=True)


def run_app(port: int = 8501, host: str = "127.0.0.1", show_browser: bool = True) -> None:
    """Start the NiceGUI server. Foregrounded; Ctrl-C to stop."""
    ui.run(
        title="vamos",
        port=port,
        host=host,
        show=show_browser,           # auto-open default browser
        reload=False,                # production mode
        storage_secret="vamos-local-dev-secret",  # required for app.storage.user
        dark=None,                   # let user toggle; defaults to light
        favicon="🚀",                # browser tab favicon (single emoji is fine here)
        native=False,                # not running as a native window
    )
