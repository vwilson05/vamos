"""vamos UI entry point — boots NiceGUI/uvicorn.

`vamos ui` calls `run_app(port=...)` here. Pages register their routes via
`@ui.page` decorators on import.
"""
from __future__ import annotations

from nicegui import ui

# Importing this module registers every @ui.page route as a side effect.
from . import pages  # noqa: F401


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
