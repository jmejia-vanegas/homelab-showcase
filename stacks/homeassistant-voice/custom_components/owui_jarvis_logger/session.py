"""Pure grouping/session/payload logic for the Open WebUI Jarvis logger.

No Home Assistant or network imports on purpose — keeps this testable with
plain stdlib unittest. Append-payload shape: only `history.messages` is
sent on append, never the legacy top-level `messages` list — Task 1's
manual curl check (live GET after an append) confirmed Open WebUI's server
merges purely from `history.messages` and doesn't read or update the
legacy list at all, so resending it would be dead weight.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from enum import Enum

APPEND_GAP_SECONDS = 2 * 60
SESSION_HARD_CUTOFF_SECONDS = 60 * 60


class GroupingDecision(Enum):
    """What to do with a newly-arrived turn."""

    APPEND = "append"
    NEW = "new"
    NEEDS_CLASSIFICATION = "needs_classification"


def decide_grouping(has_current_session: bool, gap_seconds: float) -> GroupingDecision:
    """Decide whether a new turn appends to the current session, starts a
    new one outright, or needs an Ollama topic-continuity check to decide.
    """
    if not has_current_session:
        return GroupingDecision.NEW
    if gap_seconds <= APPEND_GAP_SECONDS:
        return GroupingDecision.APPEND
    if gap_seconds > SESSION_HARD_CUTOFF_SECONDS:
        return GroupingDecision.NEW
    return GroupingDecision.NEEDS_CLASSIFICATION


@dataclass
class SessionState:
    """In-memory state for the single 'current' Open WebUI logging session."""

    owui_chat_id: str
    title: str
    last_turn_time: float
    last_user_msg: str
    last_assistant_msg: str
    last_history_current_id: str
    any_failure: bool = False


def extract_new_turn(content: list[dict], last_seen_length: int) -> tuple[str, str] | None:
    """From a HA ChatLog.as_dict()['content'] list, return the (user_text,
    assistant_text) pair for entries added since last_seen_length, or None
    if a complete new user+assistant pair isn't present yet (e.g. only a
    tool-call-only assistant entry has arrived so far).
    """
    user_text: str | None = None
    assistant_text: str | None = None
    for entry in content[last_seen_length:]:
        role = entry.get("role")
        text = entry.get("content")
        if role == "user" and text:
            user_text = text
        elif role == "assistant" and text:
            assistant_text = text
    if user_text and assistant_text:
        return user_text, assistant_text
    return None


def new_message_pair(
    user_text: str, assistant_text: str, parent_id: str | None, now: float | None = None
) -> tuple[dict, dict]:
    """Build a (user_message, assistant_message) pair of Open WebUI
    history-message dicts, chained by parentId off `parent_id`."""
    now = now if now is not None else time.time()
    user_id = str(uuid.uuid4())
    assistant_id = str(uuid.uuid4())
    user_msg = {
        "id": user_id,
        "parentId": parent_id,
        "childrenIds": [assistant_id],
        "role": "user",
        "content": user_text,
        "timestamp": int(now),
    }
    assistant_msg = {
        "id": assistant_id,
        "parentId": user_id,
        "childrenIds": [],
        "role": "assistant",
        "content": assistant_text,
        "timestamp": int(now),
    }
    return user_msg, assistant_msg


def build_new_chat_payload(title: str, user_msg: dict, assistant_msg: dict) -> dict:
    """Request body for POST /api/v1/chats/new."""
    messages = [user_msg, assistant_msg]
    return {
        "chat": {
            "title": title,
            "history": {
                "currentId": assistant_msg["id"],
                "messages": {m["id"]: m for m in messages},
            },
            "messages": messages,
        }
    }


def build_append_payload(user_msg: dict, assistant_msg: dict) -> dict:
    """Request body for POST /api/v1/chats/{id}. Only the new turn's
    `history.messages` entries are sent — the server merges them into the
    existing history by id (Chats.merge_history); the legacy top-level
    `messages` list is never read or updated by append, so it's omitted
    (confirmed via Task 1's manual curl check).
    """
    return {
        "chat": {
            "history": {
                "currentId": assistant_msg["id"],
                "messages": {user_msg["id"]: user_msg, assistant_msg["id"]: assistant_msg},
            },
        }
    }


def title_from_utterance(user_text: str, max_len: int = 60) -> str:
    """Chat title = first user utterance, whitespace-collapsed, truncated."""
    text = " ".join(user_text.split())
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"
