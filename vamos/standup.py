"""Standup brief — auto-draft yesterday/today/blockers from MD + ADO state.

Sources:
  - Yesterday's daily MD (work/<yesterday>.md) — what was being worked
  - Tickets closed since yesterday — what shipped
  - Today's daily MD (or live ADO query if today's MD doesn't exist) — what's next
  - Tickets in Blocked state assigned to me — blockers

Output: a short markdown block ready to paste into Slack/standup.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .ado import ADOClient
from .config import Config
from .markdown_io import daily_path, parse_sections


def run(cfg: Config, day: date | None = None) -> str:
    day = day or date.today()
    yesterday = day - timedelta(days=1)
    # Skip weekend backwards: if day is Mon, yesterday for standup is Fri.
    while yesterday.weekday() >= 5:
        yesterday -= timedelta(days=1)

    yesterday_md = daily_path(cfg.work_dir, yesterday)
    today_md = daily_path(cfg.work_dir, day)

    yest_sections = parse_sections(yesterday_md.read_text(encoding="utf-8")) if yesterday_md.exists() else []
    today_sections = parse_sections(today_md.read_text(encoding="utf-8")) if today_md.exists() else []

    ado = ADOClient(cfg.ado_org_url, cfg.ado_project, cfg.ado_pat, read_only=True)

    # What shipped: tickets closed since yesterday morning that I was assigned to
    cutoff = datetime.combine(yesterday, datetime.min.time(), tzinfo=timezone.utc)
    try:
        ids = ado.query_assigned(cfg.assigned_user_clause, include_closed=True)
        all_items = ado.get_work_items(ids[:200])
    except Exception:
        all_items = []

    closed_since = []
    for w in all_items:
        if w.state not in ("Closed", "Resolved", "Done"):
            continue
        cd = w.raw_fields.get("Microsoft.VSTS.Common.ClosedDate") or w.raw_fields.get("System.ChangedDate")
        if cd:
            try:
                ts = datetime.fromisoformat(cd.replace("Z", "+00:00"))
                if ts >= cutoff:
                    closed_since.append(w)
            except ValueError:
                continue

    # Active + Blocked today
    active = [w for w in all_items if w.state in ("Active", "Doing", "In Progress", "Committed")]
    blocked = [w for w in all_items if w.state in ("Blocked", "Waiting")]

    # What's "today" — from today's MD if present, else from active items
    today_titles = []
    for sect in today_sections:
        wid = sect.work_item_id
        if wid:
            today_titles.append(f"#{wid} {sect.title}")
        elif sect.is_new and sect.title:
            today_titles.append(f"[NEW] {sect.title}")
        elif sect.title:
            today_titles.append(sect.title)
    if not today_titles:
        for w in active[:5]:
            today_titles.append(f"#{w.id} {w.title}")

    # What was "yesterday" — yesterday MD section titles + closed items
    yesterday_titles = []
    closed_ids = {w.id for w in closed_since}
    for w in closed_since:
        yesterday_titles.append(f"#{w.id} {w.title}  (closed)")
    for sect in yest_sections:
        wid = sect.work_item_id
        if wid is None or wid in closed_ids:
            continue
        yesterday_titles.append(f"#{wid} {sect.title}")

    # Render
    lines = [f"## Standup — {day.strftime('%A %b %d')}", ""]
    name = cfg.developer_name or "(me)"
    lines.append(f"**{name}**")
    lines.append("")

    lines.append("**Yesterday**")
    if yesterday_titles:
        for t in yesterday_titles[:6]:
            lines.append(f"- {t}")
    else:
        lines.append("- (no recorded activity)")
    lines.append("")

    lines.append("**Today**")
    if today_titles:
        for t in today_titles[:6]:
            lines.append(f"- {t}")
    else:
        lines.append("- (no items planned)")
    lines.append("")

    lines.append("**Blockers**")
    if blocked:
        for w in blocked[:5]:
            lines.append(f"- #{w.id} {w.title}")
    else:
        lines.append("- None")

    return "\n".join(lines)
