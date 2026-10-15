"""Unit tests for the pure grouping/session/payload logic in session.py.

Run: python3 -m unittest test_session -v
(from this directory — no HA install or third-party deps required)
"""
import unittest

import session


class TestDecideGrouping(unittest.TestCase):
    def test_no_current_session_is_always_new(self):
        self.assertEqual(
            session.decide_grouping(has_current_session=False, gap_seconds=0),
            session.GroupingDecision.NEW,
        )

    def test_short_gap_appends(self):
        self.assertEqual(
            session.decide_grouping(has_current_session=True, gap_seconds=60),
            session.GroupingDecision.APPEND,
        )

    def test_gap_at_append_boundary_appends(self):
        self.assertEqual(
            session.decide_grouping(
                has_current_session=True, gap_seconds=session.APPEND_GAP_SECONDS
            ),
            session.GroupingDecision.APPEND,
        )

    def test_gap_just_over_append_boundary_needs_classification(self):
        self.assertEqual(
            session.decide_grouping(
                has_current_session=True, gap_seconds=session.APPEND_GAP_SECONDS + 1
            ),
            session.GroupingDecision.NEEDS_CLASSIFICATION,
        )

    def test_gap_at_hard_cutoff_needs_classification(self):
        self.assertEqual(
            session.decide_grouping(
                has_current_session=True,
                gap_seconds=session.SESSION_HARD_CUTOFF_SECONDS,
            ),
            session.GroupingDecision.NEEDS_CLASSIFICATION,
        )

    def test_gap_over_hard_cutoff_is_new(self):
        self.assertEqual(
            session.decide_grouping(
                has_current_session=True,
                gap_seconds=session.SESSION_HARD_CUTOFF_SECONDS + 1,
            ),
            session.GroupingDecision.NEW,
        )


class TestExtractNewTurn(unittest.TestCase):
    def test_no_new_content_returns_none(self):
        content = [{"role": "system", "content": ""}]
        self.assertIsNone(session.extract_new_turn(content, last_seen_length=1))

    def test_new_user_and_assistant_pair_extracted(self):
        content = [
            {"role": "system", "content": ""},
            {"role": "user", "content": "turn on the lights"},
            {"role": "assistant", "content": "done"},
        ]
        self.assertEqual(
            session.extract_new_turn(content, last_seen_length=1),
            ("turn on the lights", "done"),
        )

    def test_tool_call_only_assistant_entry_ignored_until_final_text(self):
        content = [
            {"role": "system", "content": ""},
            {"role": "user", "content": "turn on the lights"},
            {"role": "assistant", "agent_id": "x"},  # tool call, no content
            {"role": "assistant", "content": "done"},
        ]
        self.assertEqual(
            session.extract_new_turn(content, last_seen_length=1),
            ("turn on the lights", "done"),
        )

    def test_only_user_so_far_returns_none(self):
        content = [
            {"role": "system", "content": ""},
            {"role": "user", "content": "turn on the lights"},
        ]
        self.assertIsNone(session.extract_new_turn(content, last_seen_length=1))

    def test_already_seen_content_not_reextracted(self):
        content = [
            {"role": "system", "content": ""},
            {"role": "user", "content": "turn on the lights"},
            {"role": "assistant", "content": "done"},
        ]
        self.assertIsNone(session.extract_new_turn(content, last_seen_length=3))


class TestMessagePairAndPayloads(unittest.TestCase):
    def test_new_message_pair_chains_by_parent_id(self):
        user_msg, assistant_msg = session.new_message_pair(
            "hello", "hi there", parent_id=None, now=1000.0
        )
        self.assertEqual(user_msg["role"], "user")
        self.assertEqual(user_msg["content"], "hello")
        self.assertIsNone(user_msg["parentId"])
        self.assertEqual(user_msg["childrenIds"], [assistant_msg["id"]])
        self.assertEqual(assistant_msg["role"], "assistant")
        self.assertEqual(assistant_msg["parentId"], user_msg["id"])
        self.assertEqual(assistant_msg["childrenIds"], [])
        self.assertEqual(user_msg["timestamp"], 1000)

    def test_new_message_pair_chains_off_given_parent(self):
        user_msg, _assistant_msg = session.new_message_pair(
            "again", "sure", parent_id="prev-id", now=1000.0
        )
        self.assertEqual(user_msg["parentId"], "prev-id")

    def test_build_new_chat_payload_shape(self):
        user_msg, assistant_msg = session.new_message_pair(
            "hello", "hi there", parent_id=None, now=1000.0
        )
        payload = session.build_new_chat_payload("hello", user_msg, assistant_msg)
        self.assertEqual(payload["chat"]["title"], "hello")
        self.assertEqual(payload["chat"]["history"]["currentId"], assistant_msg["id"])
        self.assertEqual(
            set(payload["chat"]["history"]["messages"].keys()),
            {user_msg["id"], assistant_msg["id"]},
        )
        self.assertEqual(payload["chat"]["messages"], [user_msg, assistant_msg])

    def test_build_append_payload_shape(self):
        user_msg1, assistant_msg1 = session.new_message_pair(
            "first", "first reply", parent_id=None, now=1000.0
        )
        user_msg2, assistant_msg2 = session.new_message_pair(
            "second", "second reply", parent_id=assistant_msg1["id"], now=1010.0
        )
        payload = session.build_append_payload(user_msg2, assistant_msg2)
        self.assertEqual(payload["chat"]["history"]["currentId"], assistant_msg2["id"])
        self.assertEqual(
            set(payload["chat"]["history"]["messages"].keys()),
            {user_msg2["id"], assistant_msg2["id"]},
        )
        self.assertNotIn("messages", payload["chat"])


class TestTitleFromUtterance(unittest.TestCase):
    def test_short_utterance_unchanged(self):
        self.assertEqual(session.title_from_utterance("turn on the lights"), "turn on the lights")

    def test_long_utterance_truncated_with_ellipsis(self):
        text = "a" * 100
        title = session.title_from_utterance(text, max_len=60)
        self.assertEqual(len(title), 60)
        self.assertTrue(title.endswith("…"))

    def test_whitespace_collapsed(self):
        self.assertEqual(session.title_from_utterance("turn   on\n  the lights"), "turn on the lights")


if __name__ == "__main__":
    unittest.main()
