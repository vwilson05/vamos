"""ADO Pull Request REST client for vamos pr-review.

Adapted from the original pr_client.py in the standalone pr-reviewer skill.
Key changes for the suite:
- Auth comes from vamos.config.Config (PAT, org URL) — no separate .env load
- Repo can be auto-detected from `git remote get-url origin` OR passed in
- Same comment-posting + voting behavior as the original
"""
from __future__ import annotations

import base64
import json
import logging
import re
import subprocess
import urllib.parse
from pathlib import Path
from typing import Any

import requests

log = logging.getLogger(__name__)

API_VERSION = "7.1-preview"
PR_REVIEWER_TAG = "<!-- vamos:pr-review -->"

VOTE_VALUES = {
    "approve": 10,
    "approve-with-suggestions": 5,
    "no-vote": 0,
    "wait-for-author": -5,
    "reject": -10,
}


class PRClientError(RuntimeError):
    pass


def detect_repo(cwd: Path | None = None) -> tuple[str, str, str] | None:
    """Return (org_url, project, repo) by parsing the git origin URL of cwd. None if not in a git repo."""
    try:
        url = subprocess.check_output(
            ["git", "remote", "get-url", "origin"],
            stderr=subprocess.DEVNULL,
            cwd=cwd,
        ).decode().strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    url = re.sub(r"^https://[^@/]+@", "https://", url)
    m = re.match(r"https://(dev\.azure\.com/[^/]+)/([^/]+)/_git/([^/]+?)(?:\.git)?$", url)
    if not m:
        return None
    return "https://" + m.group(1), urllib.parse.unquote(m.group(2)), m.group(3)


class PRClient:
    """Thin wrapper around ADO Git APIs scoped to one repo."""

    def __init__(self, org_url: str, project: str, repo: str, pat: str, timeout: int = 30):
        self.org_url = org_url.rstrip("/")
        self.project = project
        self.repo = repo
        self.timeout = timeout
        token = base64.b64encode(f":{pat}".encode()).decode()
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Basic {token}",
            "Accept": "application/json",
        })

    @property
    def base(self) -> str:
        proj = urllib.parse.quote(self.project, safe="")
        return f"{self.org_url}/{proj}/_apis/git/repositories/{self.repo}"

    @property
    def project_base(self) -> str:
        proj = urllib.parse.quote(self.project, safe="")
        return f"{self.org_url}/{proj}/_apis"

    def _get(self, path: str) -> Any:
        return self._request("GET", path)

    def _post(self, path: str, body: dict) -> Any:
        return self._request("POST", path, body)

    def _put(self, path: str, body: dict) -> Any:
        return self._request("PUT", path, body)

    def _request(self, method: str, path: str, body: dict | None = None) -> Any:
        url = path if path.startswith("http") else f"{self.base}{path}"
        resp = self.session.request(method, url, json=body, timeout=self.timeout)
        if resp.ok:
            return resp.json() if resp.text else None
        raise PRClientError(f"{method} {url} -> {resp.status_code}: {resp.text[:500]}")

    # --- PR queries ---

    def me(self) -> dict:
        return self._get(f"{self.org_url}/_apis/connectionData?api-version={API_VERSION}")["authenticatedUser"]

    def search(self, **criteria: str) -> list[dict]:
        params = {f"searchCriteria.{k}": v for k, v in criteria.items()}
        params["api-version"] = API_VERSION
        return self._get(f"/pullrequests?{urllib.parse.urlencode(params)}").get("value", [])

    def get_pr(self, pr_id: int) -> dict:
        return self._get(f"/pullrequests/{pr_id}?api-version={API_VERSION}")

    def get_workitems(self, pr_id: int) -> list[dict]:
        d = self._get(f"/pullrequests/{pr_id}/workitems?api-version={API_VERSION}")
        refs = d.get("value", [])
        if not refs:
            return []
        ids = ",".join(str(r["id"]) for r in refs)
        wi = self._get(
            f"{self.project_base}/wit/workitems?ids={ids}"
            f"&fields=System.Title,System.Description,System.WorkItemType,System.State,Microsoft.VSTS.Common.AcceptanceCriteria"
            f"&api-version={API_VERSION}"
        )
        return wi.get("value", [])

    def get_threads(self, pr_id: int) -> list[dict]:
        return self._get(f"/pullrequests/{pr_id}/threads?api-version={API_VERSION}").get("value", [])

    def get_iterations(self, pr_id: int) -> list[dict]:
        return self._get(f"/pullrequests/{pr_id}/iterations?api-version={API_VERSION}").get("value", [])

    # --- Posting ---

    def vote(self, pr_id: int, reviewer_id: str, vote: str) -> dict:
        if vote not in VOTE_VALUES:
            raise PRClientError(f"Unknown vote {vote!r}")
        return self._put(
            f"/pullrequests/{pr_id}/reviewers/{reviewer_id}?api-version={API_VERSION}",
            {"vote": VOTE_VALUES[vote]},
        )

    def post_thread(self, pr_id: int, thread: dict) -> dict:
        return self._post(f"/pullrequests/{pr_id}/threads?api-version={API_VERSION}", thread)


