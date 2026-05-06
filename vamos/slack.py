"""Post plain-text messages to a Slack webhook.

Supports both traditional Incoming Webhooks (/services/) and the newer
Workflow webhooks (/triggers/). Auto-detects which to use based on the
webhook URL pattern.
"""
from __future__ import annotations

import logging
from urllib.parse import urlparse

import requests

log = logging.getLogger(__name__)


class SlackError(RuntimeError):
    pass


def post(webhook_url: str, text: str, title: str | None = None, timeout: int = 30) -> None:
    if not webhook_url:
        raise SlackError("SLACK_WEBHOOK_URL is not set")

    path = urlparse(webhook_url).path
    is_workflow = "/triggers/" in path

    if is_workflow:
        payload = _workflow_webhook(text, title)
    else:
        payload = _traditional_webhook(text, title)

    resp = requests.post(webhook_url, json=payload, timeout=timeout)
    if not resp.ok:
        raise SlackError(
            f"Slack webhook -> {resp.status_code}: {resp.text[:500]} "
            f"(format={'Workflow' if is_workflow else 'Traditional'})"
        )


def _workflow_webhook(text: str, title: str | None) -> dict:
    """Workflow webhook format — simple JSON with text field.

    Workflow webhooks (/triggers/) expect a simple payload.
    Combine title and text into a single message.
    """
    if title:
        message = f"*{title}*\n\n{text}"
    else:
        message = text

    return {"text": message}


def _traditional_webhook(text: str, title: str | None) -> dict:
    """Traditional Incoming Webhook format — supports richer Block Kit.

    Uses Block Kit format for better presentation.
    Each non-blank line becomes its own text element.
    """
    blocks: list[dict] = []

    if title:
        blocks.append(
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": title,
                    "emoji": True
                }
            }
        )

    # Split text into sections, preserving line breaks
    # Group consecutive non-blank lines into sections
    lines = text.splitlines()
    current_section_lines: list[str] = []

    for line in lines:
        if not line.strip():
            # Blank line - flush current section
            if current_section_lines:
                blocks.append(
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "\n".join(current_section_lines)
                        }
                    }
                )
                current_section_lines = []
        else:
            current_section_lines.append(line)

    # Flush remaining lines
    if current_section_lines:
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "\n".join(current_section_lines)
                }
            }
        )

    return {"blocks": blocks}
