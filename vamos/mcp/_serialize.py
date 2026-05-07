"""Shared JSON serializers for MCP tool returns.

Most return values come from existing dataclasses (Report, Finding, QueueItem,
InboxItem, Dep). asdict() works on all of them but produces datetime objects
and Path instances that don't serialize cleanly. These helpers normalize.
"""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any


def to_jsonable(obj: Any) -> Any:
    """Recursively convert dataclasses, datetimes, and paths to JSON primitives."""
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Path):
        return str(obj)
    if is_dataclass(obj):
        return {k: to_jsonable(v) for k, v in asdict(obj).items()}
    if isinstance(obj, dict):
        return {k: to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [to_jsonable(v) for v in obj]
    return str(obj)


def report_to_dict(report: Any) -> dict[str, Any]:
    """Serialize a vamos.core.report.Report — flatten findings + counts."""
    findings = [to_jsonable(f) for f in report.findings]
    by_severity: dict[str, int] = {}
    for f in report.findings:
        by_severity[f.severity] = by_severity.get(f.severity, 0) + 1
    return {
        "title": report.title,
        "subtitle": getattr(report, "subtitle", None),
        "generated_at": to_jsonable(report.generated_at),
        "area_path": getattr(report, "area_path", None),
        "iteration_path": getattr(report, "iteration_path", None),
        "finding_count": len(findings),
        "by_severity": by_severity,
        "findings": findings,
        "markdown": report.to_markdown() if hasattr(report, "to_markdown") else None,
    }
