"""Open WebUI conversation logger for Jarvis (HA Assist).

Subscribes read-only to conversation.chat_log — never modifies the HA
Ollama conversation agent, Wyoming, Frigate, or MQTT config. Any Open
WebUI/Ollama HTTP failure is logged and never delays or alters the actual
spoken conversation response.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import voluptuous as vol

from homeassistant.components.conversation.chat_log import (
    ChatLogEventType,
    async_subscribe_chat_logs,
)
from homeassistant.components.persistent_notification import async_create as async_create_notification
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_call_later

from . import session as session_logic
from .const import DOMAIN
from .ollama_client import classify_same_topic
from .openwebui_client import append_chat, create_chat

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required("owui_url"): cv.string,
                vol.Required("owui_api_key"): cv.string,
                vol.Required("ollama_url"): cv.string,
                vol.Required("ollama_model"): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

_NOTIFICATION_ID = "owui_jarvis_logger_failure"


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Open WebUI Jarvis logger."""
    conf = config[DOMAIN]
    aiohttp_session = async_get_clientsession(hass)

    current: session_logic.SessionState | None = None
    seen_lengths: dict[str, int] = {}
    close_timer_cancel: Any = None
    # Serializes _handle_turn's body across concurrent chat_log events — this
    # is a shared household device, and the design deliberately uses one
    # global "current session" rather than per-conversation_id state, so
    # without this lock two genuinely concurrent turns (e.g. a second
    # Assist stream started while one is still mid-turn) could interleave
    # their mutation of `current` across the awaited HTTP calls below.
    turn_lock = asyncio.Lock()

    def _close_session() -> None:
        nonlocal current, close_timer_cancel
        if current is not None and current.any_failure:
            async_create_notification(
                hass,
                (
                    "A Jarvis conversation session ended without being fully "
                    "logged to Open WebUI — Open WebUI was unreachable for "
                    "at least one exchange during it. Check the Home "
                    "Assistant log for `owui_jarvis_logger` warnings."
                ),
                title="Jarvis → Open WebUI logging failed",
                notification_id=_NOTIFICATION_ID,
            )
        # Cancel any still-pending hard-cutoff timer for the session being
        # closed here — otherwise a mid-turn close (a new topic starting
        # while a session is still open) leaves the old timer armed, and it
        # can later fire and prematurely tear down a healthy successor
        # session that _schedule_close() has since armed its own timer for.
        if close_timer_cancel is not None:
            close_timer_cancel()
        current = None
        close_timer_cancel = None

    def _schedule_close() -> None:
        nonlocal close_timer_cancel
        if close_timer_cancel is not None:
            close_timer_cancel()

        @callback
        def _on_timer(_now: Any) -> None:
            _close_session()

        close_timer_cancel = async_call_later(
            hass, session_logic.SESSION_HARD_CUTOFF_SECONDS, _on_timer
        )

    async def _handle_turn(
        conversation_id: str, user_text: str, assistant_text: str, now: float
    ) -> None:
        nonlocal current

        async with turn_lock:
            gap = (now - current.last_turn_time) if current is not None else 0.0
            decision = session_logic.decide_grouping(current is not None, gap)

            if decision is session_logic.GroupingDecision.NEEDS_CLASSIFICATION:
                same_topic = await classify_same_topic(
                    aiohttp_session,
                    conf["ollama_url"],
                    conf["ollama_model"],
                    current.last_user_msg,
                    current.last_assistant_msg,
                    user_text,
                )
                decision = (
                    session_logic.GroupingDecision.APPEND
                    if same_topic
                    else session_logic.GroupingDecision.NEW
                )

            if decision is session_logic.GroupingDecision.NEW and current is not None:
                _close_session()

            if current is None:
                current = session_logic.SessionState(
                    owui_chat_id="",
                    title=session_logic.title_from_utterance(user_text),
                    last_turn_time=now,
                    last_user_msg=user_text,
                    last_assistant_msg=assistant_text,
                    last_history_current_id="",
                    any_failure=False,
                )

            # last_history_current_id is "" until a turn actually lands in Open
            # WebUI — that's true for a brand-new session and also for one whose
            # earlier create attempt(s) failed, so parentId correctly stays None
            # (no fabricated chain) until the first successful delivery.
            parent_id = current.last_history_current_id or None
            user_msg, assistant_msg = session_logic.new_message_pair(
                user_text, assistant_text, parent_id, now
            )

            if current.owui_chat_id:
                payload = session_logic.build_append_payload(user_msg, assistant_msg)
                delivered = await append_chat(
                    aiohttp_session, conf["owui_url"], conf["owui_api_key"], current.owui_chat_id, payload
                )
                if not delivered:
                    _LOGGER.warning("Failed to append to Open WebUI chat %s", current.owui_chat_id)
            else:
                payload = session_logic.build_new_chat_payload(current.title, user_msg, assistant_msg)
                chat_id = await create_chat(aiohttp_session, conf["owui_url"], conf["owui_api_key"], payload)
                delivered = chat_id is not None
                if delivered:
                    current.owui_chat_id = chat_id
                else:
                    _LOGGER.warning(
                        "Failed to create Open WebUI chat for Jarvis session (title: %r)", current.title
                    )

            if delivered:
                # Only advance the chain anchor when this turn actually landed in
                # Open WebUI — never point a future turn's parentId at a message
                # Open WebUI never received.
                current.last_history_current_id = assistant_msg["id"]
            else:
                current.any_failure = True

            current.last_turn_time = now
            current.last_user_msg = user_text
            current.last_assistant_msg = assistant_text

            _schedule_close()

    def _on_chat_log_event(conversation_id: str, event_type: str, data: dict) -> None:
        try:
            if event_type != ChatLogEventType.UPDATED:
                return
            content = data.get("chat_log", {}).get("content", [])
            last_seen = seen_lengths.get(conversation_id, 0)
            pair = session_logic.extract_new_turn(content, last_seen)
            seen_lengths[conversation_id] = len(content)
            if pair is None:
                return
            user_text, assistant_text = pair
            now = time.time()
            hass.async_create_task(_handle_turn(conversation_id, user_text, assistant_text, now))
        except Exception:  # noqa: BLE001 — this callback runs inline on the live
            # conversation path (HA's chat_log subscriber dispatch has no
            # try/except of its own); any exception escaping here would reach
            # the actual voice pipeline, which this component must never touch.
            _LOGGER.exception("Unexpected error in owui_jarvis_logger chat_log callback")

    async_subscribe_chat_logs(hass, _on_chat_log_event)
    _LOGGER.info("Open WebUI Jarvis logger set up, forwarding to %s", conf["owui_url"])
    return True
