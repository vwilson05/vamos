"""Delivery — post a Report to Teams and/or Slack via existing adapters."""
from __future__ import annotations

import logging

from ..config import Config
from .. import slack as slack_mod
from .. import teams as teams_mod
from .report import Report

log = logging.getLogger(__name__)


def post_report(cfg: Config, report: Report, prefer: str | None = None) -> None:
    """Post the report's text form to whichever channel cfg selects.

    `prefer` overrides cfg.connection_option when set ("Teams" or "Slack").
    """
    text = report.to_markdown()
    target = prefer or cfg.connection_option
    if target == "Teams":
        if cfg.teams_webhook_url:
            teams_mod.post(cfg.teams_webhook_url, text)
            log.info("posted report to Teams")
        else:
            log.warning("TEAMS_WEBHOOK_URL not set — skipping Teams post")
    elif target == "Slack":
        if cfg.slack_webhook_url:
            try:
                slack_mod.post(cfg.slack_webhook_url, text)
                log.info("posted report to Slack")
            except Exception as exc:
                log.error("slack post failed: %s", exc)
        else:
            log.warning("SLACK_WEBHOOK_URL not set — skipping Slack post")
    else:
        log.warning("unknown delivery target: %s", target)
