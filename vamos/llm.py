"""Wrapper around `claude -p` headless invocation."""
from __future__ import annotations

import json
import logging
import re
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


class LLMError(RuntimeError):
    pass


def render_prompt(template_name: str, **kwargs) -> str:
    template = (PROMPTS_DIR / template_name).read_text(encoding="utf-8")
    # Use simple {placeholder} substitution. Escape literal braces by doubling them in the template.
    for key, value in kwargs.items():
        template = template.replace(f"{{{key}}}", value)
    return template


def call_claude(prompt: str, claude_bin: str = "claude", timeout: int = 600) -> str:
    """Run `claude -p` with the prompt on stdin, return the model's text response."""
    cmd = [claude_bin, "-p", "--output-format", "json"]
    log.debug("Invoking %s (prompt %d chars)", " ".join(cmd), len(prompt))
    if len(prompt) > 10000:
        log.warning("Large prompt (%d chars) may cause timeout or empty response", len(prompt))
    try:
        proc = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise LLMError(
            f"Could not find {claude_bin!r}. Set CLAUDE_BIN in .env or add Claude Code to PATH."
        ) from exc
    if proc.returncode != 0:
        raise LLMError(f"claude exited {proc.returncode}: {proc.stderr.strip()[:1000]}")

    raw = proc.stdout.strip()
    if not raw:
        raise LLMError("claude returned empty output")

    try:
        envelope = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LLMError(f"claude output was not JSON envelope: {raw[:500]}") from exc

    if envelope.get("is_error"):
        raise LLMError(f"claude reported error: {envelope.get('result') or envelope}")

    result = envelope.get("result")
    if not isinstance(result, str):
        raise LLMError(f"claude envelope missing 'result' string: {envelope}")
    if not result.strip():
        raise LLMError(
            f"claude returned empty result. "
            f"This may indicate the prompt was too complex, token limit was hit, "
            f"or Claude refused to respond. Envelope: {envelope}"
        )
    return result


def parse_json_response(text: str) -> dict:
    """Parse JSON from a model response.

    Tolerates: leading/trailing prose, fenced code blocks anywhere in the text,
    or a bare JSON object somewhere in the response. Returns the first valid
    JSON object found.
    """
    # Log the full response for debugging
    log.debug("Raw response to parse (first 1000 chars): %s", text[:1000])

    candidates: list[str] = []

    fence = re.search(r"```(?:json)?\s*(\{.+?\})\s*```", text, re.DOTALL)
    if fence:
        candidates.append(fence.group(1))
        log.debug("Found JSON in code fence")

    # Fall back to the first balanced top-level JSON object.
    balanced = _first_balanced_object(text)
    if balanced:
        candidates.append(balanced)
        log.debug("Found balanced JSON object")

    candidates.append(text.strip())

    last_err: Exception | None = None
    for i, cand in enumerate(candidates):
        if not cand:
            continue
        try:
            log.debug("Trying candidate %d (first 200 chars): %s", i, cand[:200])
            return json.loads(cand)
        except json.JSONDecodeError as exc:
            log.debug("Candidate %d failed: %s", i, exc)
            last_err = exc
            continue
    snippet = text[:500] if text else "(empty)"
    raise LLMError(
        f"Model response was not JSON. "
        f"Response length: {len(text)} chars. "
        f"First 500 chars: {snippet}"
    ) from last_err


def _first_balanced_object(text: str) -> str:
    """Return the first {...} block whose braces balance, ignoring quoted strings."""
    start = text.find("{")
    if start < 0:
        return ""
    depth = 0
    in_str = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return ""
