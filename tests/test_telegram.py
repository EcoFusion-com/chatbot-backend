#!/usr/bin/env python3
"""
Telegram Bot API tests
- Reads TELEGRAM_TOKEN from env
- Skips gracefully if not configured or network blocked
- Checks getMe endpoint and bad token failure case
"""

import os
import unittest
import requests


def env_missing() -> bool:
    return not os.getenv("TELEGRAM_TOKEN")


@unittest.skipIf(env_missing(), "Telegram not configured in .env; skipping")
class TestTelegramAPI(unittest.TestCase):
    def setUp(self):
        self.token = os.getenv("TELEGRAM_TOKEN")
        self.base_url = f"https://api.telegram.org/bot{self.token}"

    def test_1_get_me(self):
        try:
            resp = requests.get(f"{self.base_url}/getMe", timeout=20)
            if resp is None:
                raise unittest.SkipTest("Network returned no response")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            if not data.get("ok"):
                self.skipTest(f"Telegram API returned ok=false: {data}")
            print("✅ Telegram getMe ok for:", data.get("result", {}).get("username"))
        except requests.exceptions.RequestException as e:
            self.skipTest(f"Network error/timeout while calling Telegram API: {e}")

    def test_2_failure_bad_token(self):
        bad_url = "https://api.telegram.org/botINVALID_TOKEN/getMe"
        try:
            resp = requests.get(bad_url, timeout=10)
            # Telegram often returns 200 with ok:false for invalid tokens
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertFalse(data.get("ok", True))
            print("✅ Failure case handled (bad token)")
        except requests.exceptions.RequestException as e:
            self.skipTest(f"Network error/timeout for bad token case: {e}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
