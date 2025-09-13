#!/usr/bin/env python3
"""
WhatsApp Business API tests
- Reads WHATSAPP_TOKEN and WHATSAPP_PHONE_ID from env
- Skips gracefully if not configured
- Checks Graph API connectivity and failure case
"""

import os
import unittest
import requests

API_VERSION = os.getenv("WHATSAPP_API_VERSION", "v17.0")


def env_missing() -> bool:
    return not (os.getenv("WHATSAPP_TOKEN") and os.getenv("WHATSAPP_PHONE_ID"))


@unittest.skipIf(env_missing(), "WhatsApp not configured in .env; skipping")
class TestWhatsAppAPI(unittest.TestCase):
    def setUp(self):
        self.token = os.getenv("WHATSAPP_TOKEN")
        self.phone_id = os.getenv("WHATSAPP_PHONE_ID")
        self.base_url = f"https://graph.facebook.com/{API_VERSION}/{self.phone_id}"
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def test_1_connectivity(self):
        resp = requests.get(self.base_url, headers=self.headers, timeout=15)
        self.assertIn(resp.status_code, (200, 400), f"Unexpected status: {resp.status_code}")
        print("✅ WhatsApp API reachable (status:", resp.status_code, ")")

    def test_2_failure_case_bad_token(self):
        bad_headers = {"Authorization": "Bearer invalid_token"}
        resp = requests.get(self.base_url, headers=bad_headers, timeout=15)
        self.assertIn(resp.status_code, (400, 401, 403))
        print("✅ Failure case handled (bad token -> status:", resp.status_code, ")")


if __name__ == "__main__":
    unittest.main(verbosity=2)
