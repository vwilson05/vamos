"""NiceGUI pages — each module registers a route via @ui.page on import.
The order of imports below determines side-effect registration order.
"""
from . import home, my_day, inbox, team_status, pr_queue, brief, settings as settings_page, help_page  # noqa: F401
