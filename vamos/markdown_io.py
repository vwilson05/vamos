"""Render and parse the daily work markdown file."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from html import unescape
from pathlib import Path

from .ado import WorkItem

HEADING_RE = re.compile(r"^##\s+\[(?P<id>[^\]]+)\]\s*(?P<title>.+?)\s*$")
META_RE = re.compile(r"<!--\s*(?P<body>.+?)\s*-->")


@dataclass
class Section:
    raw_id: str  # "12345" or "NEW"
    title: str
    meta: dict[str, str] = field(default_factory=dict)
    body: str = ""

    @property
    def is_new(self) -> bool:
        return self.raw_id.upper() == "NEW"

    @property
    def work_item_id(self) -> int | None:
        try:
            return int(self.raw_id)
        except ValueError:
            return None


def daily_path(work_dir: Path, day: date | None = None) -> Path:
    day = day or date.today()
    return work_dir / f"{day.isoformat()}.md"


def render(items: list[WorkItem], day: date | None = None) -> str:
    day = day or date.today()
    lines: list[str] = [f"# {day.isoformat()} — Daily Work", ""]
    if not items:
        lines += [
            "_No assigned work items._",
            "",
            "Add new work below. Use `## [NEW] Title` to create a new ticket on next sync.",
            "",
        ]
        return "\n".join(lines)

    lines.append(
        "_Edit this file throughout the day. Sync runs every 3 hours and at EOD._"
    )
    lines.append("")
    lines.append("Conventions:")
    lines.append("- Change a `state:` value in the metadata to move the ticket")
    lines.append("- Anything you write under `### Notes` becomes an ADO comment on next sync")
    lines.append(
        "- Add a new section starting with `## [NEW] <title>` to create a ticket "
        "(set `type:` and `priority:` in the metadata comment)"
    )
    lines.append(
        "- Tag a section with `[CLOSE]` or `[DELETE]` in the title to close/remove on next sync"
    )
    lines.append("")

    for item in items:
        lines.extend(_render_section(item))
    return "\n".join(lines).rstrip() + "\n"


def _render_section(item: WorkItem) -> list[str]:
    meta_parts = [
        f"type: {item.type}",
        f"state: {item.state}",
        f"priority: {item.priority if item.priority is not None else '-'}",
    ]
    if item.tags:
        meta_parts.append(f"tags: {', '.join(item.tags)}")
    if item.url:
        meta_parts.append(f"url: {item.url}")

    out = [
        f"## [{item.id}] {item.title}",
        f"<!-- {' | '.join(meta_parts)} -->",
        "",
        "### Notes",
        "",
        "",
        "---",
        "",
    ]
    return out


def read_sections(path: Path) -> list[Section]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    return parse_sections(text)


def parse_sections(text: str) -> list[Section]:
    sections: list[Section] = []
    current: Section | None = None
    body_lines: list[str] = []

    for line in text.splitlines():
        match = HEADING_RE.match(line)
        if match:
            if current is not None:
                current.body = _clean_body(body_lines)
                sections.append(current)
            current = Section(raw_id=match.group("id"), title=match.group("title").strip())
            body_lines = []
            continue
        if current is None:
            continue
        meta_match = META_RE.search(line)
        if meta_match and not current.meta:
            current.meta = _parse_meta(meta_match.group("body"))
            continue
        body_lines.append(line)

    if current is not None:
        current.body = _clean_body(body_lines)
        sections.append(current)

    return sections


def _parse_meta(body: str) -> dict[str, str]:
    meta: dict[str, str] = {}
    for chunk in body.split("|"):
        if ":" not in chunk:
            continue
        key, _, value = chunk.partition(":")
        meta[key.strip().lower()] = unescape(value.strip())
    return meta


def _clean_body(lines: list[str]) -> str:
    body = "\n".join(lines).strip()
    # Trim trailing horizontal rule that separates sections.
    if body.endswith("---"):
        body = body[: -len("---")].rstrip()
    return body
