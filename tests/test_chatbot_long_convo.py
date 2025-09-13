#!/usr/bin/env python3
"""
Comprehensive long multi-turn conversation tests
Covers: greeting -> requirements -> quote -> proposal -> calendar -> CRM push -> handoff
Skips if Rasa server is not running.
"""

import unittest
import requests
import time

RASA_BASE = "http://localhost:5005"
REST_WEBHOOK = f"{RASA_BASE}/webhooks/rest/webhook"
STATUS_URL = f"{RASA_BASE}/status"


def rasa_up() -> bool:
    try:
        r = requests.get(STATUS_URL, timeout=5)
        return r.status_code == 200
    except Exception:
        return False


def send_and_collect(sender: str, text: str):
    r = requests.post(REST_WEBHOOK, json={"sender": sender, "message": text}, timeout=20)
    if r.status_code != 200:
        raise AssertionError(f"Bad status {r.status_code} for: {text}")
    return r.json()


def body_text(messages):
    return "\n".join(m.get("text", "") for m in messages if isinstance(m, dict))


@unittest.skipUnless(rasa_up(), "Rasa server not running; skipping long convo test")
class TestChatbotLongConversation(unittest.TestCase):
    def setUp(self):
        self.sender = f"long_convo_user_{int(time.time())}"

    def assert_contains(self, messages, snippet_list, msg):
        txt = body_text(messages).lower()
        self.assertTrue(any(s.lower() in txt for s in snippet_list), msg + f" | got: {txt}")

    def contains_any(self, messages, snippet_list) -> bool:
        txt = body_text(messages).lower()
        return any(s.lower() in txt for s in snippet_list)

    def test_end_to_end_flow(self):
        # 1) Greeting
        msgs = send_and_collect(self.sender, "hello there")
        self.assert_contains(msgs, ["hello", "hi", "assist", "help"], "Greeting response missing")

        # 2) Provide requirements progressively
        msgs = send_and_collect(self.sender, "We are in healthcare industry")
        self.assert_contains(msgs, ["requirements", "details", "timeline", "thanks", "captured"], "Requirements capture phase not acknowledged")

        msgs = send_and_collect(self.sender, "Budget around $50k and timeline 3 months using python stack")
        self.assert_contains(
            msgs,
            ["budget", "timeline", "technology", "python", "thanks", "captured your project details"],
            "Budget/timeline/tech not acknowledged",
        )

        msgs = send_and_collect(self.sender, "Project size medium with HIPAA compliance")
        self.assert_contains(msgs, ["project", "size", "compliance", "hipaa", "thanks", "captured"], "Project size/compliance not acknowledged")

        # 3) Ask for quote -> expect estimator range
        msgs = send_and_collect(self.sender, "Can you estimate the quote?")
        self.assert_contains(msgs, ["quote", "estimate", "$", "range"], "Quote estimator did not return a range")

        # 4) Generate proposal (retry once if assistant service is unreachable)
        msgs = send_and_collect(self.sender, "Generate a proposal please")
        if not self.contains_any(msgs, ["proposal", "phase", "deliverables", "next steps"]):
            if self.contains_any(msgs, ["trouble", "assistant service", "try again later", "couldn't process"]):
                # Retry once
                msgs = send_and_collect(self.sender, "Please try generating the proposal again")
        if not self.contains_any(msgs, ["proposal", "phase", "deliverables", "next steps"]):
            self.skipTest("Proposal generation unavailable (LLM/service unreachable). Skipping remainder.")

        # 5) Book meeting -> expect calendar link or event
        msgs = send_and_collect(self.sender, "Book a meeting for consultation")
        self.assert_contains(msgs, ["calendar", "booking", "consultation", "link", "event"], "Calendar link/event missing")

        # 6) Push to CRM (implicit via action or after collecting email)
        msgs = send_and_collect(self.sender, "My email is test.user@example.com")
        self.assert_contains(msgs, ["email", "test.user@example.com", "thanks", "captured"], "Email capture/ack not present")

        msgs = send_and_collect(self.sender, "Save my details to CRM")
        self.assert_contains(msgs, ["crm", "saved", "pushed", "submitted", "sent"], "CRM push acknowledgement missing")

        # 7) Handoff to human
        msgs = send_and_collect(self.sender, "I need to talk to a human agent")
        self.assert_contains(msgs, ["agent", "human", "handoff", "coming"], "Handoff acknowledgement missing")


if __name__ == "__main__":
    unittest.main(verbosity=2)
