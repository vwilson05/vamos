"""Configuration loaded from .env (or profile-specific .env files)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent

# Profile loading: each profile maps to a .env file at the repo root.
# Phase 0 wires the plumbing; later phases will populate profile-specific files.
PROFILE_FILES = {
    "personal": ".env.personal",
    "team": ".env.team",
}


@dataclass
class Config:
    ado_org_url: str
    ado_project: str
    ado_pat: str
    ado_user_email: str
    ado_read_only: bool
    connection_option: str  # "Teams" or "Slack"
    teams_webhook_url: str
    slack_webhook_url: str | None
    developer_name: str | None
    claude_bin: str
    work_dir: Path
    state_dir: Path
    healthcheck_area_path: str | None
    healthcheck_iteration_path: str | None
    sod_cleanup_enabled: bool  # Enable cleanup of previous days' files on SOD
    # --- hygiene ---
    hygiene_area_path: str | None
    hygiene_iteration_path: str | None
    hygiene_repos: list[str]  # ADO repo names to scan for PRs/branches
    hygiene_live_mode: bool  # if true, hygiene may post comments on offending tickets
    hygiene_daily_comment_deadline: str  # HH:MM local time; tickets need a comment by this time
    hygiene_stale_blocked_days: int  # blocked > N days w/ no comment = finding
    hygiene_branch_pattern: str  # regex for valid PR source branches

    @property
    def assigned_user_clause(self) -> str:
        if self.ado_user_email:
            safe = self.ado_user_email.replace("'", "''")
            return f"'{safe}'"
        return "@Me"


def load(env_path: Path | None = None, profile: str | None = None) -> Config:
    """Load config.

    Profile resolution order:
      1. Explicit `profile` arg (from --profile flag)
      2. VAMOS_PROFILE env var
      3. None — falls through to plain .env (current behavior, back-compat)

    When a profile is selected, .env loads first (shared baseline), then the
    profile file (e.g. .env.personal or .env.team) overlays so its keys win.
    Missing profile files are not an error — they're optional in Phase 0.
    """
    if env_path is None:
        env_path = ROOT / ".env"
    if env_path.exists():
        load_dotenv(env_path)

    profile = profile or os.getenv("VAMOS_PROFILE", "").strip() or None
    if profile:
        if profile not in PROFILE_FILES:
            raise SystemExit(f"Unknown profile {profile!r}. Choose from: {', '.join(PROFILE_FILES)}.")
        profile_path = ROOT / PROFILE_FILES[profile]
        if profile_path.exists():
            load_dotenv(profile_path, override=True)

    org = _required("ADO_ORG_URL")
    project = _required("ADO_PROJECT")
    pat = _required("ADO_PAT")

    work_dir = Path(os.getenv("WORK_DIR") or (ROOT / "work")).expanduser().resolve()
    state_dir = Path(os.getenv("STATE_DIR") or (ROOT / "state")).expanduser().resolve()
    work_dir.mkdir(parents=True, exist_ok=True)
    state_dir.mkdir(parents=True, exist_ok=True)

    # Get connection option, default to "Teams" if not specified
    connection_option = os.getenv("CONNECTION_OPTION", "Teams").strip()
    if connection_option not in ("Teams", "Slack"):
        raise SystemExit(
            f"Invalid CONNECTION_OPTION '{connection_option}'. Must be 'Teams' or 'Slack'."
        )

    # Default healthcheck paths to Data Platform board
    healthcheck_area = os.getenv("HEALTHCHECK_AREA_PATH", "Data Platform\\Engineering").strip() or None
    healthcheck_iteration = os.getenv("HEALTHCHECK_ITERATION_PATH", "Data Platform\\Ingestion Engineering Kanban").strip() or None

    # Hygiene defaults — fall back to healthcheck paths if not set
    hygiene_area = os.getenv("HYGIENE_AREA_PATH", "").strip() or healthcheck_area
    hygiene_iteration = os.getenv("HYGIENE_ITERATION_PATH", "").strip() or healthcheck_iteration
    hygiene_repos_raw = os.getenv("HYGIENE_REPOS", "").strip()
    hygiene_repos = [r.strip() for r in hygiene_repos_raw.split(",") if r.strip()] if hygiene_repos_raw else []
    hygiene_live = os.getenv("HYGIENE_LIVE_MODE", "").strip().lower() in ("1", "true", "yes")
    hygiene_deadline = os.getenv("HYGIENE_DAILY_COMMENT_DEADLINE", "17:00").strip()
    hygiene_stale_days = int(os.getenv("HYGIENE_STALE_BLOCKED_DAYS", "5"))
    hygiene_branch_re = os.getenv(
        "HYGIENE_BRANCH_PATTERN",
        r"^(feature|bugfix|hotfix)/\d+-[a-z0-9-]+$",
    ).strip()

    return Config(
        ado_org_url=org,
        ado_project=project,
        ado_pat=pat,
        ado_user_email=os.getenv("ADO_USER_EMAIL", "").strip(),
        ado_read_only=os.getenv("ADO_READ_ONLY", "").strip().lower() in ("1", "true", "yes"),
        connection_option=connection_option,
        teams_webhook_url=os.getenv("TEAMS_WEBHOOK_URL", "").strip(),
        slack_webhook_url=os.getenv("SLACK_WEBHOOK_URL", "").strip() or None,
        developer_name=os.getenv("DEVELOPER_NAME", "").strip() or None,
        claude_bin=os.getenv("CLAUDE_BIN", "claude").strip() or "claude",
        work_dir=work_dir,
        state_dir=state_dir,
        healthcheck_area_path=healthcheck_area,
        healthcheck_iteration_path=healthcheck_iteration,
        sod_cleanup_enabled=os.getenv("SOD_CLEANUP_ENABLED", "true").strip().lower() in ("1", "true", "yes"),
        hygiene_area_path=hygiene_area,
        hygiene_iteration_path=hygiene_iteration,
        hygiene_repos=hygiene_repos,
        hygiene_live_mode=hygiene_live,
        hygiene_daily_comment_deadline=hygiene_deadline,
        hygiene_stale_blocked_days=hygiene_stale_days,
        hygiene_branch_pattern=hygiene_branch_re,
    )


def _required(key: str) -> str:
    val = os.getenv(key, "").strip()
    if not val:
        raise SystemExit(
            f"Missing required env var {key}. Copy .env.example to .env and fill it in."
        )
    return val
