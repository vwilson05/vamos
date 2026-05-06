"""Report — first-class output object for team agents (hygiene, healthcheck, metrics).

A Report is a list of Findings plus metadata. Renderers turn it into markdown,
Teams/Slack-friendly text, or JSON for the UI.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Literal

Severity = Literal["blocker", "should-fix", "nit", "info", "praise"]

SEVERITY_RANK = {"blocker": 0, "should-fix": 1, "nit": 2, "info": 3, "praise": 4}
SEVERITY_LABEL = {
    "blocker": "[BLOCKER]",
    "should-fix": "[SHOULD-FIX]",
    "nit": "[NIT]",
    "info": "[INFO]",
    "praise": "[PRAISE]",
}
# Back-compat alias for any external consumer of the old name
SEVERITY_EMOJI = SEVERITY_LABEL


@dataclass
class Finding:
    rule_id: str
    severity: Severity
    message: str
    engineer: str | None = None
    ticket_id: int | None = None
    ticket_url: str | None = None
    ticket_title: str | None = None
    suggested_comment: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class Report:
    title: str
    findings: list[Finding]
    generated_at: datetime = field(default_factory=datetime.now)
    subtitle: str | None = None
    area_path: str | None = None
    iteration_path: str | None = None

    def by_engineer(self) -> dict[str, list[Finding]]:
        out: dict[str, list[Finding]] = {}
        for f in self.findings:
            key = f.engineer or "_team_"
            out.setdefault(key, []).append(f)
        return out

    def by_severity(self) -> dict[str, list[Finding]]:
        out: dict[str, list[Finding]] = {}
        for f in self.findings:
            out.setdefault(f.severity, []).append(f)
        return out

    @property
    def has_blockers(self) -> bool:
        return any(f.severity == "blocker" for f in self.findings)

    def to_markdown(self) -> str:
        from .boards import display_path
        lines: list[str] = []
        lines.append(f"# {self.title}")
        if self.subtitle:
            lines.append(f"_{self.subtitle}_")
        lines.append("")
        if self.area_path:
            lines.append(f"**Board:** {display_path(self.area_path)}")
        if self.iteration_path:
            disp = display_path(self.iteration_path)
            # Trim leading area path on plain string forms like "Foo\\Bar\\Sprint"
            if isinstance(self.iteration_path, str) and "\\" in self.iteration_path:
                disp = self.iteration_path.split("\\")[-1]
            lines.append(f"**Iteration:** {disp}")
        lines.append(f"**Generated:** {self.generated_at.strftime('%Y-%m-%d %H:%M')}")
        lines.append("")

        sev = self.by_severity()
        total = len(self.findings)
        if total == 0:
            lines.append("✅ **All clear** — no findings.")
            return "\n".join(lines)

        roll = []
        for s in ("blocker", "should-fix", "nit", "info", "praise"):
            n = len(sev.get(s, []))
            if n:
                roll.append(f"{SEVERITY_LABEL[s]} {n} {s}")
        lines.append("**Summary:** " + " · ".join(roll))
        lines.append("")
        lines.append("---")
        lines.append("")

        eng_groups = self.by_engineer()
        engineers = sorted(k for k in eng_groups if k != "_team_")
        if "_team_" in eng_groups:
            lines.append("## Team-level")
            lines.append("")
            for f in sorted(eng_groups["_team_"], key=lambda x: SEVERITY_RANK[x.severity]):
                lines.append(_render_finding_md(f))
            lines.append("")

        for eng in engineers:
            efs = sorted(eng_groups[eng], key=lambda x: SEVERITY_RANK[x.severity])
            lines.append(f"## {eng}")
            lines.append("")
            for f in efs:
                lines.append(_render_finding_md(f))
            lines.append("")

        return "\n".join(lines)

    def to_text(self) -> str:
        lines: list[str] = []
        lines.append(f"📋 **{self.title}** — {self.generated_at.strftime('%Y-%m-%d %H:%M')}")
        if self.subtitle:
            lines.append(f"_{self.subtitle}_")

        sev = self.by_severity()
        if not self.findings:
            lines.append("✅ All clear — no findings.")
            return "\n".join(lines)

        roll = []
        for s in ("blocker", "should-fix", "nit", "info", "praise"):
            n = len(sev.get(s, []))
            if n:
                roll.append(f"{SEVERITY_LABEL[s]} {n}")
        lines.append("Summary: " + " · ".join(roll))
        lines.append("")

        eng_groups = self.by_engineer()
        for eng in sorted(eng_groups):
            label = "Team" if eng == "_team_" else eng
            efs = sorted(eng_groups[eng], key=lambda x: SEVERITY_RANK[x.severity])
            lines.append(f"**{label}** — {len(efs)} finding(s)")
            for f in efs[:5]:
                tid = f"[{f.ticket_id}] " if f.ticket_id else ""
                lines.append(f"  {SEVERITY_LABEL[f.severity]} {tid}{f.message}")
            if len(efs) > 5:
                lines.append(f"  …and {len(efs) - 5} more")
            lines.append("")

        return "\n".join(lines)

    def to_json(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "subtitle": self.subtitle,
            "area_path": self.area_path,
            "iteration_path": self.iteration_path,
            "generated_at": self.generated_at.isoformat(),
            "findings": [asdict(f) for f in self.findings],
            "summary": {s: len(fs) for s, fs in self.by_severity().items()},
        }


def _render_finding_md(f: Finding) -> str:
    head = f"- **{SEVERITY_LABEL[f.severity]}** {f.message}"
    if f.ticket_id:
        if f.ticket_url:
            head += f" — [#{f.ticket_id}]({f.ticket_url})"
        else:
            head += f" — #{f.ticket_id}"
        if f.ticket_title:
            head += f" *{f.ticket_title[:60]}*"
    return head
