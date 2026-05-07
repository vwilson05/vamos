"""Thin programmatic adapter for the metrics generator.

The CLI handler (`vamos.metrics_cli.cmd_metrics_generate`) takes an argparse
Namespace and prints to stdout. For MCP we want a structured return without
the argparse plumbing — so this module replicates the same call sequence
(context → collect → generate) and returns the result file path + summary.
"""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from ..ado import ADOClient
from ..config import Config
from ..metrics import (
    ADOBoardMetricsCollector,
    ADOTeamContext,
    ReportGenerator,
    ReportOptions,
)

log = logging.getLogger(__name__)


def generate(cfg: Config, format: str = "markdown") -> dict[str, Any]:
    """Run the metrics pipeline using cfg's healthcheck paths as the board scope.

    Always dry-run (never sends notifications from MCP). Returns the local
    output path and a short summary so Claude can read the file or relay
    a one-liner to the user.
    """
    area = cfg.healthcheck_area_path
    iteration = cfg.healthcheck_iteration_path
    if isinstance(area, list):
        area = area[0] if area else None
    if isinstance(iteration, list):
        iteration = iteration[0] if iteration else None

    context = ADOTeamContext(
        area_path=area or "",
        iteration_path=iteration,
        board=None,
    )

    date_str = datetime.now().strftime("%Y-%m-%d")
    board_slug = (area or "metrics").replace("\\", "_").replace(" ", "_").lower()
    out_dir = Path("metrics_reports")
    out_dir.mkdir(exist_ok=True)
    output_path = str(out_dir / f"{date_str}_{board_slug}_metrics.{format}")

    client = ADOClient(
        org_url=cfg.ado_org_url,
        project=cfg.ado_project,
        pat=cfg.ado_pat,
        read_only=cfg.ado_read_only,
    )

    collector = ADOBoardMetricsCollector(client)
    metrics = collector.collect_board_metrics(context, allowed_developers=None)

    options = ReportOptions(
        area_path=area or "",
        iteration_path=iteration,
        format=format,
        output_path=output_path,
        dry_run=True,
        send_notifications=False,
        include_charts=False,
        include_achievements=True,
    )
    generator = ReportGenerator()
    result = generator.generate_report(metrics, options)

    return {
        "format": format,
        "area_path": area,
        "iteration_path": iteration,
        "output_path": str(result.local_path),
        "exists": Path(result.local_path).exists() if result.local_path else False,
        "summary": _summarize(metrics),
    }


def _summarize(metrics: Any) -> dict[str, Any]:
    """Pull a tiny summary out of the metrics object so callers don't have
    to read the file just to know what's in it. Keys vary by metrics shape;
    we fish for common attributes and skip anything missing."""
    out: dict[str, Any] = {}
    for attr in (
        "total_items", "total_active", "total_closed", "total_blocked",
        "throughput_last_week", "cycle_time_days_p50", "cycle_time_days_p90",
        "developer_count", "engineer_count",
    ):
        val = getattr(metrics, attr, None)
        if val is not None:
            out[attr] = val
    return out
