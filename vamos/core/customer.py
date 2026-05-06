"""Customer extraction heuristic for HaloMD ticket titles.

HaloMD tickets typically prefix the customer name in the title:
  'Vituity — Investigate First Response Date Source'
  'UHC: 835 enrichment'
  '[Northstar] Code Review and Push to Prod'

This module extracts the customer prefix when present, falling back
to '(no customer)' when the title doesn't match a known pattern.

Customer list comes from .ado-metrics.yml or env CUSTOMER_LIST,
with a sensible default of well-known HaloMD customers.
"""
from __future__ import annotations

import os
import re
from collections import Counter

DEFAULT_CUSTOMERS = [
    "UHC", "Vituity", "MEMS", "Northstar", "NorthStar", "Optum",
    "Concord", "EVRA", "Unico", "Adventist", "Cigna", "Afterglow",
    "Global Anesthesia", "Titans", "Vituity Anesthesia",
    "ATC", "BQ", "HHER", "ProLink", "Arbit", "Halo",
]

_PREFIX_RE = re.compile(r"^\s*\[?([A-Za-z][A-Za-z0-9 ]{1,30})\]?\s*[—\-:|>]\s*")


def known_customers() -> list[str]:
    raw = os.getenv("CUSTOMER_LIST", "").strip()
    if raw:
        return [c.strip() for c in raw.split(",") if c.strip()]
    return list(DEFAULT_CUSTOMERS)


def extract(title: str, customers: list[str] | None = None) -> str:
    """Pick the customer prefix from a ticket title. Returns '' if unclear."""
    customers = customers or known_customers()
    if not title:
        return ""
    m = _PREFIX_RE.match(title)
    if not m:
        return ""
    candidate = m.group(1).strip()
    # Direct match (case-insensitive)
    for c in customers:
        if candidate.lower() == c.lower() or candidate.lower().startswith(c.lower() + " "):
            return c
        if c.lower() in candidate.lower() and len(c) > 3:
            return c
    # If it looks like a name (Title Case, 1-3 words), accept as a customer
    if re.match(r"^[A-Z][A-Za-z0-9]+(?:\s+[A-Z][A-Za-z0-9]+){0,2}$", candidate):
        return candidate
    return ""


def group_by_customer(items, title_attr: str = "title") -> dict[str, list]:
    """Group ticket-like objects by extracted customer; '(no customer)' when none found."""
    customers = known_customers()
    out: dict[str, list] = {}
    for it in items:
        title = getattr(it, title_attr, "") or ""
        key = extract(title, customers) or "(no customer)"
        out.setdefault(key, []).append(it)
    return out


def top_customers(items, title_attr: str = "title", n: int = 10) -> list[tuple[str, int]]:
    """Return [(customer, count), ...] sorted descending."""
    grouped = group_by_customer(items, title_attr)
    counts = Counter({c: len(v) for c, v in grouped.items() if c != "(no customer)"})
    return counts.most_common(n)
