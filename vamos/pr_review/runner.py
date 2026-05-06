"""PR-review orchestration.

Three flows:
  - run() one-shot: brief → claude -p → JSON → (post if not no_post)
  - run() interactive: same, but prompt y/n before posting
  - run() watch: poll for new iterations across all active PRs and review automatically

The reviewer prompt lives at prompts/pr_review/reviewer.md.
"""
from __future__ import annotations

import json
import logging
import sys
import time
from datetime import date
from pathlib import Path

from ..ado import ADOClient
from ..config import Config, ROOT
from ..core import state
from ..llm import call_claude, parse_json_response, render_prompt
from .client import (
    PRClient,
    PRClientError,
    build_brief,
    detect_repo,
    post_review,
)

log = logging.getLogger(__name__)


def list_prs(cfg: Config, repo: str | None = None) -> list[dict]:
    """List active PRs.

    - If `repo` is given (or auto-detected from cwd's git remote): list that repo's PRs.
    - Otherwise: list active PRs across ALL repos in the project (each PR is
      tagged with `_repo` so callers can dispatch correctly).
    """
    repo_path = _detect_repo_path()
    chosen = repo
    if not chosen and repo_path:
        detected = detect_repo(repo_path)
        if detected:
            chosen = detected[2]

    if chosen:
        client = PRClient(cfg.ado_org_url, cfg.ado_project, chosen, cfg.ado_pat)
        prs = client.search(status="active")
        for p in prs:
            p["_repo"] = chosen
        return prs

    # Auto-discover: list across all repos in the project
    ado = ADOClient(cfg.ado_org_url, cfg.ado_project, cfg.ado_pat, read_only=True)
    all_prs: list[dict] = []
    for repo_name in ado.list_repo_names():
        client = PRClient(cfg.ado_org_url, cfg.ado_project, repo_name, cfg.ado_pat)
        try:
            prs = client.search(status="active")
        except PRClientError as exc:
            log.warning("pr-review: list failed for repo %s: %s", repo_name, exc)
            continue
        for p in prs:
            p["_repo"] = repo_name
        all_prs.extend(prs)
    return all_prs


def run(
    cfg: Config,
    pr_id: int | None = None,
    repo: str | None = None,
    interactive: bool = False,
    no_post: bool = False,
    watch: bool = False,
) -> int:
    if watch:
        return _watch(cfg, repo)

    repo_path = _detect_repo_path()

    # No id and no repo: list across all repos in the project
    if pr_id is None:
        prs = list_prs(cfg, repo=repo)
        if not prs:
            print("No active PRs found.")
            return 0
        # If exactly one and we have a clear repo, review it
        if len(prs) == 1 and (repo or prs[0].get("_repo")):
            chosen_repo = repo or prs[0]["_repo"]
            client = PRClient(cfg.ado_org_url, cfg.ado_project, chosen_repo, cfg.ado_pat)
            pr_id = int(prs[0]["pullRequestId"])
            print(f"Reviewing the only active PR: #{pr_id} in {chosen_repo}")
            return _review_one(cfg, client, pr_id, repo_path, interactive=interactive, no_post=no_post)
        # List for the user to choose from
        if repo:
            print(f"Active PRs in {repo}:")
        else:
            print(f"Active PRs across {len({p.get('_repo') for p in prs})} repo(s):")
        by_repo: dict[str, list[dict]] = {}
        for p in prs:
            by_repo.setdefault(p.get("_repo", "?"), []).append(p)
        for r, ps in sorted(by_repo.items()):
            print(f"\n  [{r}]")
            for p in ps:
                print(f"    #{p['pullRequestId']} — {p['title']} (by {p['createdBy']['displayName']})")
        print("\nRe-run with `vamos pr-review <PR_ID> [--repo REPO]` to review one.")
        return 0

    # PR id given: resolve repo (arg → cwd git → search across repos)
    client = _resolve_client_for_pr(cfg, pr_id, repo, repo_path)
    return _review_one(cfg, client, pr_id, repo_path, interactive=interactive, no_post=no_post)


def _review_one(
    cfg: Config,
    client: PRClient,
    pr_id: int,
    repo_path: Path | None,
    interactive: bool,
    no_post: bool,
) -> int:
    log.info("pr-review: building brief for PR #%d", pr_id)
    brief = build_brief(client, pr_id, repo_path=repo_path)

    log.info("pr-review: calling claude for review (brief %d chars)", len(brief))
    prompt = render_prompt("pr_review/reviewer.md", brief=brief)
    response = call_claude(prompt, claude_bin=cfg.claude_bin, timeout=900)

    try:
        review = parse_json_response(response)
    except Exception as exc:
        print("ERROR: model output was not valid JSON.")
        print(f"  parse error: {exc}")
        print("  raw response (first 1000 chars):")
        print(response[:1000])
        return 2

    _print_review_local(pr_id, review)

    state.write_log(cfg.state_dir, "pr-review", {
        "pr_id": pr_id,
        "repo": client.repo,
        "verdict": review.get("verdict"),
        "finding_count": len(review.get("findings") or []),
        "review": review,
    })

    if no_post:
        print("\n--no-post: skipping comment posting.")
        return 0

    vote = None
    if interactive or sys.stdin.isatty():
        choice = _prompt_post_choice(review.get("verdict", "approve-with-suggestions"))
        if choice == "skip":
            print("Skipped posting.")
            return 0
        if choice == "approve":
            vote = "approve"
        elif choice == "deny":
            vote = "reject"
    # headless: post comments without a vote (safer default — let humans decide approve/reject)

    try:
        result = post_review(client, pr_id, review, vote=vote)
    except PRClientError as exc:
        print(f"ERROR posting review: {exc}")
        return 2
    print(f"\nPosted {result['count']} thread(s) to PR #{pr_id}.")
    if result.get("vote"):
        print(f"Vote: {result['vote']}")
    return 0


