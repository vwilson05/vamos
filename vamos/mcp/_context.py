"""Server-process singleton: cfg + write-capable ADOClient.

The MCP server is a long-lived stdio process. We load Config once at startup
and reuse a single ADOClient (HTTP keep-alive on the underlying requests
session). Tools call get_ctx() instead of plumbing cfg/client through every
signature.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from ..ado import ADOClient
from ..config import Config, load as load_config

log = logging.getLogger(__name__)


@dataclass
class Ctx:
    cfg: Config
    client: ADOClient


_ctx: Ctx | None = None


def get_ctx() -> Ctx:
    global _ctx
    if _ctx is None:
        cfg = load_config()
        # MCP server needs writes for start_work / post_comment / close_ticket.
        # Honor ADO_READ_ONLY only if the user explicitly set it.
        client = ADOClient(
            cfg.ado_org_url,
            cfg.ado_project,
            cfg.ado_pat,
            read_only=cfg.ado_read_only,
        )
        _ctx = Ctx(cfg=cfg, client=client)
        log.info("mcp ctx: loaded cfg for %s/%s (read_only=%s)",
                 cfg.ado_org_url, cfg.ado_project, cfg.ado_read_only)
    return _ctx


def reset_ctx() -> None:
    """Test seam — drop the cached context so the next get_ctx() reloads."""
    global _ctx
    _ctx = None
