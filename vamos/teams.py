"""Post plain-text messages to a Microsoft Teams webhook.

Supports both the legacy Incoming Webhook (MessageCard schema) and the new
Workflows / Power Automate webhooks (Adaptive Card schema). Auto-detects which
to use based on the webhook hostname.
"""
from __future__ import annotations

import logging
from urllib.parse import urlparse

import requests

log = logging.getLogger(__name__)

LEGACY_HOSTS = ("webhook.office.com", "outlook.office.com")


class TeamsError(RuntimeError):
    pass


def post(webhook_url: str, text: str, title: str | None = None, timeout: int = 30) -> None:
    if not webhook_url:
        raise TeamsError("TEAMS_WEBHOOK_URL is not set")

    host = (urlparse(webhook_url).hostname or "").lower()
    is_legacy = any(host.endswith(h) for h in LEGACY_HOSTS)

    if is_legacy:
        payload = _legacy_message_card(text, title)
    else:
        payload = _workflows_adaptive_card(text, title)

    resp = requests.post(webhook_url, json=payload, timeout=timeout)
    if not resp.ok:
        raise TeamsError(
            f"Teams webhook -> {resp.status_code}: {resp.text[:500]} "
            f"(host={host}, format={'MessageCard' if is_legacy else 'AdaptiveCard'})"
        )


def _legacy_message_card(text: str, title: str | None) -> dict:
    """MessageCard schema — used by the deprecated *.webhook.office.com endpoints."""
    body_text = "\n".join(
        line + "  " if line.strip() else "" for line in text.splitlines()
    )
    payload: dict = {
        "@type": "MessageCard",
        "@context": "https://schema.org/extensions",
        "text": body_text,
    }
    if title:
        payload["title"] = title
    return payload


def _workflows_adaptive_card(text: str, title: str | None) -> dict:
    """Adaptive Card schema — used by Workflows / Power Automate Teams webhooks.

    Each non-blank line becomes its own TextBlock so line layout is preserved
    exactly. Blank lines become spacing.
    """
    body: list[dict] = []
    if title:
        body.append(
            {"type": "TextBlock", "text": title, "weight": "Bolder", "size": "Medium", "wrap": True}
        )

    prev_was_blank = False
    for line in text.splitlines():
        if not line.strip():
            prev_was_blank = True
            continue
        body.append(
            {
                "type": "TextBlock",
                "text": line,
                "wrap": True,
                "spacing": "Medium" if prev_was_blank else "None",
            }
        )
        prev_was_blank = False

    return {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "type": "AdaptiveCard",
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "version": "1.4",
                    "body": body,
                },
            }
        ],
    }
