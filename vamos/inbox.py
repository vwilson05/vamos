"""Inbox — aggregate everything that wants the engineer's attention.

What lands in the inbox:
  1. PRs assigned to me as reviewer (review requested)
  2. PRs I authored that have new comments since my last activity
  3. ADO comments on tickets I'm assigned to, from other people
  4. ADO @-mentions in any comment
  5. New high-priority assignments since yesterday

Output is a list of InboxItem rows + grouping. Console-friendly + UI-friendly.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from typing import Any

from .ado import ADOClient
from .config import Config
from .core.people import canonical
from .pr_review.client import PRClient

log = logging.getLogger(__name__)


@dataclass
class InboxItem:
    kind: str  # 'review-request' | 'pr-comment' | 'ticket-comment' | 'mention' | 'new-assignment'
    title: str
    url: str
    actor: str  # who triggered this (commenter, requester)
    when: datetime
    summary: str
    ticket_id: int | None = None
    pr_id: int | None = None
    repo: str | None = None
    severity: str = "info"  # 'urgent' | 'normal' | 'info'


_MENTION_RE = re.compile(r"@<([^>]+)>")


def build(cfg: Config, since_hours: int = 48) -> list[InboxItem]:
    """Build the engineer's inbox. Reads ADO snapshot data + PR threads."""
    me = cfg.ado_user_email or ""
    me_canon = canonical(me)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=since_hours)

    ado = ADOClient(cfg.ado_org_url, cfg.ado_project, cfg.ado_pat, read_only=True)
    items: list[InboxItem] = []

    # 1) Tickets assigned to me + their recent comments from others
    try:
        ids = ado.query_assigned(cfg.assigned_user_clause)
        my_items = ado.get_work_items(ids[:200])  # cap for safety
    except Exception as exc:
        log.warning("inbox: failed to fetch assigned items: %s", exc)
        my_items = []

    for w in my_items:
        try:
            comments = ado.get_work_item_comments(w.id)
        except Exception as exc:
            log.debug("inbox: comments fetch failed for #%d: %s", w.id, exc)
            continue
        for c in comments:
            created = _parse_dt(c.get("createdDate"))
            if not created or created < cutoff:
                continue
            author = (c.get("createdBy") or {}).get("displayName", "?")
            author_email = (c.get("createdBy") or {}).get("uniqueName") or ""
            text = (c.get("text") or "").strip()
            # Skip my own comments
            if canonical(author_email) == me_canon or canonical(author) == me_canon:
                continue
            items.append(InboxItem(
                kind="ticket-comment",
                title=w.title,
                url=w.url,
                actor=author,
                when=created,
                summary=_clip(_strip_html(text), 240),
                ticket_id=w.id,
                severity="normal",
            ))
            # Mention detection
            if me and _contains_mention(text, me):
                items.append(InboxItem(
                    kind="mention",
                    title=w.title,
                    url=w.url,
                    actor=author,
                    when=created,
                    summary=_clip(_strip_html(text), 240),
                    ticket_id=w.id,
                    severity="urgent",
                ))

    # 2) New high-priority assignments (P1/P2 changed within last 24h)
    one_day_ago = datetime.now(timezone.utc) - timedelta(hours=24)
    for w in my_items:
        if w.priority is not None and w.priority <= 2:
            changed = w.raw_fields.get("System.ChangedDate")
            cd = _parse_dt(changed)
            if cd and cd >= one_day_ago:
                items.append(InboxItem(
                    kind="new-assignment",
                    title=w.title,
                    url=w.url,
                    actor="(ADO)",
                    when=cd,
                    summary=f"New P{w.priority} {w.type} in state {w.state}",
                    ticket_id=w.id,
                    severity="urgent" if w.priority == 1 else "normal",
                ))

    # 3) PRs across all project repos: review requests + comments on my PRs
    try:
        repos = ado.list_repo_names()
    except Exception as exc:
        log.warning("inbox: repo discovery failed: %s", exc)
        repos = []

    for repo_name in repos:
        pr_client = PRClient(cfg.ado_org_url, cfg.ado_project, repo_name, cfg.ado_pat)
        try:
            prs = pr_client.search(status="active")
        except Exception:
            continue
        for p in prs:
            pid = int(p["pullRequestId"])
            author = (p.get("createdBy") or {}).get("displayName", "?")
            author_email = (p.get("createdBy") or {}).get("uniqueName") or ""
            i_authored = canonical(author_email) == me_canon
            reviewers = p.get("reviewers") or []
            i_reviewing = any(
                canonical((r.get("uniqueName") or r.get("displayName") or "")) == me_canon
                for r in reviewers
            )
            if not (i_authored or i_reviewing):
                continue

            # Review request: PR where I'm a reviewer + I haven't voted yet
            if i_reviewing:
                my_vote = next(
                    (
                        r.get("vote", 0) for r in reviewers
                        if canonical((r.get("uniqueName") or r.get("displayName") or "")) == me_canon
                    ),
                    0,
                )
                if my_vote == 0:
                    items.append(InboxItem(
                        kind="review-request",
                        title=p.get("title", ""),
                        url=p.get("url", ""),
                        actor=author,
                        when=_parse_dt(p.get("creationDate")) or datetime.now(timezone.utc),
                        summary=f"PR review requested in {repo_name}",
                        pr_id=pid,
                        repo=repo_name,
                        severity="normal",
                    ))

            # New comments since cutoff on PRs I authored or am reviewing
            try:
                threads = pr_client.get_threads(pid)
            except Exception:
                continue
            for t in threads:
                for c in t.get("comments", []):
                    if c.get("commentType") == "system":
                        continue
                    c_author = (c.get("author") or {}).get("displayName", "?")
                    c_author_email = (c.get("author") or {}).get("uniqueName") or ""
                    if canonical(c_author_email) == me_canon:
                        continue
                    pub = _parse_dt(c.get("publishedDate"))
                    if not pub or pub < cutoff:
                        continue
                    text = (c.get("content") or "").strip()
                    items.append(InboxItem(
                        kind="pr-comment",
                        title=p.get("title", ""),
                        url=p.get("url", ""),
                        actor=c_author,
                        when=pub,
                        summary=_clip(text, 240),
                        pr_id=pid,
                        repo=repo_name,
                        severity="normal",
                    ))

    # Dedup + sort newest-first
    seen: set[tuple] = set()
    deduped: list[InboxItem] = []
    for it in items:
        key = (it.kind, it.ticket_id, it.pr_id, it.actor, it.when.isoformat()[:16], it.summary[:80])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(it)
    deduped.sort(key=lambda i: (-_severity_rank(i.severity), -i.when.timestamp()))
    return deduped


