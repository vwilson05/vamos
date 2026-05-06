"""Settings — read/write .env files and crons.yml from the UI.

Goals:
- Preserve comments + line ordering in .env files (don't blast them with a dump)
- Distinguish secret vs non-secret fields so the UI can mask them
- Validate enough to catch obvious typos (URLs, integer fields)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Literal

from .config import ROOT, PROFILE_FILES

# Fields treated as secrets — masked by default in the UI, written write-only.
SECRET_KEYS = {
    "ADO_PAT",
    "TEAMS_WEBHOOK_URL",
    "SLACK_WEBHOOK_URL",
    "DATA_INGESTION_TEAMS_CHANNEL_WEBHOOK",
    "TEST_TEAMS_CHANNEL_WEBHOOK",
}


@dataclass
class FieldDef:
    key: str
    label: str
    section: str
    kind: Literal["text", "secret", "bool", "int", "url", "select", "time"] = "text"
    placeholder: str = ""
    options: list[str] = field(default_factory=list)
    help: str = ""
    required: bool = False


# Schema — every editable field, grouped by section.
SCHEMA: list[FieldDef] = [
    # --- ADO connection ---
    FieldDef("ADO_ORG_URL", "ADO org URL", "ADO connection", kind="url",
             placeholder="https://dev.azure.com/HaloMDLLC", required=True,
             help="No trailing slash."),
    FieldDef("ADO_PROJECT", "Project", "ADO connection",
             placeholder="Data Platform", required=True),
    FieldDef("ADO_PAT", "Personal Access Token", "ADO connection", kind="secret",
             required=True,
             help="Work Items R/W; for pr-review also needs Code R/W + PR Threads R/W."),
    FieldDef("ADO_USER_EMAIL", "Email override (blank = @Me)", "ADO connection",
             placeholder="you@halomd.com"),
    FieldDef("ADO_READ_ONLY", "Read-only mode (block writes)", "ADO connection", kind="bool"),

    # --- Channels ---
    FieldDef("CONNECTION_OPTION", "Default channel", "Channels", kind="select",
             options=["Teams", "Slack"]),
    FieldDef("TEAMS_WEBHOOK_URL", "Teams webhook URL", "Channels", kind="secret"),
    FieldDef("SLACK_WEBHOOK_URL", "Slack webhook URL", "Channels", kind="secret"),
    FieldDef("DEVELOPER_NAME", "Your name (used in EOD posts)", "Channels"),

    # --- Daily flow ---
    FieldDef("RUN_SOD_AT", "SOD time (HH:MM)", "Daily flow", kind="time",
             placeholder="08:00"),
    FieldDef("RUN_EOD_AT", "EOD time (HH:MM)", "Daily flow", kind="time",
             placeholder="18:00"),
    FieldDef("RUN_SYNC_INTERVAL_MIN", "Sync interval (minutes)", "Daily flow", kind="int"),
    FieldDef("RUN_SKIP_WEEKENDS", "Skip weekends", "Daily flow", kind="bool"),
    FieldDef("SOD_CLEANUP_ENABLED", "SOD cleans previous days' files", "Daily flow", kind="bool"),

    # --- Team agent paths ---
    FieldDef("HEALTHCHECK_AREA_PATH", "Healthcheck area path", "Team agents",
             placeholder="Data Platform\\Engineering"),
    FieldDef("HEALTHCHECK_ITERATION_PATH", "Healthcheck iteration path", "Team agents"),
    FieldDef("HYGIENE_AREA_PATH", "Hygiene area path (blank = use Healthcheck)", "Team agents"),
    FieldDef("HYGIENE_ITERATION_PATH", "Hygiene iteration path", "Team agents"),
    FieldDef("HYGIENE_REPOS", "Hygiene repos (blank = all repos in project)", "Team agents",
             help="Comma-separated. Limit hygiene's PR/branch checks to these repos."),
    FieldDef("HYGIENE_LIVE_MODE", "Hygiene live mode (allow auto-comment / clean)",
             "Team agents", kind="bool",
             help="Required for hygiene to post nudge comments or apply clean actions."),
    FieldDef("HYGIENE_DAILY_COMMENT_DEADLINE", "Daily-comment deadline", "Team agents",
             kind="time", placeholder="17:00"),
    FieldDef("HYGIENE_STALE_BLOCKED_DAYS", "Stale-blocked threshold (days)", "Team agents",
             kind="int"),
    FieldDef("HYGIENE_BRANCH_PATTERN", "Valid branch-name regex", "Team agents"),

    # --- PR review ---
    FieldDef("VAMOS_PR_REVIEW_INTERVAL", "PR-review --watch poll interval (sec)", "PR review",
             kind="int"),

    # --- Profile ---
    FieldDef("VAMOS_PROFILE", "Default profile", "Profile", kind="select",
             options=["", "personal", "team"]),
    FieldDef("VAMOS_AUTO_PREP", "Auto-prep on UI launch (SOD + inbox + standup)",
             "Profile", kind="bool",
             help="When true, ./launch.sh runs `vamos prep` before opening the UI "
                  "so My day shows your standup + inbox immediately."),

    # --- Misc ---
    FieldDef("CLAUDE_BIN", "Claude CLI binary", "Misc", placeholder="claude"),
    FieldDef("WORK_DIR", "Markdown work dir (blank = ./work)", "Misc"),
    FieldDef("STATE_DIR", "State dir (blank = ./state)", "Misc"),
]


def schema_by_section() -> dict[str, list[FieldDef]]:
    out: dict[str, list[FieldDef]] = {}
    for fd in SCHEMA:
        out.setdefault(fd.section, []).append(fd)
    return out


# ---------------------------------------------------------------------------
# .env file r/w
# ---------------------------------------------------------------------------


_ENV_LINE_RE = re.compile(r"^\s*([A-Z_][A-Z0-9_]*)\s*=\s*(.*)$")


def env_path(profile: str | None = None) -> Path:
    """Return the path of the env file to edit. profile None → .env, else .env.<profile>."""
    if profile and profile in PROFILE_FILES:
        return ROOT / PROFILE_FILES[profile]
    return ROOT / ".env"


def read_env(path: Path) -> dict[str, str]:
    """Parse an .env file, returning {KEY: value}. Missing file → {}."""
    if not path.exists():
        return {}
    out: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = _ENV_LINE_RE.match(line)
        if not m:
            continue
        key, val = m.group(1), m.group(2)
        # Strip optional surrounding quotes
        if len(val) >= 2 and val[0] in ('"', "'") and val[-1] == val[0]:
            val = val[1:-1]
        out[key] = val
    return out


def write_env(path: Path, updates: dict[str, str]) -> None:
    """Write updated values back to `path`, preserving comments + ordering.

    - Existing keys are updated in place.
    - New keys (not yet present in the file) are appended at the end.
    - Empty values are written as `KEY=` (rather than removing the line).
    - Lines that look like comments or blank are passed through unchanged.
    - Values are written quoted only if they contain whitespace or special chars.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    existing_lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    seen_keys: set[str] = set()
    out_lines: list[str] = []
    for raw in existing_lines:
        m = _ENV_LINE_RE.match(raw)
        if not m:
            out_lines.append(raw)
            continue
        key = m.group(1)
        if key in updates:
            out_lines.append(_render_line(key, updates[key]))
            seen_keys.add(key)
        else:
            out_lines.append(raw)
    # Append new keys we didn't see
    for key, val in updates.items():
        if key in seen_keys:
            continue
        out_lines.append(_render_line(key, val))
    # Ensure trailing newline
    text = "\n".join(out_lines)
    if not text.endswith("\n"):
        text += "\n"
    path.write_text(text, encoding="utf-8")


