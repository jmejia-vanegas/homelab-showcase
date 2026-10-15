"""Local-Ollama topic-continuity classification for session grouping.

Only called when a new turn's gap since the last one falls strictly between
APPEND_GAP_SECONDS and SESSION_HARD_CUTOFF_SECONDS (session.py) — fast-path
appends and hard-cutoff-forced new sessions never reach this module.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import aiohttp

_LOGGER = logging.getLogger(__name__)

CONTINUITY_PROMPT_TEMPLATE = (
    "Previous exchange:\n"
    "User: {last_user}\n"
    "Assistant: {last_assistant}\n\n"
    "New user message: {new_user}\n\n"
    "Is the new message a continuation of the same topic/conversation, or "
    "a new, unrelated request? Answer with exactly one word: SAME or "
    "UNRELATED."
)


def build_continuity_prompt(last_user: str, last_assistant: str, new_user: str) -> str:
    """Build the classification prompt sent to the local Ollama model."""
    return CONTINUITY_PROMPT_TEMPLATE.format(
        last_user=last_user, last_assistant=last_assistant, new_user=new_user
    )


def parse_continuity_response(raw_response_text: str) -> bool:
    """True means 'same topic, append'. Defaults to True on any ambiguous
    or unparseable answer — see the failure-mode rationale in the plan's
    Global Constraints: an unwanted extra chat is a smaller cost than an
    unwanted session split.
    """
    return "UNRELATED" not in raw_response_text.strip().upper()


async def classify_same_topic(
    session: aiohttp.ClientSession,
    ollama_url: str,
    model: str,
    last_user: str,
    last_assistant: str,
    new_user: str,
) -> bool:
    """Ask the local Ollama model whether new_user continues the previous
    exchange's topic. Returns True (append) on any network/parse failure.
    """
    import aiohttp

    prompt = build_continuity_prompt(last_user, last_assistant, new_user)
    url = f"{ollama_url.rstrip('/')}/api/generate"
    payload = {"model": model, "prompt": prompt, "stream": False}
    try:
        async with session.post(
            url, json=payload, timeout=aiohttp.ClientTimeout(total=15)
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()
    except (aiohttp.ClientError, TimeoutError, ValueError) as err:
        _LOGGER.warning(
            "Ollama continuity classification failed, defaulting to same-topic: %s", err
        )
        return True
    if not isinstance(data, dict):
        _LOGGER.warning(
            "Ollama continuity classification returned a non-dict response, defaulting to same-topic"
        )
        return True
    return parse_continuity_response(str(data.get("response", "")))
