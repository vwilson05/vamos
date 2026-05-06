"""Sync command: diff today's markdown against ADO and apply changes via claude -p."""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from .ado import ADOClient, ADOError, WorkItem
from .config import Config
from .llm import call_claude, parse_json_response, render_prompt
from .markdown_io import Section, daily_path, parse_sections

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
_DEFAULT_GUIDELINES = (
    "No team-specific guidelines configured. Use ADO defaults for all fields. "
    "Set a sensible Priority (3 if unsure) and write a clear, imperative title."
)

log = logging.getLogger(__name__)

ALLOWED_OPS = {
    "update_state",
    "update_field",
    "add_comment",
    "create",
    "close",
    "remove",
    "link",
}

CLOSE_STATE_BY_TYPE = {
    "Bug": "Closed",
    "Task": "Closed",
    "User Story": "Closed",
    "Issue": "Closed",
    "Epic": "Closed",
    "Feature": "Closed",
}


@dataclass
class SyncResult:
    actions_proposed: int
    actions_executed: int
    actions_failed: int
    summary: str
    log_path: Path


def run(cfg: Config, dry_run: bool = False, day: date | None = None) -> SyncResult:
    day = day or date.today()
    md_path = daily_path(cfg.work_dir, day)
    if not md_path.exists():
        raise SystemExit(f"No markdown for {day}. Run SOD first: {md_path}")

    markdown = md_path.read_text(encoding="utf-8")
    sections = parse_sections(markdown)
    log.info("Sync: parsed %d sections from %s", len(sections), md_path)

    client = ADOClient(cfg.ado_org_url, cfg.ado_project, cfg.ado_pat, read_only=cfg.ado_read_only)

    # Build the union of: assigned items + items referenced by ID in markdown.
    assigned_ids = set(client.query_assigned(cfg.assigned_user_clause))
    md_ids = {s.work_item_id for s in sections if s.work_item_id is not None}
    fetch_ids = sorted(assigned_ids | md_ids)
    items = client.get_work_items(fetch_ids)
    items_by_id = {w.id: w for w in items}

    state = _load_state(cfg.state_dir, day)

    bundle_ado_state = [
        {
            "id": w.id,
            "type": w.type,
            "title": w.title,
            "state": w.state,
            "priority": w.priority,
            "assigned_to": w.assigned_to,
            "tags": w.tags,
            "url": w.url,
        }
        for w in items
    ]

    synced_hashes: dict[str, list[str]] = {
        str(tid): info.get("note_hashes", []) for tid, info in state.items()
    }

    guidelines_path = TEMPLATES_DIR / "new-ticket.md"
    ticket_guidelines = (
        guidelines_path.read_text(encoding="utf-8")
        if guidelines_path.exists()
        else _DEFAULT_GUIDELINES
    )

    prompt = render_prompt(
        "sync.md",
        ado_state=json.dumps(bundle_ado_state, indent=2),
        synced_hashes=json.dumps(synced_hashes, indent=2),
        markdown=markdown,
        ticket_guidelines=ticket_guidelines,
    )

    log.info("Sync: invoking claude -p (prompt %d chars)", len(prompt))
    raw = call_claude(prompt, claude_bin=cfg.claude_bin)
    plan = parse_json_response(raw)

    actions = plan.get("actions") or []
    summary = plan.get("summary") or ""

    results: list[dict[str, Any]] = []
    executed = 0
    failed = 0
    new_id_by_anchor: dict[str, int] = {}
    known_hashes_by_id: dict[int, set[str]] = {
        int(k): set(v) for k, v in synced_hashes.items() if k.isdigit()
    }

    for idx, action in enumerate(actions):
        op = action.get("op")
        if op not in ALLOWED_OPS:
            results.append({"index": idx, "action": action, "status": "skipped",
                            "reason": f"unknown op: {op}"})
            continue
        if dry_run:
            results.append({"index": idx, "action": action, "status": "dry-run"})
            continue
        try:
            outcome = _execute(client, action, items_by_id, sections, new_id_by_anchor,
                               known_hashes_by_id)
            if outcome.get("dedup_skip"):
                results.append({"index": idx, "action": action, "status": "skipped",
                                "reason": "comment already posted (hash match)"})
                continue
            executed += 1
            results.append({"index": idx, "action": action, "status": "ok", "outcome": outcome})
        except (ADOError, ValueError, KeyError) as exc:
            failed += 1
            results.append({"index": idx, "action": action, "status": "error",
                            "error": str(exc)})
            log.error("action %d failed: %s", idx, exc)

    if not dry_run and new_id_by_anchor:
        markdown = _rewrite_new_ids(markdown, new_id_by_anchor)
        md_path.write_text(markdown, encoding="utf-8")
        log.info("Sync: rewrote %s with %d new IDs", md_path, len(new_id_by_anchor))

    if not dry_run:
        for tid, hashes in known_hashes_by_id.items():
            entry = state.setdefault(tid, {})
            entry["note_hashes"] = sorted(hashes)
            entry["last_sync"] = datetime.now(timezone.utc).isoformat()
        _save_state(cfg.state_dir, day, state)

    log_path = _write_log(cfg, day, prompt, raw, results, summary, dry_run)

    return SyncResult(
        actions_proposed=len(actions),
        actions_executed=executed,
        actions_failed=failed,
        summary=summary,
        log_path=log_path,
    )


# ---- action execution ----

