"""People — engineer identity normalization.

ADO surfaces the same human under multiple identifiers (display name,
email, OIDCONFLICT_UpnReuse_..., admin variants). This module collapses
those into one canonical name so per-engineer reports group correctly.
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Iterable

# Strip ADO's UPN-conflict prefix and admin suffixes
_OIDC_RE = re.compile(r"^OIDCONFLICT_UpnReuse_[a-f0-9-]+_")
_ADMIN_SUFFIX_RE = re.compile(r"[-.]?[Aa]dmi?n?$")
_EMAIL_RE = re.compile(r"^([^@]+)@.+$")


def canonical(identifier: str | None) -> str:
    """Best-effort normalization of an ADO 'assigned_to' / author string.

    Examples:
      'Louis Mangiacapra-Admin'                    -> 'louis mangiacapra'
      'Louis.Mangiacapra.adm@halomd.com'           -> 'louis mangiacapra'
      'OIDCONFLICT_UpnReuse_..._Jeff.Jordan@x.com' -> 'jeff jordan'
    """
    if not identifier:
        return ""
    s = identifier.strip()
    s = _OIDC_RE.sub("", s)
    m = _EMAIL_RE.match(s)
    if m:
        s = m.group(1)
    s = s.replace(".", " ").replace("_", " ").replace("-", " ")
    s = _ADMIN_SUFFIX_RE.sub("", s).strip()
    return " ".join(s.lower().split())


def display_name(identifier: str | None) -> str:
    """Title-case display form of the canonical name."""
    canon = canonical(identifier)
    return " ".join(p.capitalize() for p in canon.split()) if canon else "(unassigned)"


def group_by_person(items: Iterable, key=lambda x: x.assigned_to) -> dict[str, list]:
    """Group items by canonical person id. Returns {display_name: [items]}."""
    by_canon: dict[str, list] = defaultdict(list)
    raw_for_canon: dict[str, str] = {}
    for it in items:
        raw = key(it)
        canon = canonical(raw)
        by_canon[canon].append(it)
        # Keep the longest non-email raw form to use as display
        if canon not in raw_for_canon or (
            raw and "@" not in raw and len(raw) > len(raw_for_canon[canon])
        ):
            raw_for_canon[canon] = raw or ""

    out: dict[str, list] = {}
    for canon, group in by_canon.items():
        if not canon:
            out["(unassigned)"] = group
            continue
        # Prefer a clean display name from the raw if it looks like one,
        # otherwise rebuild from canonical.
        raw = raw_for_canon[canon]
        if raw and "@" not in raw and "OIDCONFLICT" not in raw:
            disp = _ADMIN_SUFFIX_RE.sub("", raw).strip()
        else:
            disp = display_name(raw)
        out[disp] = group
    return out
