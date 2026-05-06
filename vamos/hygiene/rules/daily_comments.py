"""daily-comments — Active or Blocked tickets need a comment from the assignee
on the current working day, before the configured deadline (default 5pm CST).

Dan tracks this every day. Severity: blocker.
"""
from __future__ import annotations

from datetime import datetime, time, timedelta, timezone

from ...config import Config
from ...core.report import Finding
from ...core.snapshot import ACTIVE_STATES, BLOCKED_STATES, TeamSnapshot

RULE_ID = "daily-comments"


def check(snapshot: TeamSnapshot, cfg: Config) -> list[Finding]:
    findings: list[Finding] = []
    deadline = _parse_time(cfg.hygiene_daily_comment_deadline)
    cutoff_utc = _cutoff(snapshot.snapshot_at, deadline)

    for w in snapshot.work_items:
        if w.state not in (ACTIVE_STATES | BLOCKED_STATES):
            continue
        if not w.assigned_to:
            continue
        comments = snapshot.comments_by_item.get(w.id, [])
        own = [c for c in comments if c.author_email == w.assigned_to or c.author == w.assigned_to]
        recent = [c for c in own if c.created >= cutoff_utc]
        if recent:
            continue
        findings.append(Finding(
            rule_id=RULE_ID,
            severity="blocker",
            engineer=w.assigned_to,
            ticket_id=w.id,
            ticket_url=w.url,
            ticket_title=w.title,
            message=(
                f"No daily status comment on this {w.state} ticket today. "
                f"Required by {cfg.hygiene_daily_comment_deadline} per board standards."
            ),
            suggested_comment=(
                "Daily status reminder — please post a quick update on this ticket "
                f"by {cfg.hygiene_daily_comment_deadline} (auto-tracked). "
                "Even one line: what you did today, what's next, any blockers."
            ),
        ))

    return findings


def _parse_time(s: str) -> time:
    parts = s.strip().split(":")
    return time(int(parts[0]), int(parts[1]) if len(parts) > 1 else 0)


def _cutoff(now_utc: datetime, deadline: time) -> datetime:
    """Most recent occurrence of `deadline` (treated as local time, naively)
    before `now_utc`. If now is past today's deadline, cutoff is today's
    deadline; otherwise it's yesterday's. We compute in local-naive then
    convert to UTC by treating local-naive as system local.
    """
    now_local = now_utc.astimezone()
    today_deadline = now_local.replace(
        hour=deadline.hour, minute=deadline.minute, second=0, microsecond=0
    )
    if now_local >= today_deadline:
        cutoff_local = today_deadline
    else:
        cutoff_local = today_deadline - timedelta(days=1)
    return cutoff_local.astimezone(timezone.utc)
