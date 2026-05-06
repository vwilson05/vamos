"""Minimal Azure DevOps REST API client."""
from __future__ import annotations

import base64
import logging
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote

import requests

log = logging.getLogger(__name__)

API_VERSION = "7.1"
COMMENTS_API_VERSION = "7.1-preview.4"


class ADOError(RuntimeError):
    pass


class ReadOnlyError(ADOError):
    pass


@dataclass
class WorkItem:
    id: int
    type: str
    title: str
    state: str
    priority: int | None
    assigned_to: str | None
    description: str | None
    tags: list[str] = field(default_factory=list)
    url: str = ""
    raw_fields: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> "WorkItem":
        f = payload.get("fields", {})
        assigned = f.get("System.AssignedTo")
        if isinstance(assigned, dict):
            assigned = assigned.get("uniqueName") or assigned.get("displayName")
        tags_raw = f.get("System.Tags") or ""
        tags = [t.strip() for t in tags_raw.split(";") if t.strip()]
        return cls(
            id=int(payload["id"]),
            type=f.get("System.WorkItemType", "Task"),
            title=f.get("System.Title", ""),
            state=f.get("System.State", ""),
            priority=f.get("Microsoft.VSTS.Common.Priority"),
            assigned_to=assigned,
            description=f.get("System.Description"),
            tags=tags,
            url=payload.get("_links", {}).get("html", {}).get("href", ""),
            raw_fields=f,
        )