# --- Diff helpers (use local git, much simpler than ADO diff API) ---


def _git(*args: str, cwd: Path | None = None) -> str:
    return subprocess.check_output(["git", *args], stderr=subprocess.DEVNULL, cwd=cwd).decode()


def fetch_branches(source_branch: str, target_branch: str, cwd: Path | None = None) -> None:
    subprocess.run(
        ["git", "fetch", "origin", source_branch, target_branch],
        check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=cwd,
    )


def diff_against(source: str, target: str, cwd: Path | None = None) -> tuple[str, str]:
    full = _git("diff", f"{target}...{source}", cwd=cwd)
    stat = _git("diff", "--stat", f"{target}...{source}", cwd=cwd)
    return full, stat


# --- Brief assembly (markdown for the LLM reviewer) ---


def build_brief(client: PRClient, pr_id: int, repo_path: Path | None = None) -> str:
    pr = client.get_pr(pr_id)
    wis = client.get_workitems(pr_id)
    threads = client.get_threads(pr_id)
    src_ref = pr["sourceRefName"].replace("refs/heads/", "")
    tgt_ref = pr["targetRefName"].replace("refs/heads/", "")

    diff_text = ""
    stat_text = ""
    if repo_path is not None:
        fetch_branches(src_ref, tgt_ref, cwd=repo_path)
        try:
            diff_text, stat_text = diff_against(f"origin/{src_ref}", f"origin/{tgt_ref}", cwd=repo_path)
        except subprocess.CalledProcessError as exc:
            log.warning("git diff failed: %s — brief will skip diff body", exc)

    lines: list[str] = []
    lines.append(f"# PR {pr_id}: {pr['title']}\n")
    lines.append(f"- Author: {pr['createdBy']['displayName']}")
    lines.append(f"- Source: `{src_ref}` → Target: `{tgt_ref}`")
    lines.append(f"- Status: {pr.get('status')} (draft={pr.get('isDraft')})")
    lines.append(
        f"- URL: {client.org_url}/{urllib.parse.quote(client.project)}/_git/{client.repo}/pullrequest/{pr_id}\n"
    )

    lines.append("## Description\n")
    lines.append((pr.get("description") or "_(no description)_").strip() + "\n")

    lines.append("## Linked work items\n")
    if not wis:
        lines.append("_(none)_\n")
    else:
        for w in wis:
            f = w.get("fields", {})
            lines.append(
                f"### #{w['id']} — {f.get('System.Title','(no title)')} "
                f"({f.get('System.WorkItemType','?')}, {f.get('System.State','?')})"
            )
            desc = (f.get("System.Description") or "").strip()
            ac = (f.get("Microsoft.VSTS.Common.AcceptanceCriteria") or "").strip()
            if desc:
                lines.append("**Description:**\n" + desc + "\n")
            if ac:
                lines.append("**Acceptance criteria:**\n" + ac + "\n")

    lines.append("## Files changed\n")
    if stat_text:
        lines.append("```")
        lines.append(stat_text.strip())
        lines.append("```\n")
    else:
        lines.append("_(no local repo to compute diff stat — review by description and existing threads)_\n")

    lines.append("## Diff (merge-base)\n")
    if diff_text:
        lines.append("```diff")
        lines.append(diff_text.rstrip())
        lines.append("```\n")
    else:
        lines.append("_(no diff available — pass --repo or run from inside the cloned repo for code-level review)_\n")

    lines.append("## Existing PR comment threads\n")
    open_threads = [t for t in threads if t.get("status") not in ("fixed", "closed", "wontFix", "byDesign")]
    if not open_threads:
        lines.append("_(no open threads)_\n")
    else:
        for t in open_threads:
            ctx = t.get("threadContext") or {}
            loc = ""
            if ctx.get("filePath"):
                rs = ctx.get("rightFileStart") or {}
                loc = f"{ctx['filePath']}:{rs.get('line','?')}"
            lines.append(f"### Thread {t['id']} ({t.get('status','?')}) {loc}".rstrip())
            for c in t.get("comments", []):
                if c.get("commentType") == "system":
                    continue
                author = (c.get("author") or {}).get("displayName", "?")
                content = (c.get("content") or "").strip()
                lines.append(f"- **{author}:** {content}")
            lines.append("")

    return "\n".join(lines)


