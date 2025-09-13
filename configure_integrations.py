#!/usr/bin/env python3
"""
Eco Fusion Chatbot - Integration Configuration Helper
This script helps you configure WhatsApp, Telegram, and Google Calendar integrations
"""

import os
import sys
from pathlib import Path

def print_header(title):
    print(f"\n{'='*60}")
    print(f"🔧 {title}")
    print(f"{'='*60}")

def print_step(step_num, description):
    print(f"\n📋 Step {step_num}: {description}")

def check_env_file():
    """Check if .env file exists and show current configuration"""
    env_file = Path(".env")
    
    if not env_file.exists():
        print_header("ENVIRONMENT SETUP")
        print("❌ No .env file found!")
        print_step(1, "Create .env file")
        print("Copy env.example to .env:")
        print("   cp env.example .env")
        print("\nThen edit .env with your actual credentials.")
        return False
    
    print_header("CURRENT CONFIGURATION")
    print("✅ .env file found")
    
    # Read and display current config
    with open(env_file, 'r') as f:
        content = f.read()
    
    # Check key integrations
    integrations = {
        "Google Calendar": ["GOOGLE_CALENDAR_API_KEY", "GOOGLE_CALENDAR_ID", "GOOGLE_CALENDAR_CREDENTIALS_FILE"],
        "WhatsApp": ["WHATSAPP_TOKEN", "WHATSAPP_PHONE_ID"],
        "Telegram": ["TELEGRAM_TOKEN"],
        "Hugging Face": ["HF_API_KEY"],
        "Email": ["ADMIN_EMAIL", "SMTP_USER", "SMTP_PASS"]
    }
    
    for integration, vars in integrations.items():
        print(f"\n🔍 {integration}:")
        for var in vars:
            if var in content:
                # Check if it's configured (not placeholder)
                lines = content.split('\n')
                for line in lines:
                    if line.startswith(f"{var}="):
                        value = line.split('=', 1)[1].strip()
                        if value and not value.startswith('your_') and value != 'your-email@example.com':
                            print(f"   ✅ {var}: Configured")
                        else:
                            print(f"   ❌ {var}: Not configured")
                        break
            else:
                print(f"   ❌ {var}: Missing")
    
    return True

def google_calendar_setup():
    """Guide for Google Calendar setup"""
    print_header("GOOGLE CALENDAR SETUP")
    
    print("Google Calendar API requires OAuth2 authentication, not just an API key.")
    print("You have two options:")
    
    print_step(1, "Option A: Service Account (Recommended)")
    print("1. Go to https://console.cloud.google.com/")
    print("2. Create a new project or select existing")
    print("3. Enable Google Calendar API")
    print("4. Create a Service Account:")
    print("   - Go to 'APIs & Services' > 'Credentials'")
    print("   - Click 'Create Credentials' > 'Service Account'")
    print("5. Download the JSON credentials file")
    print("6. Add to your .env file:")
    print("   GOOGLE_CALENDAR_CREDENTIALS_FILE=path/to/your/credentials.json")
    print("   GOOGLE_CALENDAR_ID=your-email@gmail.com")
    
    print_step(2, "Option B: API Key (Limited)")
    print("1. Go to https://console.cloud.google.com/")
    print("2. Create API key")
    print("3. Add to your .env file:")
    print("   GOOGLE_CALENDAR_API_KEY=your_api_key_here")
    print("   GOOGLE_CALENDAR_ID=your-email@gmail.com")
    print("\n⚠️  Note: API keys have limited functionality for Calendar API")

def whatsapp_setup():
    """Guide for WhatsApp setup"""
    print_header("WHATSAPP BUSINESS API SETUP")
    
    print_step(1, "Create WhatsApp Business App")
    print("1. Go to https://developers.facebook.com/")
    print("2. Create a new app or use existing")
    print("3. Add WhatsApp Business API product")
    print("4. Get your credentials:")
    print("   - Phone Number ID")
    print("   - Access Token")
    
    print_step(2, "Configure in .env")
    print("Add to your .env file:")
    print("   WHATSAPP_TOKEN=your_whatsapp_business_token")
    print("   WHATSAPP_PHONE_ID=your_whatsapp_phone_id")
    
    print_step(3, "Alternative: Use Rocket.Chat")
    print("If you prefer, you can use Rocket.Chat as a hub:")
    print("1. Set up Rocket.Chat server")
    print("2. Configure WhatsApp integration in Rocket.Chat")
    print("3. Connect Rasa to Rocket.Chat")

def telegram_setup():
    """Guide for Telegram setup"""
    print_header("TELEGRAM BOT SETUP")
    
    print_step(1, "Create Telegram Bot")
    print("1. Message @BotFather on Telegram")
    print("2. Send /newbot command")
    print("3. Follow instructions to create bot")
    print("4. Get your bot token")
    
    print_step(2, "Configure in .env")
    print("Add to your .env file:")
    print("   TELEGRAM_TOKEN=your_telegram_bot_token")
    
    print_step(3, "Test your bot")
    print("1. Start a chat with your bot")
    print("2. Send /start command")
    print("3. Test basic functionality")

def test_integrations():
    """Test configured integrations"""
    print_header("TESTING INTEGRATIONS")
    
    print("To test your integrations, run:")
    print("   python test_integrations.py")
    
    print("\nOr test individual features:")
    print("1. Test Google Calendar:")
    print("   Send: 'I want to schedule a consultation'")
    print("2. Test WhatsApp/Telegram:")
    print("   Configure webhooks in your messaging platform")
    print("3. Test basic chatbot:")
    print("   Send: 'Hello' or 'What services do you offer?'")

def main():
    """Main configuration helper"""
    print("🚀 Eco Fusion Chatbot - Integration Configuration Helper")
    
    # Check current setup
    if not check_env_file():
        return
    
    # Show setup guides
    google_calendar_setup()
    whatsapp_setup()
    telegram_setup()
    test_integrations()
    
    print_header("NEXT STEPS")
    print("1. Edit your .env file with actual credentials")
    print("2. Restart the Rasa and Actions servers")
    print("3. Run: python test_integrations.py")
    print("4. Test your integrations!")
    
    print("\n📚 For detailed setup guides, see:")
    print("   - GOOGLE_CALENDAR_SETUP.md")
    print("   - README.md (Multi-Channel Integration section)")

if __name__ == "__main__":
    main()
