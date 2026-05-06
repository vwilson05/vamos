"""PR review queue — triaged view of PRs across all repos.

What it adds beyond `list_prs`:
  - Tags each PR with whether the caller is the author / a reviewer / both
  - Flags "blocked on me" — last comment in any thread is from someone else
  - Computes age (days since creation) and last-activity
  - Sorts: blocker-on-me first, then aging assigned PRs, then drafts last
  - Optional buddy-routing check: warns when an India-team author skipped
    their Costa Rica buddy reviewer
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from ..ado import ADOClient
from ..config import Config, ROOT
from ..core.people import canonical
from .client import PRClient

log = logging.getLogger(__name__)


@dataclass
class QueueItem:
    pr_id: int
    repo: str
    title: str
    author: str
    author_email: str | None
    source_branch: str
    target_branch: str
    is_draft: bool
    age_days: int
    role: str  # 'author' | 'reviewer' | 'both' | 'observer'
    blocked_on_me: bool
    last_activity: datetime | None
    url: str
    buddy_skipped: str | None = None  # if non-None: name of buddy who should have been added


def load_buddies() -> dict[str, str]:
    """Read author -> buddy reviewer map from .ado-metrics.yml or routing.yml."""
    paths = [ROOT / "routing.yml", ROOT / ".ado-metrics.yml"]
    for p in paths:
        if not p.exists():
            continue
        try:
            data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue
        buddies = data.get("buddies") or data.get("review_buddies") or {}
        if isinstance(buddies, dict) and buddies:
            return {canonical(k): v for k, v in buddies.items()}
        if isinstance(buddies, list):
            out: dict[str, str] = {}
            for entry in buddies:
                if isinstance(entry, dict) and "author" in entry and "buddy" in entry:
                    out[canonical(entry["author"])] = entry["buddy"]
            if out:
                return out
    return {}


def build_queue(cfg: Config, repo: str | None = None) -> list[QueueItem]:
    me = canonical(cfg.ado_user_email)
    buddies = load_buddies()
    ado = ADOClient(cfg.ado_org_url, cfg.ado_project, cfg.ado_pat, read_only=True)
    repos = [repo] if repo else ado.list_repo_names()

    items: list[QueueItem] = []
    now = datetime.now(timezone.utc)

    for repo_name in repos:
        client = PRClient(cfg.ado_org_url, cfg.ado_project, repo_name, cfg.ado_pat)
        try:
            prs = client.search(status="active")
        except Exception as exc:
            log.warning("queue: list failed for %s: %s", repo_name, exc)
            continue

        for p in prs:
            pid = int(p["pullRequestId"])
            author = (p.get("createdBy") or {}).get("displayName", "?")
            author_email = (p.get("createdBy") or {}).get("uniqueName") or ""
            author_canon = canonical(author_email or author)

            reviewers = p.get("reviewers") or []
            reviewer_canons = [
                canonical((r.get("uniqueName") or r.get("displayName") or ""))
                for r in reviewers
            ]
            i_authored = author_canon == me and bool(me)
            i_reviewing = me in reviewer_canons and bool(me)
            role = (
                "both" if i_authored and i_reviewing else
                "author" if i_authored else
                "reviewer" if i_reviewing else
                "observer"
            )

            creation = p.get("creationDate")
            try:
                created = datetime.fromisoformat(creation.replace("Z", "+00:00")) if creation else now
            except ValueError:
                created = now
            age_days = (now - created).days

            # Threads → blocked-on-me?
            blocked_on_me = False
            last_activity = created
            try:
                threads = client.get_threads(pid)
            except Exception:
                threads = []
            for t in threads:
                if t.get("status") in ("fixed", "closed", "wontFix", "byDesign"):
                    continue
                comments = [c for c in t.get("comments", []) if c.get("commentType") != "system"]
                if not comments:
                    continue
                last = comments[-1]
                last_author = canonical(
                    (last.get("author") or {}).get("uniqueName") or
                    (last.get("author") or {}).get("displayName") or ""
                )
                pub = last.get("publishedDate")
                try:
                    pub_dt = datetime.fromisoformat(pub.replace("Z", "+00:00")) if pub else None
                    if pub_dt and pub_dt > last_activity:
                        last_activity = pub_dt
                except ValueError:
                    pass
                # Blocked on me: I'm reviewer or author, last comment isn't mine
                if (i_reviewing or i_authored) and last_author and last_author != me:
                    blocked_on_me = True

            # Buddy routing check
            buddy_skipped = None
            buddy_name = buddies.get(author_canon)
            if buddy_name:
                buddy_canon = canonical(buddy_name)
                if buddy_canon not in reviewer_canons:
                    buddy_skipped = buddy_name

            items.append(QueueItem(
                pr_id=pid,
                repo=repo_name,
                title=p.get("title", ""),
                author=author,
                author_email=author_email,
                source_branch=(p.get("sourceRefName") or "").replace("refs/heads/", ""),
                target_branch=(p.get("targetRefName") or "").replace("refs/heads/", ""),
                is_draft=bool(p.get("isDraft", False)),
                age_days=age_days,
                role=role,
                blocked_on_me=blocked_on_me,
                last_activity=last_activity,
                url=p.get("url", ""),
                buddy_skipped=buddy_skipped,
            ))

    # Sort: blocked-on-me first, then assigned to me by age desc, then everything else
    def sort_key(it: QueueItem):
        return (
            0 if it.blocked_on_me else 1,
            0 if it.role in ("author", "reviewer", "both") else 1,
            -it.age_days,
            it.is_draft,
        )

    items.sort(key=sort_key)
    return items


def review_load(cfg: Config, days: int = 30) -> dict[str, int]:
    """Approximate review load: count of distinct PRs each reviewer is currently assigned to."""
    ado = ADOClient(cfg.ado_org_url, cfg.ado_project, cfg.ado_pat, read_only=True)
    counts: dict[str, int] = {}
    for repo_name in ado.list_repo_names():
        client = PRClient(cfg.ado_org_url, cfg.ado_project, repo_name, cfg.ado_pat)
        try:
            prs = client.search(status="active")
        except Exception:
            continue
        for p in prs:
            for r in p.get("reviewers") or []:
                name = r.get("displayName") or r.get("uniqueName") or "?"
                counts[name] = counts.get(name, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: -kv[1]))