def _execute(
    client: ADOClient,
    action: dict[str, Any],
    items_by_id: dict[int, WorkItem],
    sections: list[Section],
    new_id_by_anchor: dict[str, int],
    known_hashes_by_id: dict[int, set[str]],
) -> dict[str, Any]:
    op = action["op"]

    if op == "update_state":
        wid = int(action["id"])
        target = action["to"]
        current = items_by_id.get(wid)
        if current and current.state == target:
            return {"noop": "state already matches"}
        updated = client.patch_fields(wid, {"System.State": target})
        items_by_id[wid] = updated
        return {"new_state": updated.state}

    if op == "update_field":
        wid = int(action["id"])
        field = action["field"]
        value = action["value"]
        current = items_by_id.get(wid)
        if current and current.raw_fields.get(field) == value:
            return {"noop": f"{field} already matches"}
        updated = client.patch_fields(wid, {field: value})
        items_by_id[wid] = updated
        return {"updated_field": field}

    if op == "add_comment":
        wid = int(action["id"])
        text = action["text"]
        if not text or not text.strip():
            return {"noop": "empty comment"}
        note_hash = hashlib.sha256(text.strip().encode("utf-8")).hexdigest()
        already = known_hashes_by_id.get(wid, set())
        if note_hash in already:
            return {"dedup_skip": True, "hash": note_hash}
        result = client.add_comment(wid, text)
        known_hashes_by_id.setdefault(wid, set()).add(note_hash)
        return {"comment_id": result.get("id"), "hash": note_hash}

    if op == "create":
        anchor = action.get("markdown_anchor", "")
        created = client.create_work_item(
            work_item_type=action["type"],
            title=action["title"],
            description=action.get("description"),
            priority=action.get("priority"),
            area_path=action.get("area_path"),
            iteration_path=action.get("iteration_path"),
            acceptance_criteria=action.get("acceptance_criteria"),
            tags=action.get("tags"),
            parent_id=action.get("parent_id"),
        )
        items_by_id[created.id] = created
        if anchor:
            new_id_by_anchor[anchor] = created.id
        link_results: list[dict[str, Any]] = []
        for link in action.get("links") or []:
            try:
                target = int(link["target_id"])
                rel = link.get("rel", "System.LinkTypes.Related")
                client.link_work_items(created.id, target, rel=rel)
                link_results.append({"target_id": target, "rel": rel, "ok": True})
            except (ADOError, ValueError, KeyError) as exc:
                link_results.append({"link": link, "ok": False, "error": str(exc)})
        return {
            "created_id": created.id,
            "type": created.type,
            "links": link_results,
        }

    if op == "close":
        wid = int(action["id"])
        current = items_by_id.get(wid)
        terminal = CLOSE_STATE_BY_TYPE.get(current.type if current else "", "Closed")
        if current and current.state == terminal:
            return {"noop": "already closed"}
        updated = client.patch_fields(wid, {"System.State": terminal})
        items_by_id[wid] = updated
        return {"new_state": updated.state}

    if op == "remove":
        wid = int(action["id"])
        updated = client.patch_fields(wid, {"System.State": "Removed"})
        items_by_id[wid] = updated
        return {"new_state": updated.state}

    if op == "link":
        source = int(action["id"])
        target = int(action["target_id"])
        rel = action.get("rel", "System.LinkTypes.Related")
        client.link_work_items(source, target, rel=rel)
        return {"linked": [source, target], "rel": rel}

    raise ValueError(f"unhandled op: {op}")


# ---- markdown rewriting ----

def _rewrite_new_ids(markdown: str, new_id_by_anchor: dict[str, int]) -> str:
    out = markdown
    for anchor, new_id in new_id_by_anchor.items():
        # Anchor looks like "[NEW] Some title". The heading line is `## [NEW] Some title`.
        anchor_clean = anchor.strip()
        if anchor_clean.startswith("["):
            heading_old = f"## {anchor_clean}"
        else:
            heading_old = f"## [NEW] {anchor_clean}"
        if heading_old not in out:
            log.warning("Could not find anchor %r to rewrite with id %d", heading_old, new_id)
            continue
        title_part = anchor_clean.split("]", 1)[-1].strip()
        heading_new = f"## [{new_id}] {title_part}"
        out = out.replace(heading_old, heading_new, 1)
    return out


# ---- state sidecar ----

def _state_path(state_dir: Path, day: date) -> Path:
    return state_dir / f"{day.isoformat()}.json"


def _load_state(state_dir: Path, day: date) -> dict[int, dict[str, Any]]:
    path = _state_path(state_dir, day)
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {int(k): v for k, v in raw.items()}


def _save_state(state_dir: Path, day: date, state: dict[int, dict[str, Any]]) -> None:
    path = _state_path(state_dir, day)
    serializable = {str(k): v for k, v in state.items()}
    path.write_text(json.dumps(serializable, indent=2), encoding="utf-8")


# ---- run log ----

def _write_log(
    cfg: Config,
    day: date,
    prompt: str,
    raw_response: str,
    results: list[dict[str, Any]],
    summary: str,
    dry_run: bool,
) -> Path:
    logs_dir = cfg.state_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = logs_dir / f"{day.isoformat()}-sync-{ts}{'-dry' if dry_run else ''}.json"
    path.write_text(
        json.dumps(
            {
                "day": day.isoformat(),
                "dry_run": dry_run,
                "summary": summary,
                "results": results,
                "raw_response": raw_response,
                "prompt": prompt,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return path
