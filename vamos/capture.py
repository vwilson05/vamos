"""Quick capture — append a [NEW] section to today's daily markdown.

Use it when something hits during a meeting and you don't want to context-switch
to ADO. The next sync run will turn it into a real ticket per templates/new-ticket.md.
"""
from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

from .config import Config
from .markdown_io import daily_path

log = logging.getLogger(__name__)


def run(cfg: Config, text: str, customer: str | None = None,
        priority: int | None = None, day: date | None = None) -> Path:
    """Append a [NEW] section to the day's MD; create the file if missing."""
    day = day or date.today()
    md_path = daily_path(cfg.work_dir, day)
    if not md_path.exists():
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(f"# {day.isoformat()}\n\n", encoding="utf-8")

    title = text.split("\n", 1)[0].strip()[:120] or "Captured note"
    body = text.strip()

    meta_bits = []
    if customer:
        meta_bits.append(f"customer: {customer}")
    if priority:
        meta_bits.append(f"priority: {priority}")
    meta_line = " | ".join(meta_bits) if meta_bits else ""

    section_lines: list[str] = []
    section_lines.append(f"\n## [NEW] {title}")
    if meta_line:
        section_lines.append(f"<!-- {meta_line} -->")
    section_lines.append("")
    section_lines.append("### Notes")
    section_lines.append("")
    section_lines.append(body)
    section_lines.append("")

    with md_path.open("a", encoding="utf-8") as fh:
        fh.write("\n".join(section_lines))

    log.info("capture: appended [NEW] '%s' to %s", title, md_path)
    return md_path