def _watch(cfg: Config, repo: str | None) -> int:
    """Service mode: poll active PRs across all repos, review new iterations.

    Repo scope:
      - If `repo` is given: poll only that repo
      - Else: poll EVERY repo in the project on each tick

    State: state/pr-review/iterations.json keeps {"<repo>:<pr_id>": last_iteration_id}.
    Sleep VAMOS_PR_REVIEW_INTERVAL seconds between polls (default 300).
    Comments include <!-- vamos:pr-review --> so re-runs never double-post.
    """
    import os
    interval = int(os.getenv("VAMOS_PR_REVIEW_INTERVAL", "300"))

    if repo:
        repos = [repo]
        log.info("pr-review --watch: polling repo=%s every %ds", repo, interval)
    else:
        ado = ADOClient(cfg.ado_org_url, cfg.ado_project, cfg.ado_pat, read_only=True)
        repos = ado.list_repo_names()
        log.info("pr-review --watch: polling %d repos every %ds", len(repos), interval)

    iter_path = cfg.state_dir / "pr-review" / "iterations.json"
    iter_path.parent.mkdir(parents=True, exist_ok=True)
    seen: dict[str, int] = {}
    if iter_path.exists():
        try:
            seen = json.loads(iter_path.read_text())
        except json.JSONDecodeError:
            seen = {}

    while True:
        for repo_name in repos:
            client = PRClient(cfg.ado_org_url, cfg.ado_project, repo_name, cfg.ado_pat)
            try:
                prs = client.search(status="active")
            except PRClientError as exc:
                log.error("pr-review --watch: PR list failed for %s: %s", repo_name, exc)
                continue
            for p in prs:
                pid = int(p["pullRequestId"])
                key = f"{repo_name}:{pid}"
                try:
                    iters = client.get_iterations(pid)
                except PRClientError as exc:
                    log.warning("pr-review --watch: iter fetch failed for %s#%d: %s", repo_name, pid, exc)
                    continue
                if not iters:
                    continue
                latest = int(iters[-1]["id"])
                if seen.get(key) == latest:
                    continue
                log.info("pr-review --watch: %s#%d has new iteration %d — reviewing", repo_name, pid, latest)
                try:
                    _review_one(cfg, client, pid, _detect_repo_path(), interactive=False, no_post=False)
                    seen[key] = latest
                    iter_path.write_text(json.dumps(seen, indent=2))
                except Exception as exc:
                    log.exception("pr-review --watch: review of %s#%d failed: %s", repo_name, pid, exc)

        time.sleep(interval)


def _resolve_client_for_pr(
    cfg: Config, pr_id: int, repo: str | None, repo_path: Path | None,
) -> PRClient:
    """Find which repo a PR id lives in.

    Resolution order:
      1. --repo flag
      2. cwd's git remote (auto-detect)
      3. Search every repo in the project for one that has this pr_id
    """
    if repo:
        return PRClient(cfg.ado_org_url, cfg.ado_project, repo, cfg.ado_pat)

    if repo_path:
        detected = detect_repo(repo_path)
        if detected:
            return PRClient(detected[0], detected[1], detected[2], cfg.ado_pat)

    # Search across all repos for this PR id
    log.info("pr-review: searching all project repos for PR #%d", pr_id)
    ado = ADOClient(cfg.ado_org_url, cfg.ado_project, cfg.ado_pat, read_only=True)
    for repo_name in ado.list_repo_names():
        client = PRClient(cfg.ado_org_url, cfg.ado_project, repo_name, cfg.ado_pat)
        try:
            client.get_pr(pr_id)
            log.info("pr-review: PR #%d lives in %s", pr_id, repo_name)
            return client
        except PRClientError:
            continue

    raise SystemExit(
        f"PR #{pr_id} not found in any repo of project {cfg.ado_project!r}. "
        "Pass --repo <name> if the PR lives in a different project."
    )


def _detect_repo_path() -> Path | None:
    """Return cwd if it looks like a git repo, else None."""
    import subprocess
    try:
        top = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"], stderr=subprocess.DEVNULL,
        ).decode().strip()
        return Path(top)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def _print_review_local(pr_id: int, review: dict) -> None:
    print(f"\n# Review of PR {pr_id}")
    print(f"**Verdict:** {review.get('verdict','?')}\n")
    print(review.get("summary", "_(no summary)_"))
    findings = review.get("findings") or []
    print(f"\n## Findings ({len(findings)})\n")
    SEV_EMOJI = {"blocker": " ", "should-fix": " ", "nit": " ", "question": " ", "praise": " "}
    for f in findings:
        emoji = SEV_EMOJI.get(f.get("severity"), "•")
        loc = ""
        if f.get("file"):
            loc = f" ({f['file']}:{f.get('line_start','?')})"
        print(f"### {emoji} {(f.get('severity') or '').upper()} — {f.get('title','(no title)')}{loc}")
        print(f.get("body", "").strip())
        if f.get("suggestion"):
            print("\n```")
            print(f["suggestion"].strip())
            print("```")
        print()


def _prompt_post_choice(verdict: str) -> str:
    default = {
        "approve": "approve",
        "request-changes": "deny",
        "approve-with-suggestions": "post",
    }.get(verdict, "post")
    print(f"\nPost this to PR? [post/approve/deny/skip] (default: {default}) > ", end="", flush=True)
    raw = sys.stdin.readline().strip().lower()
    if not raw:
        raw = default
    if raw in ("p", "post", "y", "yes"):
        return "post"
    if raw in ("a", "approve"):
        return "approve"
    if raw in ("d", "deny", "reject", "n", "no"):
        return "deny"
    return "skip"
