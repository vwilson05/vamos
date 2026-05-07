"""PR-centric MCP tools.

  open_pr        — create a PR via ADO + link work item (auto-execute)
  run_pr_review  — call the existing pr-review pipeline, return findings JSON
                   (no_post=True by default; pass post=True + confirm=True to publish)
"""
from __future__ import annotations

import logging
from typing import Any

from ...llm import call_claude, parse_json_response, render_prompt
from ...pr_review.client import PRClient, build_brief, post_review
from .. import trail
from .._context import get_ctx

log = logging.getLogger(__name__)


def open_pr(
    ticket_id: int,
    repo: str,
    source_branch: str,
    title: str,
    description: str = "",
    target_branch: str = "main",
    is_draft: bool = False,
) -> dict[str, Any]:
    """Open a PR in the named ADO git repo and link it to the work item.

    Auto-executes (no confirm). PRs are easy to abandon if wrong; the cost
    of one extra confirm round-trip per PR isn't worth the friction.
    """
    ctx = get_ctx()
    payload = ctx.client.create_pr(
        repo=repo,
        source_branch=source_branch,
        target_branch=target_branch,
        title=title,
        description=description,
        work_item_ids=[ticket_id],
        is_draft=is_draft,
    )
    pr_id = int(payload.get("pullRequestId", 0))
    web_url = _pr_web_url(ctx.cfg.ado_org_url, ctx.cfg.ado_project, repo, pr_id)
    result = {
        "pr_id": pr_id,
        "repo": repo,
        "title": title,
        "source_branch": source_branch,
        "target_branch": target_branch,
        "is_draft": is_draft,
        "url": web_url,
        "linked_ticket": ticket_id,
        "next_actions": [
            {
                "tool": "run_pr_review",
                "why": "Get an automated review pass before requesting human review",
                "args": {"pr_id": pr_id, "repo": repo},
            }
        ],
    }
    trail.append_event(
        ctx.cfg.state_dir, ticket_id, "open_pr",
        args={"repo": repo, "source_branch": source_branch, "title": title},
        result={"pr_id": pr_id, "url": web_url},
    )
    return result


def run_pr_review(
    pr_id: int,
    repo: str,
    post: bool = False,
    confirm: bool = False,
) -> dict[str, Any]:
    """Run the vamos PR reviewer against a PR and return the structured review.

    By default returns the review JSON without posting. To publish the
    findings as PR comments, pass post=True AND confirm=True (two-step
    safety so Claude can't accidentally spam a PR with comments).
    """
    ctx = get_ctx()
    pr_client = PRClient(ctx.cfg.ado_org_url, ctx.cfg.ado_project, repo, ctx.cfg.ado_pat)

    log.info("mcp run_pr_review: building brief for %s#%d", repo, pr_id)
    brief = build_brief(pr_client, pr_id, repo_path=None)
    prompt = render_prompt("pr_review/reviewer.md", brief=brief)
    response = call_claude(prompt, claude_bin=ctx.cfg.claude_bin, timeout=900)

    try:
        review = parse_json_response(response)
    except Exception as exc:  # noqa: BLE001
        return {
            "error": "Reviewer returned non-JSON output",
            "parse_error": str(exc),
            "raw_response_head": response[:500],
        }

    findings = review.get("findings") or []
    base_result: dict[str, Any] = {
        "pr_id": pr_id,
        "repo": repo,
        "verdict": review.get("verdict"),
        "summary": review.get("summary"),
        "finding_count": len(findings),
        "findings": findings,
    }

    if not post:
        base_result["posted"] = False
        # Post-trail before returning so we know a review pass ran.
        _trail_review(ctx, pr_id, repo, base_result)
        return base_result

    if not confirm:
        base_result["preview"] = True
        base_result["message"] = (
            f"Would post {len(findings)} thread(s) to PR #{pr_id} in {repo}. "
            "Re-call with post=True AND confirm=True to publish."
        )
        return base_result

    try:
        post_result = post_review(pr_client, pr_id, review, vote=None)
    except Exception as exc:  # noqa: BLE001
        return {**base_result, "post_error": str(exc), "posted": False}

    base_result["posted"] = True
    base_result["threads_posted"] = post_result.get("count", 0)
    _trail_review(ctx, pr_id, repo, base_result)
    return base_result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _pr_web_url(org_url: str, project: str, repo: str, pr_id: int) -> str:
    return f"{org_url}/{project}/_git/{repo}/pullrequest/{pr_id}"


def _trail_review(ctx: Any, pr_id: int, repo: str, result: dict[str, Any]) -> None:
    """PR reviews don't have a single ticket — fan out across linked work items.

    We look up which work items the PR is linked to and write the trail event
    on each so next_actions on those tickets sees "review already ran".
    """
    try:
        ticket_ids = ctx.client.get_pr_work_item_ids(repo, pr_id)
    except Exception as exc:  # noqa: BLE001
        log.debug("trail: PR work-item lookup failed for %s#%d: %s", repo, pr_id, exc)
        return
    for tid in ticket_ids:
        trail.append_event(
            ctx.cfg.state_dir, tid, "run_pr_review",
            args={"pr_id": pr_id, "repo": repo},
            result={
                "verdict": result.get("verdict"),
                "finding_count": result.get("finding_count"),
                "posted": result.get("posted"),
            },
        )
