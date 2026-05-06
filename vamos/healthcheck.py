"""Team healthcheck: generate a summary of tickets for all developers."""
from __future__ import annotations

import json
import logging
import random
import yaml
from datetime import date, datetime
from pathlib import Path
from typing import Any

from .ado import ADOClient
from .config import Config, ROOT
from .core.people import canonical, display_name
from . import teams as teams_mod
from . import slack as slack_mod

log = logging.getLogger(__name__)


# Status phrases (no emojis per project convention)
DEVELOPER_PHRASES = [
    "is in the zone",
    "is shipping",
    "is heads-down",
    "is closing tickets steadily",
    "is on a roll",
    "is making progress",
    "is wrangling production",
    "is reviewing and refactoring",
    "is debugging methodically",
    "is dialed in",
]


def load_developers(work_dir: Path) -> list[str]:
    """Load developers from developers.yml.

    Looks at the repo root first (canonical location), then work_dir
    (back-compat with older deployments). Returns [] when neither file
    exists or both are empty — caller should auto-discover from ADO.
    """
    for candidate in (ROOT / "developers.yml", work_dir / "developers.yml"):
        if not candidate.exists():
            continue
        try:
            data = yaml.safe_load(candidate.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            log.warning("could not parse %s: %s", candidate, exc)
            continue
        devs = data.get("developers", []) or []
        if devs:
            log.info("healthcheck: loaded %d developers from %s", len(devs), candidate)
            return devs
    log.info("healthcheck: developers.yml empty or missing — will auto-discover from ADO")
    return []


def auto_discover_developers(
    client: ADOClient,
    area_path: str | None,
    iteration_path: str | None,
) -> list[str]:
    """Discover the team by listing assignees in the configured area path.

    Uses people.canonical to dedupe ADO's split identities (display name vs
    email vs OIDCONFLICT_UpnReuse_..._...).
    """
    if not (area_path or iteration_path):
        return []
    try:
        ids = client.query_team_items(
            area_path=area_path,
            iteration_path=iteration_path,
            include_closed_days=0,
        )
    except Exception as exc:
        log.warning("healthcheck: auto-discover query failed: %s", exc)
        return []
    if not ids:
        return []
    items = client.get_work_items(ids)
    seen: dict[str, str] = {}
    for w in items:
        if not w.assigned_to:
            continue
        canon = canonical(w.assigned_to)
        if canon and canon not in seen:
            # Prefer the raw display-name form when available; fall back to canonical
            seen[canon] = (
                w.assigned_to if "@" not in w.assigned_to else display_name(w.assigned_to)
            )
    discovered = sorted(seen.values())
    log.info("healthcheck: auto-discovered %d developer(s) from area path", len(discovered))
    return discovered


def get_developer_summary(client: ADOClient, developer_name: str, area_path: str | None = None, iteration_path: str | None = None) -> dict[str, Any]:
    """Get ticket summary for a specific developer."""
    # Build the user clause for the query
    # ADO expects format like '@Me' or 'John Doe'
    user_clause = f"'{developer_name}'"

    try:
        # Query assigned items for this developer with filters
        items = client.get_assigned_work_items_with_filters(
            user_clause,
            area_path=area_path,
            iteration_path=iteration_path
        )

        # Categorize items by state
        in_progress = []
        todo = []
        blocked = []
        other = []

        for item in items:
            state = item.state.lower()
            item_info = {
                "id": item.id,
                "title": item.title[:80],  # Truncate long titles
                "type": item.type,
                "priority": item.priority,
                "state": item.state,
            }

            if "progress" in state or "active" in state or "doing" in state:
                in_progress.append(item_info)
            elif "new" in state or "to do" in state or "proposed" in state:
                todo.append(item_info)
            elif "blocked" in state or "waiting" in state:
                blocked.append(item_info)
            else:
                other.append(item_info)

        # Select a random funny phrase
        phrase = random.choice(DEVELOPER_PHRASES)

        return {
            "name": developer_name,
            "phrase": phrase,
            "total_items": len(items),
            "in_progress": in_progress[:3],  # Top 3 in progress items
            "todo": todo[:3],  # Top 3 todo items
            "blocked": blocked,  # All blocked items (important to know)
            "stats": {
                "in_progress_count": len(in_progress),
                "todo_count": len(todo),
                "blocked_count": len(blocked),
                "other_count": len(other),
            }
        }
    except Exception as e:
        log.error(f"Failed to get summary for {developer_name}: {e}")
        return {
            "name": developer_name,
            "phrase": "is between updates",
            "error": str(e),
            "total_items": 0,
            "in_progress": [],
            "todo": [],
            "blocked": [],
            "stats": {
                "in_progress_count": 0,
                "todo_count": 0,
                "blocked_count": 0,
                "other_count": 0,
            }
        }


def format_healthcheck_markdown(summaries: list[dict[str, Any]], check_date: date, area_path=None, iteration_path=None) -> str:
    """Format the healthcheck data as markdown."""
    from .core.boards import display_path
    lines = []
    lines.append(f"# Team Health Check — {check_date.strftime('%A, %B %d, %Y')}")
    lines.append("")
    lines.append("_Snapshot of what each engineer is working on right now._")
    lines.append("")
    if area_path:
        lines.append(f"**Board:** {display_path(area_path)}")
    if iteration_path:
        lines.append(f"**Iteration:** {display_path(iteration_path)}")
    if area_path or iteration_path:
        lines.append("")
    lines.append("---")
    lines.append("")

    for summary in summaries:
        name = summary["name"]
        phrase = summary["phrase"]

        lines.append(f"## {name}")
        lines.append(f"*{name} {phrase}*")
        lines.append("")

        if "error" in summary:
            lines.append(f"**Unable to fetch tickets:** {summary['error']}")
            lines.append("")
            continue

        stats = summary["stats"]
        lines.append(f"**Overview:** {summary['total_items']} total items "
                    f"({stats['in_progress_count']} in progress, "
                    f"{stats['todo_count']} todo, "
                    f"{stats['blocked_count']} blocked)")
        lines.append("")

        if summary["blocked"]:
            lines.append("**Blocked:**")
            for item in summary["blocked"]:
                lines.append(f"- [{item['id']}] {item['title']}")
            lines.append("")

        if summary["in_progress"]:
            lines.append("**Currently working on:**")
            for item in summary["in_progress"]:
                priority = f"P{item['priority']}" if item['priority'] else "No Priority"
                lines.append(f"- [{item['id']}] {item['title']} ({priority})")
            lines.append("")

        if summary["todo"]:
            lines.append("**Next up:**")
            for item in summary["todo"]:
                priority = f"P{item['priority']}" if item['priority'] else "No Priority"
                lines.append(f"- [{item['id']}] {item['title']} ({priority})")
            lines.append("")

        lines.append("---")
        lines.append("")

    # Add summary statistics
    total_items = sum(s["total_items"] for s in summaries if "error" not in s)
    total_blocked = sum(s["stats"]["blocked_count"] for s in summaries if "error" not in s)
    total_in_progress = sum(s["stats"]["in_progress_count"] for s in summaries if "error" not in s)

    lines.append("## Team Summary")
    lines.append(f"- **Total Active Items:** {total_items}")
    lines.append(f"- **Items In Progress:** {total_in_progress}")
    blocked_label = "needs attention" if total_blocked > 0 else "all clear"
    lines.append(f"- **Blocked Items:** {total_blocked} ({blocked_label})")
    lines.append("")
    lines.append(f"_Generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}_")

    return "\n".join(lines)


def format_healthcheck_text(summaries: list[dict[str, Any]], check_date: date, area_path=None, iteration_path=None) -> str:
    """Format the healthcheck data as plain text for Teams/Slack."""
    from .core.boards import display_path
    lines = []
    lines.append(f"**Team Health Check — {check_date.strftime('%A, %B %d, %Y')}**")

    if area_path or iteration_path:
        board_info = []
        if area_path:
            board_info.append(f"**Board:** {display_path(area_path)}")
        if iteration_path:
            board_info.append(f"**Iteration:** {display_path(iteration_path)}")
        lines.append(" | ".join(board_info))
    lines.append("")

    for summary in summaries:
        name = summary["name"]
        phrase = summary["phrase"]

        lines.append(f"**{name}** {phrase}")

        if "error" in summary:
            lines.append(f"⚠️ Unable to fetch tickets: {summary['error']}")
            lines.append("")
            continue

        stats = summary["stats"]

        # Show key metrics
        metrics = []
        if stats['blocked_count'] > 0:
            metrics.append(f"{stats['blocked_count']} blocked")
        metrics.append(f"{stats['in_progress_count']} in progress")
        metrics.append(f"{stats['todo_count']} todo")

        lines.append(f"  {' | '.join(metrics)}")

        # Show blocked items if any
        if summary["blocked"]:
            for item in summary["blocked"][:2]:  # Show max 2 blocked items
                lines.append(f"  Blocked: [{item['id']}] {item['title'][:50]}...")

        lines.append("")

    # Add summary
    total_items = sum(s["total_items"] for s in summaries if "error" not in s)
    total_blocked = sum(s["stats"]["blocked_count"] for s in summaries if "error" not in s)

    lines.append("**Team Totals:**")
    lines.append(f"{total_items} active items")
    if total_blocked > 0:
        lines.append(f"{total_blocked} blocked items need attention")
    else:
        lines.append("No blockers")

    return "\n".join(lines)


def run(
    cfg: Config,
    skip_post: bool = False,
    day: date | None = None,
) -> str:
    """Run the healthcheck and generate the report."""
    day = day or date.today()

    # Initialize ADO client first (needed for auto-discovery + per-dev queries)
    client = ADOClient(cfg.ado_org_url, cfg.ado_project, cfg.ado_pat, read_only=True)

    # Load developers from developers.yml first; fall back to ADO auto-discovery
    log.info("healthcheck: resolving developer list")
    developers = load_developers(cfg.work_dir)
    if not developers:
        developers = auto_discover_developers(
            client,
            area_path=cfg.healthcheck_area_path,
            iteration_path=cfg.healthcheck_iteration_path,
        )

    if not developers:
        raise SystemExit(
            "No developers found. Add to developers.yml at the repo root, or set "
            "HEALTHCHECK_AREA_PATH so we can auto-discover from ADO."
        )

    log.info("healthcheck: %d developer(s) to summarize", len(developers))

    # Use configured area and iteration paths, or defaults
    area_path = cfg.healthcheck_area_path
    iteration_path = cfg.healthcheck_iteration_path

    if area_path:
        log.info(f"Querying tickets from area: {area_path}")
    if iteration_path:
        log.info(f"Querying tickets from iteration: {iteration_path}")
    if not area_path and not iteration_path:
        log.info("No area or iteration filters configured - querying all tickets")

    # Get summary for each developer
    summaries = []
    for developer in developers:
        log.info(f"Fetching tickets for {developer}")
        summary = get_developer_summary(client, developer, area_path=area_path, iteration_path=iteration_path)
        summaries.append(summary)

    # Generate markdown report
    markdown_content = format_healthcheck_markdown(summaries, day, area_path=area_path, iteration_path=iteration_path)

    # Save markdown file
    healthcheck_path = cfg.state_dir / f"{day.isoformat()}-healthcheck.md"
    healthcheck_path.write_text(markdown_content, encoding="utf-8")
    log.info(f"Wrote healthcheck to {healthcheck_path}")

    # Use the full markdown content for posting (not the simplified version)
    post_text = markdown_content

    # Post to Teams or Slack if not skipped
    if not skip_post:
        if cfg.connection_option == "Teams":
            if cfg.teams_webhook_url:
                teams_mod.post(cfg.teams_webhook_url, post_text)
                log.info("Posted healthcheck to Teams")
            else:
                log.warning("TEAMS_WEBHOOK_URL not set — skipping Teams post")
        elif cfg.connection_option == "Slack":
            if cfg.slack_webhook_url:
                try:
                    slack_mod.post(cfg.slack_webhook_url, post_text)
                    log.info("Posted healthcheck to Slack")
                except Exception as e:
                    log.error(f"Failed to post to Slack: {e}")
            else:
                log.warning("SLACK_WEBHOOK_URL not set — skipping Slack post")
    else:
        log.info("Skipping post to Teams/Slack (--skip-post flag)")

    return markdown_content