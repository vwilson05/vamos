"""End of day: final sync, generate EOD text via claude -p, post to Teams."""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from pathlib import Path

from .ado import ADOClient
from .config import Config
from .llm import call_claude, render_prompt
from .markdown_io import daily_path, parse_sections
from . import sync as sync_mod
from . import teams as teams_mod
from . import slack as slack_mod

log = logging.getLogger(__name__)


def run(
    cfg: Config,
    dry_run: bool = False,
    skip_sync: bool = False,
    skip_post: bool = False,
    skip_slack: bool = False,
    day: date | None = None,
) -> str:
    day = day or date.today()
    md_path = daily_path(cfg.work_dir, day)
    if not md_path.exists():
        raise SystemExit(f"No markdown for {day}: {md_path}")

    if not skip_sync:
        log.info("EOD: running final sync")
        sync_mod.run(cfg, dry_run=dry_run, day=day)

    markdown = md_path.read_text(encoding="utf-8")
    sections = parse_sections(markdown)
    referenced_ids = sorted({s.work_item_id for s in sections if s.work_item_id is not None})

    client = ADOClient(cfg.ado_org_url, cfg.ado_project, cfg.ado_pat, read_only=True)
    items = client.get_work_items(referenced_ids) if referenced_ids else []
    ado_state = [
        {
            "id": w.id,
            "type": w.type,
            "title": w.title,
            "state": w.state,
            "priority": w.priority,
            "tags": w.tags,
        }
        for w in items
    ]

    posted_comments = _collect_posted_comments(cfg.state_dir, day)

    # Format developer name with space prefix if it exists
    developer_name_formatted = f" {cfg.developer_name}" if cfg.developer_name else ""

    prompt = render_prompt(
        "eod.md",
        ado_state=json.dumps(ado_state, indent=2),
        posted_comments=json.dumps(posted_comments, indent=2),
        markdown=markdown,
        developer_name=developer_name_formatted,
        current_date=day.isoformat(),
    )

    log.info("EOD: invoking claude -p for summary (prompt %d chars)", len(prompt))
    eod_text = call_claude(prompt, claude_bin=cfg.claude_bin).strip()

    eod_path = cfg.state_dir / f"{day.isoformat()}-eod.txt"
    eod_path.write_text(eod_text + "\n", encoding="utf-8")
    log.info("EOD: wrote %s", eod_path)

    # Post to Teams or Slack based on CONNECTION_OPTION
    if cfg.connection_option == "Teams":
        if dry_run or skip_post:
            log.info("EOD: skipping Teams post (dry_run=%s skip_post=%s)", dry_run, skip_post)
        else:
            if not cfg.teams_webhook_url:
                log.warning("EOD: TEAMS_WEBHOOK_URL not set — skipping Teams post")
            else:
                teams_mod.post(cfg.teams_webhook_url, eod_text)
                log.info("EOD: posted to Teams")
    elif cfg.connection_option == "Slack":
        if dry_run or skip_slack:
            log.info("EOD: skipping Slack post (dry_run=%s skip_slack=%s)", dry_run, skip_slack)
        else:
            if not cfg.slack_webhook_url:
                log.info("EOD: SLACK_WEBHOOK_URL not set — skipping Slack post")
            else:
                try:
                    print(f"Using this slack webhook: {cfg.slack_webhook_url}")
                    slack_mod.post(cfg.slack_webhook_url, eod_text)
                    log.info("EOD: posted to Slack")
                except slack_mod.SlackError as e:
                    log.error("EOD: failed to post to Slack: %s", e)
    else:
        log.warning("EOD: Invalid CONNECTION_OPTION '%s' — must be 'Teams' or 'Slack'", cfg.connection_option)

    return eod_text


def _collect_posted_comments(state_dir: Path, day: date) -> list[dict]:
    """Walk today's sync logs to collect comments that were actually posted."""
    logs_dir = state_dir / "logs"
    if not logs_dir.exists():
        return []
    posted: list[dict] = []
    prefix = f"{day.isoformat()}-sync-"
    for log_file in sorted(logs_dir.glob(f"{prefix}*.json")):
        if log_file.name.endswith("-dry.json"):
            continue
        try:
            data = json.loads(log_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        for entry in data.get("results", []):
            action = entry.get("action", {})
            if action.get("op") != "add_comment":
                continue
            if entry.get("status") != "ok":
                continue
            posted.append(
                {
                    "id": action.get("id"),
                    "text": action.get("text"),
                }
            )
    return posted