def _render_line(key: str, value: str) -> str:
    if value == "":
        return f"{key}="
    needs_quote = any(c.isspace() for c in value) or any(c in value for c in '#"\'\\')
    if needs_quote:
        # Escape any double-quote in the value
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'{key}="{escaped}"'
    return f"{key}={value}"


# ---------------------------------------------------------------------------
# crons.yml r/w
# ---------------------------------------------------------------------------


def crons_path() -> Path:
    return ROOT / "crons.yml"


def crons_example_path() -> Path:
    return ROOT / "crons.yml.example"


def read_crons() -> list[dict]:
    """Read crons.yml; if missing, fall back to crons.yml.example contents."""
    import yaml
    path = crons_path()
    if not path.exists() and crons_example_path().exists():
        path = crons_example_path()
    if not path.exists():
        return []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return []
    return data.get("crons", []) or []


def write_crons(crons: Iterable[dict]) -> None:
    import yaml
    path = crons_path()
    path.write_text(
        "# vamos cron schedule (managed by Settings UI).\n"
        "# Re-run `vamos cron-install` after toggling entries.\n\n"
        + yaml.safe_dump({"crons": list(crons)}, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )


def mask_secret(value: str, show_chars: int = 4) -> str:
    """Mask a secret for display, showing only the last `show_chars` chars."""
    if not value:
        return ""
    if len(value) <= show_chars:
        return "•" * len(value)
    return "•" * (len(value) - show_chars) + value[-show_chars:]


def is_secret(key: str) -> bool:
    return key in SECRET_KEYS or any(s in key for s in ("PAT", "TOKEN", "WEBHOOK", "SECRET"))
