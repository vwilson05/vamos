"""Start of day: pull assigned work items into today's markdown."""
from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta
from pathlib import Path

from .ado import ADOClient
from .config import Config
from .markdown_io import daily_path, render

log = logging.getLogger(__name__)


def cleanup_previous_days(cfg: Config, current_day: date) -> None:
    """Delete logs and markdown files from previous days."""
    log.info("SOD: Starting cleanup of previous days' files")

    # Pattern for matching date-based files (YYYY-MM-DD format)
    date_pattern = re.compile(r'(\d{4}-\d{2}-\d{2})')

    cleanup_count = 0

    # Cleanup work directory (daily markdown files)
    if cfg.work_dir.exists():
        for file_path in cfg.work_dir.glob('*.md'):
            match = date_pattern.search(file_path.name)
            if match:
                file_date = datetime.strptime(match.group(1), '%Y-%m-%d').date()
                if file_date < current_day:
                    try:
                        file_path.unlink()
                        log.debug(f"Deleted work file: {file_path}")
                        cleanup_count += 1
                    except Exception as e:
                        log.warning(f"Failed to delete {file_path}: {e}")

    # Cleanup state directory
    if cfg.state_dir.exists():
        # Clean up EOD files (YYYY-MM-DD-eod.txt)
        for file_path in cfg.state_dir.glob('*-eod.txt'):
            match = date_pattern.search(file_path.name)
            if match:
                file_date = datetime.strptime(match.group(1), '%Y-%m-%d').date()
                if file_date < current_day:
                    try:
                        file_path.unlink()
                        log.debug(f"Deleted EOD file: {file_path}")
                        cleanup_count += 1
                    except Exception as e:
                        log.warning(f"Failed to delete {file_path}: {e}")

        # Clean up healthcheck files (YYYY-MM-DD-healthcheck.md)
        for file_path in cfg.state_dir.glob('*-healthcheck.md'):
            match = date_pattern.search(file_path.name)
            if match:
                file_date = datetime.strptime(match.group(1), '%Y-%m-%d').date()
                if file_date < current_day:
                    try:
                        file_path.unlink()
                        log.debug(f"Deleted healthcheck file: {file_path}")
                        cleanup_count += 1
                    except Exception as e:
                        log.warning(f"Failed to delete {file_path}: {e}")

        # Clean up run state files (YYYY-MM-DD-run.json)
        for file_path in cfg.state_dir.glob('*-run.json'):
            match = date_pattern.search(file_path.name)
            if match:
                file_date = datetime.strptime(match.group(1), '%Y-%m-%d').date()
                if file_date < current_day:
                    try:
                        file_path.unlink()
                        log.debug(f"Deleted run state file: {file_path}")
                        cleanup_count += 1
                    except Exception as e:
                        log.warning(f"Failed to delete {file_path}: {e}")

        # Clean up sync state files (YYYY-MM-DD.json)
        for file_path in cfg.state_dir.glob('????-??-??.json'):
            match = date_pattern.search(file_path.name)
            if match:
                file_date = datetime.strptime(match.group(1), '%Y-%m-%d').date()
                if file_date < current_day:
                    try:
                        file_path.unlink()
                        log.debug(f"Deleted sync state file: {file_path}")
                        cleanup_count += 1
                    except Exception as e:
                        log.warning(f"Failed to delete {file_path}: {e}")

        # Clean up sync log files in logs directory
        logs_dir = cfg.state_dir / 'logs'
        if logs_dir.exists():
            for file_path in logs_dir.glob('*-sync-*.json'):
                match = date_pattern.search(file_path.name)
                if match:
                    file_date = datetime.strptime(match.group(1), '%Y-%m-%d').date()
                    if file_date < current_day:
                        try:
                            file_path.unlink()
                            log.debug(f"Deleted sync log: {file_path}")
                            cleanup_count += 1
                        except Exception as e:
                            log.warning(f"Failed to delete {file_path}: {e}")

    log.info(f"SOD: Cleanup completed. Deleted {cleanup_count} file(s) from previous days")


def run(cfg: Config, force: bool = False, day: date | None = None) -> Path:
    day = day or date.today()

    # Cleanup previous days' files when starting a new day (if enabled)
    if cfg.sod_cleanup_enabled:
        cleanup_previous_days(cfg, day)
    else:
        log.info("SOD: Cleanup is disabled. Set SOD_CLEANUP_ENABLED=true to enable automatic cleanup.")

    path = daily_path(cfg.work_dir, day)
    if path.exists() and not force:
        log.info("SOD: %s already exists. Use --force to overwrite.", path)
        return path

    client = ADOClient(cfg.ado_org_url, cfg.ado_project, cfg.ado_pat, read_only=cfg.ado_read_only)
    items = client.get_assigned_work_items(cfg.assigned_user_clause)
    log.info("SOD: pulled %d items from ADO", len(items))

    rendered = render(items, day=day)
    path.write_text(rendered, encoding="utf-8")
    log.info("SOD: wrote %s", path)
    return path
