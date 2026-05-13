"""reminders — advisory board-wide recommendations.

Sibling to `hygiene` (strict standards) and `at_risk` (risk surfacing).
Reminders are softer: "you sent the workbook — close the ticket?",
"P1 sitting in To Do for 3 days — anyone want to pick it up?".

CLI:    vamos reminders [--skip-post|--send] [--channel slack|teams] [--comment-tickets]
MCP:    get_reminders()  (read-only)
        send_reminders(confirm=True)  (gated)
"""
from .runner import run

__all__ = ["run"]