# --- Posting reviews ---


def _comment_body(text: str, severity: str | None = None, title: str | None = None) -> str:
    parts = [PR_REVIEWER_TAG]
    head_bits = []
    if severity:
        head_bits.append(f"**[{severity.upper()}]**")
    if title:
        head_bits.append(title)
    if head_bits:
        parts.append(" ".join(head_bits))
    parts.append(text.rstrip())
    return "\n\n".join(parts)


def _normalize_path(p: str) -> str:
    p = p.replace("\\", "/")
    if not p.startswith("/"):
        p = "/" + p
    return p


def post_review(client: PRClient, pr_id: int, review: dict, vote: str | None = None) -> dict:
    posted: list[dict] = []
    summary = (review.get("summary") or "").strip()
    verdict = review.get("verdict", "approve-with-suggestions")
    findings = review.get("findings", []) or []

    summary_body = _comment_body(
        f"_Verdict: **{verdict}**_\n\n{summary}\n\n"
        f"_{len(findings)} inline finding(s) below._",
        title="vamos pr-review summary",
    )
    summary_thread = client.post_thread(pr_id, {
        "comments": [{"parentCommentId": 0, "content": summary_body, "commentType": 1}],
        "status": 1,
    })
    posted.append({"kind": "summary", "thread_id": summary_thread.get("id")})

    for f in findings:
        body = _comment_body(
            (f.get("body") or "").strip()
            + (f"\n\n**Suggestion:**\n```\n{f['suggestion'].rstrip()}\n```" if f.get("suggestion") else ""),
            severity=f.get("severity"),
            title=f.get("title"),
        )
        thread: dict[str, Any] = {
            "comments": [{"parentCommentId": 0, "content": body, "commentType": 1}],
            "status": 1 if f.get("severity") in ("blocker", "should-fix", "question") else 4,
        }
        if f.get("file") and f.get("line_start"):
            ls = int(f["line_start"])
            le = int(f.get("line_end") or ls)
            if le < ls:
                le = ls
            thread["threadContext"] = {
                "filePath": _normalize_path(f["file"]),
                "rightFileStart": {"line": ls, "offset": 1},
                "rightFileEnd": {"line": le, "offset": 1},
            }
        t = client.post_thread(pr_id, thread)
        posted.append({
            "kind": "finding",
            "thread_id": t.get("id"),
            "severity": f.get("severity"),
            "file": f.get("file"),
            "line": f.get("line_start"),
        })

    result: dict[str, Any] = {"posted": posted, "count": len(posted), "vote": None}
    if vote and vote != "no-vote":
        try:
            reviewer_id = client.me()["id"]
            client.vote(pr_id, reviewer_id, vote)
            result["vote"] = {"value": vote, "score": VOTE_VALUES[vote], "status": "ok"}
        except PRClientError as exc:
            result["vote"] = {"value": vote, "status": "failed", "error": str(exc)}
    return result
