"""Success-story posting to Slack.

Auto-fires from a small set of "major actions" (start_work, open_pr,
close_ticket, vote_on_pr, run_pr_review-posted) so usage is visible to
the broader org. Plus a manual `share_success_story` MCP tool for ad-hoc
shout-outs.

Env knobs:
  VAMOS_SUCCESS_STORIES        on|off  (default: on)
  VAMOS_SUCCESS_WEBHOOK_URL    Slack incoming webhook for the share channel
                               (e.g. halo-nation). NO fallback — must be set
                               or shouting is silently skipped.

Identity comes from cfg.developer_name → cfg.ado_user_email → "someone".

Failures never raise — share posts are best-effort. We don't want a Slack
hiccup to fail an otherwise-successful close_ticket or vote_on_pr.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from .. import slack as slack_mod
from ..config import Config

log = logging.getLogger(__name__)

# Tag appended to every auto-fired message so readers know it's vamos-driven.
TAG = "_via vamos_"


def is_enabled() -> bool:
    return os.getenv("VAMOS_SUCCESS_STORIES", "true").strip().lower() in ("1", "true", "yes")


def webhook_url() -> str | None:
    return os.getenv("VAMOS_SUCCESS_WEBHOOK_URL", "").strip() or None


def actor(cfg: Config) -> str:
    return (cfg.developer_name or "").strip() or (cfg.ado_user_email or "").strip() or "someone"


def share(cfg: Config, text: str) -> bool:
    """Post `text` to the share channel. Returns True on success, False on
    skip/failure. Never raises."""
    if not is_enabled():
        return False
    url = webhook_url()
    if not url:
        log.debug("share: VAMOS_SUCCESS_WEBHOOK_URL unset; skipping")
        return False
    try:
        slack_mod.post(url, text)
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("share: Slack post failed: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Per-action formatters
# ---------------------------------------------------------------------------


def _ticket_link(cfg: Config, ticket_id: int) -> str:
    """Return Slack mrkdwn link to a ticket — falls back to plain `#id`."""
    if not ticket_id:
        return ""
    base = cfg.ado_org_url.rstrip("/")
    project = cfg.ado_project
    url = f"{base}/{project}/_workitems/edit/{ticket_id}"
    return f"<{url}|#{ticket_id}>"


def _pr_link(cfg: Config, repo: str, pr_id: int) -> str:
    base = cfg.ado_org_url.rstrip("/")
    project = cfg.ado_project
    url = f"{base}/{project}/_git/{repo}/pullrequest/{pr_id}"
    return f"<{url}|PR #{pr_id}>"


def started_work(cfg: Config, ticket_id: int, title: str | None = None) -> bool:
    title_part = f" — {title}" if title else ""
    text = f"*{actor(cfg)}* started work on {_ticket_link(cfg, ticket_id)}{title_part} · {TAG}"
    return share(cfg, text)


def opened_pr(cfg: Config, pr_id: int, repo: str, title: str | None = None) -> bool:
    title_part = f" — {title}" if title else ""
    text = f"*{actor(cfg)}* opened {_pr_link(cfg, repo, pr_id)} in {repo}{title_part} · {TAG}"
    return share(cfg, text)


def closed_ticket(
    cfg: Config, ticket_id: int, title: str | None,
    resolution: str | None = None,
) -> bool:
    title_part = f" — {title}" if title else ""
    res_part = f" (resolved as {resolution})" if resolution else ""
    text = f"*{actor(cfg)}* closed {_ticket_link(cfg, ticket_id)}{title_part}{res_part} · {TAG}"
    return share(cfg, text)


def voted_on_pr(cfg: Config, pr_id: int, repo: str, vote: str) -> bool:
    verb_by_vote = {
        "approve": "approved",
        "approve-with-suggestions": "approved (with suggestions)",
        "wait-for-author": "asked for changes on",
        "reject": "rejected",
        "no-vote": "cleared their vote on",
    }
    verb = verb_by_vote.get(vote, f"voted {vote} on")
    text = f"*{actor(cfg)}* {verb} {_pr_link(cfg, repo, pr_id)} in {repo} · {TAG}"
    return share(cfg, text)


def ran_pr_review(
    cfg: Config, pr_id: int, repo: str, finding_count: int, posted: bool,
) -> bool:
    if not posted:
        return False  # silent reviews shouldn't shout
    text = (
        f"*{actor(cfg)}* ran an automated review on {_pr_link(cfg, repo, pr_id)} "
        f"in {repo} ({finding_count} finding(s) posted) · {TAG}"
    )
    return share(cfg, text)


def custom(
    cfg: Config, action: str, summary: str,
    ticket_id: int | None = None, pr_id: int | None = None, repo: str | None = None,
) -> bool:
    """Manual share_success_story tool — Claude-formatted ad-hoc moments.

    `action` is a short verb-phrase ("crushed three P1s", "first vamos use",
    etc.). `summary` is the human-friendly sentence body.
    """
    parts = [f"*{actor(cfg)}* — {action}", summary]
    if ticket_id:
        parts.append(_ticket_link(cfg, ticket_id))
    if pr_id and repo:
        parts.append(_pr_link(cfg, repo, pr_id))
    text = "  ·  ".join(p for p in parts if p) + f" · {TAG}"
    return share(cfg, text)


# ---------------------------------------------------------------------------
# MCP tool entry point
# ---------------------------------------------------------------------------


def share_success_story(
    action: str,
    summary: str,
    ticket_id: int | None = None,
    pr_id: int | None = None,
    repo: str | None = None,
) -> dict[str, Any]:
    """MCP tool body: post a freeform success-story message.

    Use for genuinely interesting moments that don't map to one of the
    auto-fired actions — e.g. "first vamos use", "closed three P1s in
    one day", "review-to-merge in 90 minutes".
    """
    from ._context import get_ctx

    ctx = get_ctx()
    posted = custom(ctx.cfg, action=action, summary=summary,
                    ticket_id=ticket_id, pr_id=pr_id, repo=repo)
    return {
        "posted": posted,
        "channel": "VAMOS_SUCCESS_WEBHOOK_URL" if webhook_url() else None,
        "action": action,
        "summary": summary,
        "skipped_reason": (
            None if posted
            else "VAMOS_SUCCESS_STORIES=false" if not is_enabled()
            else "VAMOS_SUCCESS_WEBHOOK_URL unset" if not webhook_url()
            else "Slack post failed (see server logs)"
        ),
    }
