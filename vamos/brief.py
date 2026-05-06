"""1:1 brief — per-engineer summary for managers.

Pulls together: shipped this week, currently working, blocked, hygiene record,
PRs reviewed/authored, comments. Output: one short markdown page.
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .ado import ADOClient
from .config import Config
from .core.people import canonical, display_name
from .core.snapshot import (
    ACTIVE_STATES, BLOCKED_STATES, CLOSED_STATES, build_snapshot,
)

log = logging.getLogger(__name__)


def run(cfg: Config, engineer: str, weeks: int = 1, day: date | None = None) -> str:
    """Build a 1:1 brief for `engineer` covering the last `weeks` weeks."""
    day = day or date.today()
    target_canon = canonical(engineer)

    client = ADOClient(cfg.ado_org_url, cfg.ado_project, cfg.ado_pat, read_only=True)

    snapshot = build_snapshot(
        client,
        area_path=cfg.hygiene_area_path,
        iteration_path=cfg.hygiene_iteration_path,
        repos=cfg.hygiene_repos or None,
        include_closed_days=weeks * 7 + 7,
    )

    items = [
        w for w in snapshot.work_items
        if canonical(w.assigned_to) == target_canon
    ]
    if not items:
        return f"# 1:1 brief — {display_name(engineer)}\n\n_No tickets found assigned to this person._\n"

    cutoff = datetime.now(timezone.utc) - timedelta(days=weeks * 7)

    shipped = []
    for w in items:
        if w.state not in CLOSED_STATES:
            continue
        cd = w.raw_fields.get("Microsoft.VSTS.Common.ClosedDate") or w.raw_fields.get("System.ChangedDate")
        try:
            if cd and datetime.fromisoformat(cd.replace("Z", "+00:00")) >= cutoff:
                shipped.append(w)
        except ValueError:
            continue

    active = [w for w in items if w.state in ACTIVE_STATES]
    blocked = [w for w in items if w.state in BLOCKED_STATES]

    # PRs authored or reviewed in the window
    pr_authored = [
        pr for pr in snapshot.pull_requests
        if canonical(pr.author_email or pr.author) == target_canon
    ]

    # Comments authored by the engineer in this window
    comment_count = 0
    for cmts in snapshot.comments_by_item.values():
        for c in cmts:
            if c.created < cutoff:
                continue
            if canonical(c.author_email or c.author) == target_canon:
                comment_count += 1

    # Hygiene history
    hyg_dir = cfg.state_dir / "hygiene"
    hygiene_findings_recent = 0
    hygiene_clean_days = 0
    if hyg_dir.exists():
        for f in sorted(hyg_dir.glob("*.json"))[-7:]:
            try:
                payload = json.loads(f.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            mine = [x for x in payload.get("findings", [])
                    if canonical(x.get("engineer")) == target_canon]
            if mine:
                hygiene_findings_recent += len(mine)
            else:
                hygiene_clean_days += 1

    # Render
    name = display_name(engineer)
    out = []
    out.append(f"# 1:1 brief — {name}")
    out.append(f"_Window: last {weeks} week(s)  ·  Generated {day.isoformat()}_\n")

    out.append("## At a glance")
    out.append(f"- Shipped: **{len(shipped)}** ticket(s)")
    out.append(f"- Active: **{len(active)}**, Blocked: **{len(blocked)}**")
    out.append(f"- PRs authored (active): **{len(pr_authored)}**")
    out.append(f"- ADO comments authored: **{comment_count}**")
    out.append(
        f"- Hygiene: **{hygiene_findings_recent}** findings in last 7 days  ·  "
        f"**{hygiene_clean_days}** clean day(s)"
    )
    out.append("")

    if shipped:
        out.append("## Shipped this window")
        for w in shipped[:10]:
            out.append(f"- [#{w.id}] {w.title}")
        if len(shipped) > 10:
            out.append(f"- _...and {len(shipped) - 10} more_")
        out.append("")

    if active:
        out.append("## Currently active")
        for w in active[:10]:
            ac = "P" + str(w.priority) if w.priority else "—"
            out.append(f"- [#{w.id}] {w.title}  ·  {ac}  ·  {w.state}")
        out.append("")

    if blocked:
        out.append("## Blocked")
        for w in blocked:
            out.append(f"- [#{w.id}] {w.title}")
        out.append("")

    if pr_authored:
        out.append("## PRs authored")
        for pr in pr_authored[:10]:
            out.append(f"- {pr.repo} PR #{pr.id} — {pr.title}")
        out.append("")

    return "\n".join(out)


def list_engineers(cfg: Config) -> list[str]:
    """List canonical engineer names from the current team snapshot."""
    client = ADOClient(cfg.ado_org_url, cfg.ado_project, cfg.ado_pat, read_only=True)
    snapshot = build_snapshot(
        client,
        area_path=cfg.hygiene_area_path,
        iteration_path=cfg.hygiene_iteration_path,
        repos=[],  # don't need PRs for the list
    )
    seen: dict[str, str] = {}
    for w in snapshot.work_items:
        if not w.assigned_to:
            continue
        c = canonical(w.assigned_to)
        if c not in seen:
            seen[c] = display_name(w.assigned_to)
    return sorted(seen.values())
