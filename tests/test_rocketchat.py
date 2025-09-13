#!/usr/bin/env python3
import unittest


@unittest.skip("Rocket.Chat is not used in this project configuration")
class TestRocketChatWebhook(unittest.TestCase):
    def test_skip(self):
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
