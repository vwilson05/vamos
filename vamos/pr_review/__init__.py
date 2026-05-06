"""vamos.pr_review — automated pull-request review for Azure DevOps Repos.

Two modes:
- One-shot: `vamos pr-review <PR_ID>` — review a single PR. Posts comments unless --no-post.
- Watch:    `vamos pr-review --watch` — service mode; polls active PRs and auto-reviews
            new iterations. Designed for cron / always-on host.
"""
from .runner import run, list_prs

__all__ = ["run", "list_prs"]
