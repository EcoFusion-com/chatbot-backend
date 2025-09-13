"""
Eco Fusion Chatbot - Google Calendar Integration Tests
------------------------------------------------------
Run this file with:  python test_calendar.py

This validates your service account credentials and basic
Google Calendar operations: list, create, and delete events.
"""

import os
import unittest
from datetime import datetime, timedelta

from google.oauth2 import service_account
from googleapiclient.discovery import build

# Path to your credentials file
SERVICE_ACCOUNT_FILE = os.path.join(os.getcwd(), "google-calendar-credentials.json")
SCOPES = ["https://www.googleapis.com/auth/calendar"]

class TestGoogleCalendar(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Load credentials
        if not os.path.exists(SERVICE_ACCOUNT_FILE):
            raise FileNotFoundError(f"Service account file not found: {SERVICE_ACCOUNT_FILE}")
        
        cls.credentials = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES
        )
        cls.service = build("calendar", "v3", credentials=cls.credentials)
        cls.calendar_id = "primary"


    def test_2_list_calendars(self):
        """Ensure service account can list calendars."""
        calendar_list = self.service.calendarList().list().execute()
        self.assertIn("items", calendar_list, "No calendars found")
        print("✅ Calendars accessible:", [c["id"] for c in calendar_list["items"]])

    def test_3_create_event(self):
        """Create a temporary test event."""
        event = {
            "summary": "Eco Fusion Test Event",
            "description": "Testing Google Calendar API integration.",
            "start": {"dateTime": (datetime.utcnow() + timedelta(minutes=5)).isoformat() + "Z"},
            "end": {"dateTime": (datetime.utcnow() + timedelta(minutes=65)).isoformat() + "Z"},
        }

        created_event = (
            self.service.events()
            .insert(calendarId=self.calendar_id, body=event)
            .execute()
        )

        self.__class__.event_id = created_event["id"]
        print("✅ Event created:", created_event["htmlLink"])
        self.assertIsNotNone(created_event.get("id"), "Event creation failed")

    def test_4_list_events(self):
        """List events and check our test event exists."""
        events_result = (
            self.service.events()
            .list(calendarId=self.calendar_id, maxResults=10, singleEvents=True, orderBy="startTime")
            .execute()
        )
        events = events_result.get("items", [])
        event_ids = [e["id"] for e in events]
        self.assertIn(self.__class__.event_id, event_ids, "Test event not found in calendar")
        print("✅ Event found in calendar list.")

    def test_5_delete_event(self):
        """Delete the temporary test event."""
        self.service.events().delete(
            calendarId=self.calendar_id, eventId=self.__class__.event_id
        ).execute()
        print("✅ Test event deleted successfully.")

if __name__ == "__main__":
    unittest.main(verbosity=2)