class ADOClient:
    def __init__(
        self,
        org_url: str,
        project: str,
        pat: str,
        read_only: bool = False,
        timeout: int = 30,
    ):
        self.org_url = org_url.rstrip("/")
        self.project = project
        self.read_only = read_only
        self.timeout = timeout
        token = base64.b64encode(f":{pat}".encode()).decode()
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Basic {token}",
                "Accept": "application/json",
            }
        )

    @property
    def base(self) -> str:
        return f"{self.org_url}/{quote(self.project, safe='')}/_apis"

    # ---- read ----

    def query_assigned(self, user_clause: str, include_closed: bool = False) -> list[int]:
        states_filter = ""
        if not include_closed:
            states_filter = (
                "AND [System.State] <> 'Closed' "
                "AND [System.State] <> 'Removed' "
                "AND [System.State] <> 'Done' "
                "AND [System.State] <> 'Resolved' "
            )
        query = (
            "SELECT [System.Id] FROM WorkItems "
            f"WHERE [System.AssignedTo] = {user_clause} "
            f"{states_filter}"
            "ORDER BY [Microsoft.VSTS.Common.Priority] ASC, [System.ChangedDate] DESC"
        )
        url = f"{self.base}/wit/wiql?api-version={API_VERSION}"
        resp = self.session.post(url, json={"query": query}, timeout=self.timeout)
        _raise(resp)
        return [int(item["id"]) for item in resp.json().get("workItems", [])]

    def get_work_items(self, ids: list[int]) -> list[WorkItem]:
        if not ids:
            return []
        items: list[WorkItem] = []
        # ADO caps batch GET at 200 ids.
        for chunk_start in range(0, len(ids), 200):
            chunk = ids[chunk_start : chunk_start + 200]
            url = (
                f"{self.base}/wit/workitems"
                f"?ids={','.join(str(i) for i in chunk)}"
                f"&$expand=all&api-version={API_VERSION}"
            )
            resp = self.session.get(url, timeout=self.timeout)
            _raise(resp)
            for payload in resp.json().get("value", []):
                items.append(WorkItem.from_api(payload))
        return items

    def query_assigned_with_filters(
        self,
        user_clause: str,
        area_path: str | list[str] | None = None,
        iteration_path: str | list[str] | None = None,
        include_closed: bool = False
    ) -> list[int]:
        """Query assigned items with optional area / iteration filters.

        Lists of paths are queried individually and merged (deduped) — one
        nonexistent area path logs a warning rather than killing the run.
        """
        areas = [area_path] if isinstance(area_path, str) else (list(area_path) if area_path else [None])
        iters = [iteration_path] if isinstance(iteration_path, str) else (list(iteration_path) if iteration_path else [None])
        if len(areas) == 1 and len(iters) == 1:
            pairs = [(areas[0], iters[0])]
        elif len(areas) == len(iters):
            pairs = list(zip(areas, iters))
        else:
            pairs = [(a, i) for a in areas for i in iters]

        seen: dict[int, None] = {}
        any_success = False
        any_attempted = False
        for a, i in pairs:
            any_attempted = True
            try:
                ids = self._query_assigned_with_filters_single(
                    user_clause, a, i, include_closed,
                )
                any_success = True
                for x in ids:
                    seen[x] = None
            except ADOError as exc:
                log.warning("query_assigned: skipping (area=%r, iter=%r): %s", a, i, exc)
        if not any_success and any_attempted:
            # Bubble up the failure only when EVERY combination failed.
            raise ADOError("All area/iteration combinations failed for assigned query")
        return list(seen.keys())

    def _query_assigned_with_filters_single(
        self,
        user_clause: str,
        area_path: str | None,
        iteration_path: str | None,
        include_closed: bool,
    ) -> list[int]:
        states_filter = ""
        if not include_closed:
            states_filter = (
                "AND [System.State] <> 'Closed' "
                "AND [System.State] <> 'Removed' "
                "AND [System.State] <> 'Done' "
                "AND [System.State] <> 'Resolved' "
            )
        area_filter = f"AND [System.AreaPath] = '{area_path}' " if area_path else ""
        iteration_filter = f"AND [System.IterationPath] = '{iteration_path}' " if iteration_path else ""
        query = (
            "SELECT [System.Id] FROM WorkItems "
            f"WHERE [System.AssignedTo] = {user_clause} "
            f"{area_filter}"
            f"{iteration_filter}"
            f"{states_filter}"
            "ORDER BY [Microsoft.VSTS.Common.Priority] ASC, [System.ChangedDate] DESC"
        )
        url = f"{self.base}/wit/wiql?api-version={API_VERSION}"
        resp = self.session.post(url, json={"query": query}, timeout=self.timeout)
        _raise(resp)
        return [int(item["id"]) for item in resp.json().get("workItems", [])]

    def get_assigned_work_items(self, user_clause: str) -> list[WorkItem]:
        ids = self.query_assigned(user_clause)
        items = self.get_work_items(ids)
        items.sort(
            key=lambda w: (
                w.priority if w.priority is not None else 99,
                _state_order(w.state),
                w.id,
            )
        )
        return items

    def get_assigned_work_items_with_filters(
        self,
        user_clause: str,
        area_path: str | None = None,
        iteration_path: str | None = None
    ) -> list[WorkItem]:
        """Get assigned work items with optional area and iteration path filters."""
        ids = self.query_assigned_with_filters(user_clause, area_path, iteration_path)
        items = self.get_work_items(ids)
        items.sort(
            key=lambda w: (
                w.priority if w.priority is not None else 99,
                _state_order(w.state),
                w.id,
            )
        )
        return items

    def query_team_items(
        self,
        area_path: str | list[str] | None,
        iteration_path: str | list[str] | None,
        include_closed_days: int = 14,
    ) -> list[int]:
        """Query work items by area / iteration path.

        Either argument may be a single string OR a list of strings. When a
        list is passed, each path is queried separately and results are merged
        (deduped) — one bad path logs a warning instead of failing the whole
        run. This matters because boards in .ado-metrics.yml may include
        aspirational paths that don't yet exist in ADO.
        """
        # Normalize to lists for uniform handling
        areas = [area_path] if isinstance(area_path, str) else (list(area_path) if area_path else [None])
        iters = [iteration_path] if isinstance(iteration_path, str) else (list(iteration_path) if iteration_path else [None])

        # Pair them up: same length = zip; otherwise cartesian (treat None as "no filter")
        if len(areas) == 1 and len(iters) == 1:
            pairs = [(areas[0], iters[0])]
        elif len(areas) == len(iters):
            pairs = list(zip(areas, iters))
        else:
            pairs = [(a, i) for a in areas for i in iters]

        seen: dict[int, None] = {}
        any_success = False
        for a, i in pairs:
            if not (a or i):
                continue
            try:
                ids = self._query_team_items_single(a, i, include_closed_days)
                any_success = True
                for x in ids:
                    seen[x] = None
            except ADOError as exc:
                log.warning("query_team_items: skipping (area=%r, iter=%r): %s", a, i, exc)
        if not any_success and pairs:
            raise ADOError(f"All {len(pairs)} area/iteration combinations failed in ADO query")
        return list(seen.keys())

    def _query_team_items_single(
        self, area_path: str | None, iteration_path: str | None, include_closed_days: int
    ) -> list[int]:
        clauses: list[str] = []
        if area_path:
            clauses.append(f"[System.AreaPath] = '{area_path}'")
        if iteration_path:
            clauses.append(f"[System.IterationPath] = '{iteration_path}'")
        if not clauses:
            raise ADOError("query_team_items requires area_path or iteration_path")
        clauses.append(
            "(([System.State] <> 'Closed' AND [System.State] <> 'Removed' "
            "AND [System.State] <> 'Done' AND [System.State] <> 'Resolved') "
            f"OR [System.ChangedDate] >= @Today - {int(include_closed_days)})"
        )
        query = (
            "SELECT [System.Id] FROM WorkItems WHERE "
            + " AND ".join(clauses)
            + " ORDER BY [System.AssignedTo], [Microsoft.VSTS.Common.Priority] ASC"
        )
        url = f"{self.base}/wit/wiql?api-version={API_VERSION}"
        resp = self.session.post(url, json={"query": query}, timeout=self.timeout)
        _raise(resp)
        return [int(w["id"]) for w in resp.json().get("workItems", [])]

    def get_work_item_comments(self, work_item_id: int) -> list[dict[str, Any]]:
        url = (
            f"{self.base}/wit/workItems/{work_item_id}/comments"
            f"?api-version={COMMENTS_API_VERSION}"
        )
        resp = self.session.get(url, timeout=self.timeout)
        _raise(resp)
        return resp.json().get("comments", [])

    def list_repos(self) -> list[dict[str, Any]]:
        """List all git repos in the configured project."""
        url = f"{self.base}/git/repositories?api-version={API_VERSION}"
        resp = self.session.get(url, timeout=self.timeout)
        _raise(resp)
        return resp.json().get("value", [])

    def list_repo_names(self) -> list[str]:
        return [r["name"] for r in self.list_repos() if not r.get("isDisabled", False)]

    def list_active_prs(self, repo: str) -> list[dict[str, Any]]:
        url = (
            f"{self.base}/git/repositories/{quote(repo, safe='')}/pullrequests"
            f"?searchCriteria.status=active&api-version={API_VERSION}"
        )
        resp = self.session.get(url, timeout=self.timeout)
        _raise(resp)
        return resp.json().get("value", [])

    def get_work_item_relations(self, work_item_id: int) -> list[dict[str, Any]]:
        """Return raw `relations` array for a work item ($expand=relations)."""
        url = (
            f"{self.base}/wit/workitems/{work_item_id}"
            f"?$expand=relations&api-version={API_VERSION}"
        )
        resp = self.session.get(url, timeout=self.timeout)
        _raise(resp)
        return resp.json().get("relations", []) or []

    def get_pr_work_item_ids(self, repo: str, pr_id: int) -> list[int]:
        url = (
            f"{self.base}/git/repositories/{quote(repo, safe='')}/pullrequests/{pr_id}/workitems"
            f"?api-version={API_VERSION}"
        )
        resp = self.session.get(url, timeout=self.timeout)
        _raise(resp)
        return [int(r["id"]) for r in resp.json().get("value", [])]

    # ---- write ----

    def patch_fields(self, work_item_id: int, fields: dict[str, Any]) -> WorkItem:
        ops = [
            {"op": "add", "path": f"/fields/{name}", "value": value}
            for name, value in fields.items()
        ]
        return self._patch_work_item(work_item_id, ops)

    def add_comment(self, work_item_id: int, text: str) -> dict[str, Any]:
        self._guard_write()
        url = (
            f"{self.base}/wit/workItems/{work_item_id}/comments"
            f"?api-version={COMMENTS_API_VERSION}"
        )
        resp = self.session.post(
            url,
            json={"text": text},
            headers={"Content-Type": "application/json"},
            timeout=self.timeout,
        )
        _raise(resp)
        return resp.json()

    def create_work_item(
        self,
        work_item_type: str,
        title: str,
        description: str | None = None,
        priority: int | None = None,
        assigned_to: str | None = None,
        area_path: str | None = None,
        iteration_path: str | None = None,
        acceptance_criteria: str | None = None,
        tags: list[str] | None = None,
        parent_id: int | None = None,
        extra_fields: dict[str, Any] | None = None,
    ) -> WorkItem:
        self._guard_write()
        ops: list[dict[str, Any]] = [
            {"op": "add", "path": "/fields/System.Title", "value": title}
        ]
        if description:
            ops.append(
                {"op": "add", "path": "/fields/System.Description", "value": description}
            )
        if priority is not None:
            ops.append(
                {"op": "add", "path": "/fields/Microsoft.VSTS.Common.Priority", "value": priority}
            )
        if assigned_to:
            ops.append({"op": "add", "path": "/fields/System.AssignedTo", "value": assigned_to})
        if area_path:
            ops.append({"op": "add", "path": "/fields/System.AreaPath", "value": area_path})
        if iteration_path:
            ops.append({"op": "add", "path": "/fields/System.IterationPath", "value": iteration_path})
        if acceptance_criteria:
            ops.append({
                "op": "add",
                "path": "/fields/Microsoft.VSTS.Common.AcceptanceCriteria",
                "value": acceptance_criteria,
            })
        if tags:
            ops.append({"op": "add", "path": "/fields/System.Tags", "value": "; ".join(tags)})
        if parent_id is not None:
            parent_url = f"{self.org_url}/_apis/wit/workItems/{parent_id}"
            ops.append({
                "op": "add",
                "path": "/relations/-",
                "value": {
                    "rel": "System.LinkTypes.Hierarchy-Reverse",
                    "url": parent_url,
                    "attributes": {},
                },
            })
        for name, value in (extra_fields or {}).items():
            ops.append({"op": "add", "path": f"/fields/{name}", "value": value})

        encoded_type = quote(f"${work_item_type}", safe="$")
        url = f"{self.base}/wit/workitems/{encoded_type}?api-version={API_VERSION}"
        resp = self.session.post(
            url,
            json=ops,
            headers={"Content-Type": "application/json-patch+json"},
            timeout=self.timeout,
        )
        _raise(resp)
        return WorkItem.from_api(resp.json())

    def link_work_items(
        self,
        source_id: int,
        target_id: int,
        rel: str = "System.LinkTypes.Related",
    ) -> WorkItem:
        target_url = f"{self.org_url}/_apis/wit/workItems/{target_id}"
        ops = [
            {
                "op": "add",
                "path": "/relations/-",
                "value": {"rel": rel, "url": target_url, "attributes": {}},
            }
        ]
        return self._patch_work_item(source_id, ops)

    # ---- internals ----

    def _patch_work_item(self, work_item_id: int, ops: list[dict[str, Any]]) -> WorkItem:
        self._guard_write()
        url = f"{self.base}/wit/workitems/{work_item_id}?api-version={API_VERSION}"
        resp = self.session.patch(
            url,
            json=ops,
            headers={"Content-Type": "application/json-patch+json"},
            timeout=self.timeout,
        )
        _raise(resp)
        return WorkItem.from_api(resp.json())

    def _guard_write(self) -> None:
        if self.read_only:
            raise ReadOnlyError("ADO_READ_ONLY=true blocks write operations")


def _path_clause(field: str, value: str | list[str] | None) -> str:
    """Render a `[field] = 'X'` or `([field] = 'X' OR [field] = 'Y')` clause.

    Returns '' when value is falsy.
    """
    if not value:
        return ""
    paths = [value] if isinstance(value, str) else list(value)
    paths = [p for p in paths if p]
    if not paths:
        return ""
    if len(paths) == 1:
        return f"[{field}] = '{paths[0]}'"
    parts = " OR ".join(f"[{field}] = '{p}'" for p in paths)
    return f"({parts})"


_STATE_RANK = {
    "New": 0,
    "Active": 1,
    "Doing": 1,
    "In Progress": 1,
    "Committed": 1,
    "Approved": 2,
    "Resolved": 3,
    "Done": 4,
    "Closed": 5,
}


def _state_order(state: str) -> int:
    return _STATE_RANK.get(state, 2)


def _raise(resp: requests.Response) -> None:
    if resp.ok:
        return
    body = resp.text
    if len(body) > 500:
        body = body[:500] + "…"
    raise ADOError(f"ADO {resp.request.method} {resp.url} -> {resp.status_code}: {body}")
