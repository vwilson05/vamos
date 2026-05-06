"""Dependencies — render a ticket's parent/child/blocking relationships.

This is the MVP version: a flat list grouped by relation type, with one
hop in each direction. Reads via ADOClient.get_work_item_relations.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .ado import ADOClient

# Relation rels we surface (from ADO's link types)
REL_LABELS = {
    "System.LinkTypes.Hierarchy-Forward": "Children",
    "System.LinkTypes.Hierarchy-Reverse": "Parent",
    "System.LinkTypes.Dependency-Forward": "Blocks",
    "System.LinkTypes.Dependency-Reverse": "Blocked by",
    "System.LinkTypes.Related": "Related",
    "System.LinkTypes.Duplicate-Forward": "Duplicates",
    "System.LinkTypes.Duplicate-Reverse": "Duplicate of",
}


@dataclass
class Dep:
    rel_label: str
    target_id: int
    title: str
    state: str
    url: str


def fetch(client: ADOClient, work_item_id: int) -> list[Dep]:
    rels = client.get_work_item_relations(work_item_id)
    target_ids: list[int] = []
    rel_for_id: dict[int, str] = {}
    for r in rels:
        rel = r.get("rel", "")
        if rel not in REL_LABELS:
            continue
        url = r.get("url", "")
        m = re.search(r"/workItems/(\d+)$", url)
        if not m:
            continue
        tid = int(m.group(1))
        target_ids.append(tid)
        rel_for_id[tid] = REL_LABELS[rel]

    if not target_ids:
        return []

    items = client.get_work_items(target_ids)
    out: list[Dep] = []
    for w in items:
        out.append(Dep(
            rel_label=rel_for_id.get(w.id, "Related"),
            target_id=w.id,
            title=w.title,
            state=w.state,
            url=w.url,
        ))
    # Group order: Parent, Blocked by, Blocks, Children, Related, Duplicates
    order = ["Parent", "Blocked by", "Blocks", "Children", "Related", "Duplicates", "Duplicate of"]
    out.sort(key=lambda d: (order.index(d.rel_label) if d.rel_label in order else 99, d.target_id))
    return out


def render_text(work_item_id: int, deps: list[Dep]) -> str:
    if not deps:
        return f"#{work_item_id} — no linked work items."
    lines = [f"## Dependencies for #{work_item_id}", ""]
    last_label = None
    for d in deps:
        if d.rel_label != last_label:
            lines.append(f"**{d.rel_label}:**")
            last_label = d.rel_label
        lines.append(f"- [#{d.target_id}]({d.url}) {d.title}  ·  {d.state}")
    return "\n".join(lines)
