"""Streaming logs — capture a logger's output and pipe it to a NiceGUI ui.log element.

Each long-running agent call uses `run_with_logs(label, fn, *args, **kwargs)`,
which returns the result and surfaces every log line in real time.
"""
from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import Callable

from nicegui import ui


class _QueueHandler(logging.Handler):
    def __init__(self, queue: asyncio.Queue):
        super().__init__()
        self.queue = queue

    def emit(self, record: logging.LogRecord) -> None:
        try:
            ts = time.strftime("%H:%M:%S", time.localtime(record.created))
            msg = f"{ts}  {record.levelname[:4]:>4}  {record.getMessage()}"
            try:
                self.queue.put_nowait(msg)
            except asyncio.QueueFull:
                pass
        except Exception:
            pass


async def run_with_logs(
    label: str,
    fn: Callable,
    *args,
    log_namespace: str = "vamos",
    level: str = "INFO",
    **kwargs,
):
    """Run `fn(*args, **kwargs)` in a thread while streaming its log output.

    A ui.expansion + ui.log block is created in the current UI context. The
    expansion auto-closes on success and stays open + red on failure.
    Returns whatever `fn` returns; re-raises any exception fn raised.
    """
    target = logging.getLogger(log_namespace)
    queue: asyncio.Queue = asyncio.Queue()
    handler = _QueueHandler(queue)
    handler.setLevel(getattr(logging, level, logging.INFO))
    prev_level = target.level
    target.addHandler(handler)
    target.setLevel(getattr(logging, level, logging.INFO))

    expansion = ui.expansion(label, icon="play_circle").classes(
        "w-full bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 "
        "rounded-lg my-2"
    )
    expansion.value = True  # open while running
    with expansion:
        log_el = ui.log(max_lines=200).classes(
            "h-64 w-full font-mono text-xs bg-slate-900 text-slate-200 rounded-md p-3"
        )

    error: Exception | None = None
    drain_running = True

    async def drain_logs():
        while drain_running:
            try:
                msg = queue.get_nowait()
                log_el.push(msg)
            except asyncio.QueueEmpty:
                await asyncio.sleep(0.15)

    drain_task = asyncio.create_task(drain_logs())

    try:
        result = await asyncio.to_thread(fn, *args, **kwargs)
    except Exception as exc:
        error = exc
        result = None
    finally:
        # Drain anything left in the queue before tearing down
        await asyncio.sleep(0.2)
        while True:
            try:
                msg = queue.get_nowait()
                log_el.push(msg)
            except asyncio.QueueEmpty:
                break
        drain_running = False
        drain_task.cancel()
        target.removeHandler(handler)
        target.setLevel(prev_level)

    if error:
        expansion.props("expand-icon=error").classes("border-rose-500 dark:border-rose-700")
        expansion._props["label"] = f"{label} — failed"
        expansion.update()
        ui.notify(f"{label} failed: {error}", color="negative", position="top")
        raise error

    expansion._props["label"] = f"{label} — done"
    expansion.value = False
    expansion.update()
    return result
