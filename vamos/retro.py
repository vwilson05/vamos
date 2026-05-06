"""Sprint retro — auto-draft retrospective starter.

Aggregates from the configured iteration:
  - What shipped (closed in window)
  - What missed (target dates that passed during the window)
  - Themes from blocked-reasons (most common keywords in Blocked-state titles/notes)
  - Top customers by closure count (using customer.py heuristic)
  - Velocity (story points completed)

Output: a markdown retro starter the team can paste into a doc and edit.
"""
from __future__ import annotations

import logging
import re
from collections import Counter
from datetime import date, datetime, timedelta, timezone

from .ado import ADOClient
from .config import Config
from .core.customer import group_by_customer, top_customers
from .core.snapshot import CLOSED_STATES, BLOCKED_STATES, build_snapshot

log = logging.getLogger(__name__)


def run(cfg: Config, iteration_path: str | None = None, weeks: int = 2,
        day: date | None = None) -> str:
    day = day or date.today()
    client = ADOClient(cfg.ado_org_url, cfg.ado_project, cfg.ado_pat, read_only=True)

    iter_path = iteration_path or cfg.hygiene_iteration_path
    snapshot = build_snapshot(
        client,
        area_path=cfg.hygiene_area_path,
        iteration_path=iter_path,
        include_closed_days=weeks * 7 + 7,
        repos=[],  # PRs not needed for retro v1
    )

    cutoff = datetime.now(timezone.utc) - timedelta(days=weeks * 7)

    shipped = []
    missed = []
    for w in snapshot.work_items:
        # Shipped: closed within window
        if w.state in CLOSED_STATES:
            cd = w.raw_fields.get("Microsoft.VSTS.Common.ClosedDate") or w.raw_fields.get("System.ChangedDate")
            try:
                if cd and datetime.fromisoformat(cd.replace("Z", "+00:00")) >= cutoff:
                    shipped.append(w)
            except ValueError:
                continue
        # Missed: not closed and target date passed within window
        else:
            target = w.raw_fields.get("Microsoft.VSTS.Scheduling.TargetDate")
            if target:
                try:
                    td = datetime.fromisoformat(target.replace("Z", "+00:00"))
                    if td >= cutoff and td.date() < day:
                        missed.append(w)
                except ValueError:
                    pass

    # Velocity (sum of story points among shipped)
    points = 0
    for w in shipped:
        sp = w.raw_fields.get("Microsoft.VSTS.Scheduling.StoryPoints")
        if isinstance(sp, (int, float)):
            points += int(sp)

    # Customer breakdown
    customer_breakdown = top_customers(shipped, n=8)

    # Theme extraction from blocked tickets — naive top-words
    blocked = [w for w in snapshot.work_items if w.state in BLOCKED_STATES]
    blocker_themes = _top_keywords([w.title for w in blocked], n=8)

    # Render
    out = []
    out.append(f"# Sprint retro starter — {day.strftime('%b %d, %Y')}")
    if iter_path:
        out.append(f"_Iteration: {iter_path}_")
    out.append(f"_Window: last {weeks} week(s)_\n")

    out.append("## Headline numbers")
    out.append(f"- Tickets shipped: **{len(shipped)}**")
    out.append(f"- Story points completed: **{points}**")
    out.append(f"- Tickets that missed target date: **{len(missed)}**")
    out.append(f"- Currently blocked: **{len(blocked)}**")
    out.append("")

    if customer_breakdown:
        out.append("## Top customers by ticket closure")
        for c, n in customer_breakdown:
            out.append(f"- {c}: {n}")
        out.append("")

    if shipped:
        out.append("## What shipped (sample)")
        for w in shipped[:15]:
            out.append(f"- [#{w.id}] {w.title}")
        if len(shipped) > 15:
            out.append(f"- _...and {len(shipped) - 15} more_")
        out.append("")

    if missed:
        out.append("## What missed target")
        for w in missed[:10]:
            out.append(f"- [#{w.id}] {w.title}  (assigned to {w.assigned_to or '?'})")
        out.append("")

    if blocker_themes:
        out.append("## Recurring blocker themes")
        for kw, n in blocker_themes:
            out.append(f"- {kw}  ({n} tickets)")
        out.append("")

    out.append("## Discussion prompts (fill in)")
    out.append("- What went well?")
    out.append("- What got in our way?")
    out.append("- What's one thing we should change next iteration?")

    return "\n".join(out)


_STOPWORDS = {
    "the", "a", "an", "and", "or", "to", "of", "in", "on", "for", "with",
    "is", "are", "be", "by", "from", "as", "at", "this", "that", "it",
    "fix", "update", "review", "implement", "code", "test", "add",
}


def _top_keywords(texts: list[str], n: int = 5) -> list[tuple[str, int]]:
    counts: Counter[str] = Counter()
    for t in texts:
        words = re.findall(r"[A-Za-z][A-Za-z\-]{2,}", t.lower())
        for w in words:
            if w in _STOPWORDS:
                continue
            counts[w] += 1
    return counts.most_common(n)
