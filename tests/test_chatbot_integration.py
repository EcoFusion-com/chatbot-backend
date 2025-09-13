#!/usr/bin/env python3
"""
Chatbot multi-turn integration tests via REST channel
- Requires Rasa server at http://localhost:5005 and actions at http://localhost:5055
- Sends multi-turn dialogs and checks for semantic correctness (snippets)
- Skips if servers are not reachable
"""

import unittest
import requests

RASA_BASE = "http://localhost:5005"
REST_WEBHOOK = f"{RASA_BASE}/webhooks/rest/webhook"
STATUS_URL = f"{RASA_BASE}/status"


def rasa_up() -> bool:
    try:
        r = requests.get(STATUS_URL, timeout=5)
        return r.status_code == 200
    except Exception:
        return False


@unittest.skipUnless(rasa_up(), "Rasa server not running; skipping integration test")
class TestChatbotIntegration(unittest.TestCase):
    def _send(self, text: str, sender: str = "integration_user"):
        r = requests.post(REST_WEBHOOK, json={"sender": sender, "message": text}, timeout=15)
        self.assertEqual(r.status_code, 200, f"Bad status: {r.status_code}")
        return r.json()

    def _assert_contains_any(self, messages, snippets):
        body = "\n".join(m.get("text", "") for m in messages if isinstance(m, dict))
        self.assertTrue(any(s.lower() in body.lower() for s in snippets), f"Expected one of {snippets} in response: {body}")

    def test_1_service_greeting_flow(self):
        msgs = self._send("hello")
        self._assert_contains_any(msgs, ["hi", "hello", "how can i help", "assist you"])        

    def test_2_quote_flow(self):
        msgs = self._send("I need a quote for an AI project")
        self._assert_contains_any(msgs, ["quote", "estimate", "budget", "timeline"])        

    def test_3_meeting_booking(self):
        msgs = self._send("I want to book a meeting")
        self._assert_contains_any(msgs, ["calendar", "booking", "consultation", "link"])        

    def test_4_handoff(self):
        msgs = self._send("I need a human agent")
        # Either acknowledge or mention agent
        self._assert_contains_any(msgs, ["agent", "human", "handoff"])        


if __name__ == "__main__":
    unittest.main(verbosity=2)
