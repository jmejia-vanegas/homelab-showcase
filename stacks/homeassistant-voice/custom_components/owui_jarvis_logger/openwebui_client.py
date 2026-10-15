"""Open WebUI REST client — create/append chat entries.

Contract verified manually (see Task 1 of the implementation plan and the
Phase 1 curl test in the design doc): POST /api/v1/chats/new creates a
sidebar-visible chat; POST /api/v1/chats/{id} merges new history.messages
into the existing chat server-side.
"""
from __future__ import annotations

import logging
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

_TIMEOUT = aiohttp.ClientTimeout(total=10)


async def create_chat(
    session: aiohttp.ClientSession, base_url: str, api_key: str, payload: dict[str, Any]
) -> str | None:
    """POST /api/v1/chats/new. Returns the new chat id, or None on failure."""
    url = f"{base_url.rstrip('/')}/api/v1/chats/new"
    try:
        async with session.post(
            url,
            json=payload,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=_TIMEOUT,
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()
            return data.get("id") if isinstance(data, dict) else None
    except (aiohttp.ClientError, TimeoutError, ValueError) as err:
        _LOGGER.warning("Open WebUI create_chat failed: %s", err)
        return None


async def append_chat(
    session: aiohttp.ClientSession,
    base_url: str,
    api_key: str,
    chat_id: str,
    payload: dict[str, Any],
) -> bool:
    """POST /api/v1/chats/{id}. Returns True on success."""
    url = f"{base_url.rstrip('/')}/api/v1/chats/{chat_id}"
    try:
        async with session.post(
            url,
            json=payload,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=_TIMEOUT,
        ) as resp:
            resp.raise_for_status()
            return True
    except (aiohttp.ClientError, TimeoutError) as err:
        _LOGGER.warning("Open WebUI append_chat failed for chat %s: %s", chat_id, err)
        return False
