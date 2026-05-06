"""vamos.hygiene — enforces ADO board standards (Jeff's spec, May 5 2026).

Each rule is a function: (snapshot, cfg) -> list[Finding]. The runner loads
the rule registry, runs each rule against a single TeamSnapshot, aggregates
into a Report, and posts to Teams/Slack.

Live mode (HYGIENE_LIVE_MODE=true + --auto-comment) optionally posts a single
nudge comment per finding on the offending ticket. Default is report-only.
"""
from .runner import run, run_rules
from . import clean_runner

__all__ = ["run", "run_rules", "clean_runner"]
