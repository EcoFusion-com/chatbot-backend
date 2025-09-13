#!/usr/bin/env python3
"""
Debug script to check environment variables and integrations
"""

import os
from pathlib import Path
import requests

# Load .env file
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / ".env"
    load_dotenv(env_path)
    print(f"✅ Loaded .env from: {env_path}")
except Exception as e:
    print(f"❌ Failed to load .env: {e}")

print("\n🔍 Environment Variables Check:")
print("=" * 50)

variables = [
    "GOOGLE_CALENDAR_API_KEY",
    "GOOGLE_CALENDAR_ID", 
    "GOOGLE_CALENDAR_CREDENTIALS_FILE",
    "WHATSAPP_TOKEN",
    "WHATSAPP_PHONE_ID",
    "TELEGRAM_TOKEN",
    "HF_API_KEY",
    "ADMIN_EMAIL"
]

for var in variables:
    value = os.getenv(var)
    if value:
        display_value = value[:10] + "..." if len(value) > 10 else value
        print(f"✅ {var}: {display_value}")
    else:
        print(f"❌ {var}: Not set")

# ==============================
# GOOGLE CALENDAR
# ==============================
print("\n🔍 Testing Google Calendar Integration:")
print("=" * 50)

api_key = os.getenv("GOOGLE_CALENDAR_API_KEY")
calendar_id = os.getenv("GOOGLE_CALENDAR_ID")
credentials_file = os.getenv("GOOGLE_CALENDAR_CREDENTIALS_FILE")

print(f"API Key exists: {bool(api_key)}")
print(f"Calendar ID exists: {bool(calendar_id)}")
print(f"Credentials file exists: {bool(credentials_file)}")

if credentials_file:
    cred_path = Path(credentials_file)
    print(f"Credentials file path exists: {cred_path.exists()}")
    if cred_path.exists():
        print(f"Credentials file size: {cred_path.stat().st_size} bytes")

print("\n🔍 Testing Calendar Event Creation:")
print("=" * 50)
try:
    payload = {"sender": "test_user", "message": "I want to schedule a consultation"}
    response = requests.post(
        "http://localhost:5005/webhooks/rest/webhook",
        json=payload,
        timeout=10
    )
    if response.status_code == 200:
        print("✅ Calendar test message sent successfully")
        print(f"📝 Response: {response.json()}")
    else:
        print(f"❌ Failed to send test message: {response.status_code}")
except Exception as e:
    print(f"❌ Error testing calendar: {e}")

# ==============================
# WHATSAPP
# ==============================
print("\n🔍 Testing WhatsApp Integration:")
print("=" * 50)

wa_token = os.getenv("WHATSAPP_TOKEN")
wa_phone = os.getenv("WHATSAPP_PHONE_ID")

if wa_token and wa_phone:
    url = f"https://graph.facebook.com/v19.0/{wa_phone}/messages"
    headers = {"Authorization": f"Bearer {wa_token}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "to": "YOUR_TEST_NUMBER",  # ⚠️ replace with your number with country code
        "type": "text",
        "text": {"body": "Hello from Eco Fusion Debug Test 🚀"}
    }
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=10)
        if r.status_code == 200:
            print("✅ WhatsApp test message sent")
            print(r.json())
        else:
            print(f"❌ WhatsApp API error: {r.status_code} - {r.text}")
    except Exception as e:
        print(f"❌ Error testing WhatsApp: {e}")
else:
    print("❌ WhatsApp credentials missing in .env")

# ==============================
# TELEGRAM
# ==============================
print("\n🔍 Testing Telegram Integration:")
print("=" * 50)

telegram_token = os.getenv("TELEGRAM_TOKEN")
telegram_bot = os.getenv("TELEGRAM_BOT_USERNAME")

if telegram_token:
    test_url = f"https://api.telegram.org/bot{telegram_token}/getMe"
    try:
        r = requests.get(test_url, timeout=10)
        if r.status_code == 200:
            print("✅ Telegram bot is reachable")
            print(r.json())
        else:
            print(f"❌ Telegram API error: {r.status_code} - {r.text}")
    except Exception as e:
        print(f"❌ Error testing Telegram: {e}")
else:
    print("❌ Telegram credentials missing in .env")

# ==============================
# HF MODEL API
# ==============================
print("\n🔍 Testing Hugging Face Model API:")
print("=" * 50)

hf_key = os.getenv("HF_API_KEY")
hf_model = os.getenv("HF_MODEL_NAME", "gpt2")

if hf_key:
    try:
        r = requests.post(
            f"https://api-inference.huggingface.co/models/{hf_model}",
            headers={"Authorization": f"Bearer {hf_key}"},
            json={"inputs": "Hello from Eco Fusion debug script"},
            timeout=15
        )
        if r.status_code == 200:
            print("✅ HF model responded")
            print(r.json())
        else:
            print(f"❌ HF API error: {r.status_code} - {r.text}")
    except Exception as e:
        print(f"❌ Error testing HF API: {e}")
else:
    print("❌ HF_API_KEY not set")
