"""TeamSnapshot — single in-memory dataset for rule-based team agents.

Built once per agent run via build_snapshot(); rules then iterate over it
without re-querying ADO. The snapshot includes work items (active + recently
closed), comments on Active/Blocked items, and PRs from configured repos.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from ..ado import ADOClient, WorkItem

log = logging.getLogger(__name__)

ACTIVE_STATES = {"Active", "Doing", "In Progress", "Committed"}
BLOCKED_STATES = {"Blocked", "Waiting"}
TODO_STATES = {"New", "To Do", "Proposed", "Groomed", "Ready"}
CLOSED_STATES = {"Closed", "Resolved", "Done", "Removed"}
DEPRECATED_STATES = {"QA", "PR Ready", "QA Ready"}


@dataclass
class Comment:
    id: int
    work_item_id: int
    author: str  # display name
    author_email: str | None
    text: str
    created: datetime  # tz-aware UTC


@dataclass
class PullRequest:
    id: int
    title: str
    author: str
    author_email: str | None
    source_branch: str  # without refs/heads/
    target_branch: str
    status: str  # active | completed | abandoned
    is_draft: bool
    repo: str
    created: datetime
    work_item_ids: list[int]
    url: str


@dataclass
class TeamSnapshot:
    area_path: str | list[str] | None
    iteration_path: str | list[str] | None
    work_items: list[WorkItem]
    comments_by_item: dict[int, list[Comment]] = field(default_factory=dict)
    pull_requests: list[PullRequest] = field(default_factory=list)
    snapshot_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def assignees(self) -> list[str]:
        seen: dict[str, None] = {}
        for w in self.work_items:
            if w.assigned_to:
                seen.setdefault(w.assigned_to, None)
        return list(seen)

    def items_by_assignee(self, assignee: str) -> list[WorkItem]:
        return [w for w in self.work_items if w.assigned_to == assignee]

    def active_items(self) -> list[WorkItem]:
        return [w for w in self.work_items if w.state in ACTIVE_STATES]

    def blocked_items(self) -> list[WorkItem]:
        return [w for w in self.work_items if w.state in BLOCKED_STATES]

    def open_items(self) -> list[WorkItem]:
        return [w for w in self.work_items if w.state not in CLOSED_STATES]

    def closed_recently(self, since: datetime) -> list[WorkItem]:
        out: list[WorkItem] = []
        for w in self.work_items:
            if w.state not in CLOSED_STATES:
                continue
            cd = w.raw_fields.get("Microsoft.VSTS.Common.ClosedDate") or w.raw_fields.get("System.ChangedDate")
            if not cd:
                continue
            try:
                dt = datetime.fromisoformat(cd.replace("Z", "+00:00"))
                if dt >= since:
                    out.append(w)
            except (ValueError, AttributeError):
                continue
        return out

    def prs_for_item(self, item_id: int) -> list[PullRequest]:
        return [pr for pr in self.pull_requests if item_id in pr.work_item_ids]


def build_snapshot(
    client: ADOClient,
    area_path: str | list[str] | None,
    iteration_path: str | list[str] | None,
    include_closed_days: int = 14,
    repos: list[str] | None = None,
) -> TeamSnapshot:
    """Build a single team-wide snapshot.

    - Queries all work items in area_path (and iteration_path if set)
    - Includes recently-closed items (within include_closed_days) for the
      resolution-on-close rule
    - Loads comments only for Active/Blocked items (the rules that need them)
    - Loads PRs from `repos`. Semantics:
        * `None` → auto-discover ALL repos in the project (default for hygiene)
        * `[]`   → skip PR loading entirely (opt-out)
        * `[...]` → only the named repos
    """
    log.info("snapshot: querying work items area=%s iter=%s", area_path, iteration_path)
    ids = client.query_team_items(area_path=area_path, iteration_path=iteration_path,
                                  include_closed_days=include_closed_days)
    items = client.get_work_items(ids) if ids else []
    log.info("snapshot: %d items loaded", len(items))

    comments_by_item: dict[int, list[Comment]] = {}
    needs_comments = [w for w in items if w.state in ACTIVE_STATES | BLOCKED_STATES]
    log.info("snapshot: fetching comments for %d active/blocked items", len(needs_comments))
    for w in needs_comments:
        try:
            raw = client.get_work_item_comments(w.id)
        except Exception as exc:
            log.warning("snapshot: comment fetch failed for #%d: %s", w.id, exc)
            continue
        comments_by_item[w.id] = [_comment_from_api(w.id, c) for c in raw]

    prs: list[PullRequest] = []
    resolved_repos: list[str]
    if repos is None:
        try:
            resolved_repos = client.list_repo_names()
            log.info("snapshot: auto-discovered %d repo(s) in project", len(resolved_repos))
        except Exception as exc:
            log.warning("snapshot: repo auto-discovery failed: %s — skipping PR rules", exc)
            resolved_repos = []
    else:
        resolved_repos = list(repos)

    for repo in resolved_repos:
        try:
            raw_prs = client.list_active_prs(repo)
        except Exception as exc:
            log.warning("snapshot: PR list failed for repo %s: %s", repo, exc)
            continue
        if not raw_prs:
            continue
        for p in raw_prs:
            pr = _pr_from_api(p, repo)
            try:
                pr.work_item_ids = client.get_pr_work_item_ids(repo, pr.id)
            except Exception as exc:
                log.warning("snapshot: PR work-item link fetch failed for %s#%d: %s", repo, pr.id, exc)
            prs.append(pr)
    log.info("snapshot: %d PRs loaded across %d repo(s)", len(prs), len(resolved_repos))

    return TeamSnapshot(
        area_path=area_path,
        iteration_path=iteration_path,
        work_items=items,
        comments_by_item=comments_by_item,
        pull_requests=prs,
    )


def _comment_from_api(item_id: int, c: dict[str, Any]) -> Comment:
    author = c.get("createdBy") or {}
    return Comment(
        id=int(c.get("id", 0)),
        work_item_id=item_id,
        author=author.get("displayName", "?"),
        author_email=author.get("uniqueName"),
        text=c.get("text") or "",
        created=_parse_dt(c.get("createdDate")),
    )


def _pr_from_api(p: dict[str, Any], repo: str) -> PullRequest:
    author = p.get("createdBy") or {}
    return PullRequest(
        id=int(p["pullRequestId"]),
        title=p.get("title", ""),
        author=author.get("displayName", "?"),
        author_email=author.get("uniqueName"),
        source_branch=(p.get("sourceRefName") or "").replace("refs/heads/", ""),
        target_branch=(p.get("targetRefName") or "").replace("refs/heads/", ""),
        status=p.get("status", "?"),
        is_draft=bool(p.get("isDraft", False)),
        repo=repo,
        created=_parse_dt(p.get("creationDate")),
        work_item_ids=[],
        url=p.get("url", ""),
    )


def _parse_dt(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(timezone.utc)