def render_text(items: list[InboxItem]) -> str:
    """Plain-text inbox for the CLI."""
    if not items:
        return "Inbox is clear."
    lines = [f"Inbox — {len(items)} item(s)"]
    by_kind: dict[str, list[InboxItem]] = {}
    for it in items:
        by_kind.setdefault(it.kind, []).append(it)
    KIND_ORDER = ["mention", "review-request", "new-assignment", "pr-comment", "ticket-comment"]
    for kind in KIND_ORDER:
        group = by_kind.get(kind, [])
        if not group:
            continue
        lines.append("")
        lines.append(f"[{kind.upper()}] {len(group)}")
        for it in group[:10]:
            ref = f" #{it.ticket_id}" if it.ticket_id else (f" PR#{it.pr_id}" if it.pr_id else "")
            lines.append(f"  {it.when.strftime('%m-%d %H:%M')}{ref} {it.title[:70]}")
            if it.summary:
                lines.append(f"      {it.actor}: {it.summary[:120]}")
        if len(group) > 10:
            lines.append(f"  ...and {len(group) - 10} more")
    return "\n".join(lines)


def to_dict_list(items: list[InboxItem]) -> list[dict[str, Any]]:
    return [asdict(it) | {"when": it.when.isoformat()} for it in items]


# --- helpers ---


def _parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text)


def _clip(text: str, n: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1] + "…"


def _contains_mention(text: str, email: str) -> bool:
    handle = email.split("@")[0].lower() if "@" in email else email.lower()
    if not handle:
        return False
    text_lower = text.lower()
    return ("@" + handle) in text_lower or handle in [m.group(1).lower() for m in _MENTION_RE.finditer(text)]


def _severity_rank(s: str) -> int:
    return {"urgent": 2, "normal": 1, "info": 0}.get(s, 0)
