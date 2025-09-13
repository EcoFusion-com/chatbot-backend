from __future__ import annotations

import os
import time
import logging
from typing import Any, Dict, List, Optional, Text, Tuple

# Load .env from project root to make env vars (e.g., HF_TOKEN) available in actions server
try:
    from pathlib import Path
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env")
except Exception:
    pass

import base64
import smtplib
from email.message import EmailMessage

import requests
from requests import Response
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet
from rasa_sdk.events import FollowupAction  # Fix: Import FollowupAction for safe transitions

# Import centralized configuration
from .config import config

# Google Calendar API imports
try:
    from googleapiclient.discovery import build
    from google.oauth2 import service_account
    from google.auth.transport.requests import Request
    from google.auth.exceptions import GoogleAuthError
    GOOGLE_CALENDAR_AVAILABLE = config.is_google_calendar_available()
except ImportError:
    GOOGLE_CALENDAR_AVAILABLE = False
    print("Google Calendar API not available. Install: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib")

from .crm_utils import store_lead
from .analytics import (
    track_quote_generated, track_proposal_generated, track_calendar_link_created,
    track_crm_push_attempted, track_handoff_requested
)

# Import enhanced modules
from .enhanced_context import context_manager
from .enhanced_llm import contextual_response_generator

# Import modular actions
from .requirements_action import ActionHandleRequirements
from .quote_action import ActionQuoteEstimator

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Enhanced Hugging Face model configuration using router
HF_TOKEN = config.huggingface.token
HF_ROUTER_URL = config.huggingface.router_url
HF_ROUTER_HEADERS = config.get_router_headers()

# Fallback to old HF API if enhanced model not available
HF_MODEL_NAME = config.huggingface.model_name
HF_API_URL = f"https://api-inference.huggingface.co/models/{HF_MODEL_NAME}"
HF_API_KEY = config.huggingface.api_key
HF_HEADERS = config.get_huggingface_headers()

# Simple in-process rate limiting for HF API
_RATE_LIMIT_MAX = config.rate_limit.max_requests
_RATE_LIMIT_WINDOW_SEC = config.rate_limit.window_seconds
_rate_call_timestamps: List[float] = []

ECO_FUSION_CONTEXT = (
    "You are Eco Fusion's intelligent assistant. Eco Fusion provides:\n"
    "- AI & Automation (AI agents, chatbots, predictive analytics, RPA)\n"
    "- IoT Solutions (smart home, industrial IoT, energy monitoring)\n"
    "- Full-Stack Development (SaaS platforms, enterprise apps)\n"
    "\nIMPORTANT GUIDELINES:\n"
    "1. Be conversational and human-like, not robotic\n"
    "2. Don't ask repetitive questions - use context from the conversation\n"
    "3. If you need more information, ask specific, contextual questions\n"
    "4. Provide helpful, actionable responses\n"
    "5. When appropriate, naturally promote Eco Fusion's services\n"
    "6. If you don't understand something, ask for clarification in a friendly way\n"
    "7. Keep responses concise but informative\n"
    "8. Use the conversation history to provide better context-aware responses"
)

# Google Calendar API configuration
GOOGLE_CALENDAR_API_KEY = config.google_calendar.api_key
GOOGLE_CALENDAR_ID = config.google_calendar.calendar_id
GOOGLE_CALENDAR_CREDENTIALS_FILE = config.google_calendar.credentials_file

ADMIN_EMAIL = config.email.admin_email
SMTP_HOST = config.email.smtp_host
SMTP_PORT = config.email.smtp_port
SMTP_USER = config.email.smtp_user
SMTP_PASS = config.email.smtp_password

# New environment variables for pro features
CRM_WEBHOOK_URL = config.crm.webhook_url


def _within_rate_limit(now: float) -> bool:
    while _rate_call_timestamps and now - _rate_call_timestamps[0] > _RATE_LIMIT_WINDOW_SEC:
        _rate_call_timestamps.pop(0)
    return len(_rate_call_timestamps) < _RATE_LIMIT_MAX


def _register_rate_call(now: float) -> None:
    _rate_call_timestamps.append(now)


def _post_hf(payload: Dict[str, Any], timeout_seconds: int) -> Optional[Dict[str, Any]]:
    """
    Calls Hugging Face Inference API with correct endpoint and payload.
    Returns parsed JSON or None on error.
    """
    try:
        response = requests.post(HF_API_URL, headers=HF_HEADERS, json=payload, timeout=timeout_seconds)
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"HF API error {response.status_code}: {response.text}")
            return None
    except Exception as exc:
        logger.exception(f"HF API call failed: {exc}")
        return None

def call_enhanced_llm(prompt: str, timeout_seconds: int = 15, retries: int = 2) -> str:
    """
    Calls the enhanced LLM using Hugging Face router with OpenAI-compatible model.
    Falls back to old HF API if needed.
    Returns generated text or fallback message.
    """
    # Try Hugging Face router with OpenAI-compatible model first
    if HF_TOKEN:
        try:
            payload = {
                "model": "openai/gpt-oss-20b",
                "messages": [
                    {
                        "role": "system",
                        "content": ECO_FUSION_CONTEXT
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "max_tokens": 500,
                "temperature": 0.7
            }
            
            response = requests.post(
                f"{HF_ROUTER_URL}/chat/completions",
                headers=HF_ROUTER_HEADERS,
                json=payload,
                timeout=timeout_seconds
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("choices") and data["choices"][0].get("message"):
                    response_text = data["choices"][0]["message"]["content"]
                    if response_text and response_text.strip():
                        logger.info("Enhanced LLM response successful")
                        return response_text.strip()
                else:
                    logger.warning(f"Unexpected enhanced LLM response format: {data}")
            else:
                logger.warning(f"Enhanced LLM failed with status {response.status_code}: {response.text}")
        except Exception as exc:
            logger.warning(f"Enhanced LLM failed, falling back to HF API: {exc}")
    
    # Fallback to old HF API
    now = time.time()
    if not _within_rate_limit(now):
        logger.warning("HF API rate limit reached; serving branded fallback message")
        return (
            "I'm not fully certain. Eco Fusion offers AI & Automation, IoT, and Full-Stack Development. "
            "Could you provide more details so I can help better?"
        )

    backoff = 0.8
    last_error: Optional[Exception] = None
    for attempt in range(retries + 1):
        try:
            _register_rate_call(time.time())
            payload = {"inputs": prompt}
            data = _post_hf(payload, timeout_seconds)
            if not data:
                raise ValueError("No response from HF API")
            # Robust parsing for both list and dict formats
            if isinstance(data, list) and data and isinstance(data[0], dict) and "generated_text" in data[0]:
                return str(data[0]["generated_text"]).strip()
            if isinstance(data, dict) and "generated_text" in data:
                return str(data["generated_text"]).strip()
            if isinstance(data, dict) and "error" in data:
                logger.error(f"HF API returned error: {data['error']}")
                return "I'm sorry, I couldn't process your request. Please try again or ask something else about Eco Fusion."
            logger.warning(f"Unexpected HF response format: {data}")
            return (
                "I couldn't parse the assistant response. Eco Fusion specializes in AI & Automation, IoT, and "
                "Full-Stack Development. How can I assist further?"
            )
        except Exception as exc:
            last_error = exc
            logger.warning(f"HF Inference API attempt {attempt + 1} failed: {exc}")
            if attempt < retries:
                time.sleep(backoff)
                backoff *= 2
    logger.exception(f"HF Inference API error after retries: {last_error}")
    return (
        "I couldn't reach our assistant service right now. Meanwhile, I can share that Eco Fusion "
        "specializes in AI & Automation, IoT Solutions, and Full-Stack Development. How can I help?"
    )


def _normalize_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    v = str(value).strip()
    return v or None


def _normalize_budget(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    v = str(value).strip().replace("$", "").replace(",", "")
    return v or None


class ActionHandleRequirements(Action):
    def name(self) -> Text:
        return "action_handle_requirements"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        # Get user ID for context management
        user_id = tracker.sender_id
        
        # Enhanced extraction: parse latest user text for common fields
        user_text = (tracker.latest_message.get("text") or "").lower()
        industry = _normalize_text(tracker.get_slot("industry"))
        budget = _normalize_budget(tracker.get_slot("budget"))
        timeline = _normalize_text(tracker.get_slot("timeline"))
        technology = _normalize_text(tracker.get_slot("technology"))

        # Enhanced extraction with more context
        if not industry:
            industry_keywords = {
                "health": "healthcare", "medical": "healthcare", "hospital": "healthcare", "patient": "healthcare",
                "finance": "finance", "banking": "finance", "fintech": "finance",
                "retail": "retail", "ecommerce": "retail", "shopping": "retail",
                "education": "education", "learning": "education", "school": "education",
                "iot": "iot", "smart": "iot", "sensor": "iot",
                "ai": "ai", "machine learning": "ai", "automation": "ai", "predict": "ai",
                "manufacturing": "manufacturing", "factory": "manufacturing",
                "logistics": "logistics", "supply chain": "logistics"
            }
            for key, value in industry_keywords.items():
                if key in user_text:
                    industry = value
                    break
        
        if not budget:
            import re
            # Enhanced budget extraction
            budget_patterns = [
                r"\$?\s?(\d+\s*(k|k\+|\,?\d{3})?)",
                r"(\d+)\s*(thousand|k)",
                r"budget.*?(\d+)",
                r"cost.*?(\d+)",
                r"(\d+k)",  # Handle "13k" format
                r"(\d+\s*k)"  # Handle "13 k" format
            ]
            for pattern in budget_patterns:
                m = re.search(pattern, user_text)
                if m:
                    budget = m.group(0)
                    break
        
        if not timeline:
            import re
            # Enhanced timeline extraction with regex
            timeline_patterns = [
                (r"(\d+)\s*month", lambda m: f"{m.group(1)} month{'s' if int(m.group(1)) > 1 else ''}"),
                (r"(\d+)\s*week", lambda m: f"{m.group(1)} week{'s' if int(m.group(1)) > 1 else ''}"),
                (r"(\d+)\s*day", lambda m: f"{m.group(1)} day{'s' if int(m.group(1)) > 1 else ''}"),
            ]
            
            for pattern, formatter in timeline_patterns:
                m = re.search(pattern, user_text)
                if m:
                    timeline = formatter(m)
                    break
            
            # Fallback to keyword matching
            if not timeline:
                timeline_keywords = {
                    "week": "1 week", "weeks": "2 weeks", "month": "1 month", "months": "3 months",
                    "quarter": "3 months", "year": "1 year", "urgent": "1 month",
                    "asap": "1 month", "quick": "2 weeks"
                }
                for key, value in timeline_keywords.items():
                    if key in user_text:
                        timeline = value
                        break
        
        if not technology:
            tech_keywords = {
                "python": "Python", "node": "Node.js", "react": "React", "django": "Django",
                "fastapi": "FastAPI", "ml": "Machine Learning", "ai": "AI", "nlp": "NLP",
                "chatbot": "Chatbot", "automation": "Automation", "iot": "IoT",
                "mobile": "Mobile App", "web": "Web App", "saas": "SaaS Platform",
                "machine learning": "Machine Learning", "predictive": "AI", "prediction": "AI",
                "artificial intelligence": "AI", "intelligence": "AI", "smart": "AI"
            }
            for key, value in tech_keywords.items():
                if key in user_text:
                    technology = value
                    break

        missing_fields: List[str] = [
            key for key, value in {
                "industry": industry,
                "budget": budget,
                "timeline": timeline,
                "technology": technology,
            }.items() if not value
        ]

        # Set the slots
        events = [
            SlotSet("industry", industry),
            SlotSet("budget", budget),
            SlotSet("timeline", timeline),
            SlotSet("technology", technology),
        ]

        if missing_fields:
            # Use enhanced context-aware response generation
            try:
                # Get current tracker context
                tracker_context = {
                    "industry": industry,
                    "budget": budget,
                    "timeline": timeline,
                    "technology": technology
                }
                
                # Generate contextual response
                response = contextual_response_generator.generate_response(
                    user_id=user_id,
                    user_message=tracker.latest_message.get("text", ""),
                    intent="provide_requirements",
                    entities=tracker.latest_message.get("entities", []),
                    tracker_context=tracker_context
                )
                
                dispatcher.utter_message(text=response)
            except Exception as e:
                logger.warning(f"Enhanced response generation failed: {e}")
                dispatcher.utter_message(response="utter_ask_missing_info")
        else:
            # All fields captured, provide a helpful response using enhanced context
            try:
                # Get current tracker context
                tracker_context = {
                    "industry": industry,
                    "budget": budget,
                    "timeline": timeline,
                    "technology": technology
                }
                
                # Generate contextual response for complete project
                response = contextual_response_generator.generate_response(
                    user_id=user_id,
                    user_message=tracker.latest_message.get("text", ""),
                    intent="provide_requirements",
                    entities=tracker.latest_message.get("entities", []),
                    tracker_context=tracker_context
                )
                
                dispatcher.utter_message(text=response)
            except Exception as e:
                logger.warning(f"Enhanced response generation failed: {e}")
                # Fallback response
                response = (
                    f"Perfect! I've captured your {industry} project details:\n"
                    f"• **Technology**: {technology}\n"
                    f"• **Timeline**: {timeline}\n"
                    f"• **Budget**: {budget}\n\n"
                    f"Would you like me to generate a detailed quote or schedule a consultation with our team?"
                )
                dispatcher.utter_message(text=response)

        events.append(FollowupAction("action_listen"))
        return events


class ActionLLMFallback(Action):
    def name(self) -> Text:
        return "action_llm_fallback"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        """
        Enhanced LLM fallback with better context awareness and humanized responses.
        Uses the enhanced context management system for more intelligent conversations.
        """
        from rasa_sdk.events import SlotSet, FollowupAction

        # Get user ID for context management
        user_id = tracker.sender_id
        
        # Track if fallback was already used
        fallback_used = tracker.get_slot("llm_fallback_used")
        user_text = tracker.latest_message.get("text", "")

        events_to_return = []

        if not HF_TOKEN and not HF_API_KEY:
            logger.warning("No API keys configured; returning default fallback message.")
            dispatcher.utter_message(
                text=(
                    "I'm not fully certain about that. Eco Fusion offers AI & Automation, IoT, and Full-Stack Development. "
                    "Could you tell me more about what you're looking for?"
                )
            )
            events_to_return.append(FollowupAction("action_listen"))
            return events_to_return

        if not fallback_used:
            # First fallback: Use enhanced context-aware response
            try:
                # Get current tracker context
                tracker_context = {
                    "industry": tracker.get_slot("industry"),
                    "budget": tracker.get_slot("budget"),
                    "timeline": tracker.get_slot("timeline"),
                    "technology": tracker.get_slot("technology"),
                    "project_size": tracker.get_slot("project_size"),
                    "compliance": tracker.get_slot("compliance")
                }
                
                # Generate contextual response
                response = contextual_response_generator.generate_response(
                    user_id=user_id,
                    user_message=user_text,
                    intent="nlu_fallback",
                    entities=tracker.latest_message.get("entities", []),
                    tracker_context=tracker_context
                )
                
                dispatcher.utter_message(text=response)
                events_to_return.append(SlotSet("llm_fallback_used", True))
                    
            except Exception as exc:
                logger.exception(f"Enhanced fallback error: {exc}")
                # Provide a more helpful fallback response
                dispatcher.utter_message(
                    text=(
                        "I'm having trouble understanding that specific request. "
                        "Could you rephrase it or ask about our services, pricing, or how we can help with your project?"
                    )
                )
                events_to_return.append(SlotSet("llm_fallback_used", True))
        else:
            # Second consecutive fallback: Show helpful options
            msg = (
                "I'm still not quite sure what you're asking. Let me help you better:\n\n"
                "• **Services**: Ask about our AI & Automation, IoT, or Full-Stack Development\n"
                "• **Pricing**: Get a quote for your project\n"
                "• **Process**: Learn how we work with clients\n"
                "• **Human Help**: Connect with our team directly\n\n"
                "What would you like to know?"
            )
            
            dispatcher.utter_message(
                text=msg,
                buttons=[
                    {"title": "Our Services", "payload": "/ask_services"},
                    {"title": "Get Quote", "payload": "/ask_quote"},
                    {"title": "Our Process", "payload": "/ask_process"},
                    {"title": "Connect to Human", "payload": "/connect_human"},
                ]
            )
            # Reset slot so next fallback starts fresh
            events_to_return.append(SlotSet("llm_fallback_used", None))

        # Always yield control back to bot to prevent circuit breaker
        events_to_return.append(FollowupAction("action_listen"))
        return events_to_return


class ActionScheduleMeeting(Action):
    """Schedule a meeting via Google Calendar using a pre-authorized OAuth token."""

    def name(self) -> Text:
        return "action_schedule_meeting"

    def _create_event(self, summary: str, description: str, start_iso: str, end_iso: str, attendee_email: str) -> Optional[str]:
        if not (GOOGLE_CALENDAR_API_KEY and GOOGLE_CALENDAR_ID):
            logger.warning("Google Calendar not configured; set GOOGLE_CALENDAR_API_KEY and GOOGLE_CALENDAR_ID")
            return None
        url = f"https://www.googleapis.com/calendar/v3/calendars/{GOOGLE_CALENDAR_ID}/events"
        headers = {
            "Authorization": f"Bearer {GOOGLE_CALENDAR_API_KEY}",
            "Content-Type": "application/json",
        }
        body = {
            "summary": summary,
            "description": description,
            "start": {"dateTime": start_iso},
            "end": {"dateTime": end_iso},
            "attendees": [{"email": attendee_email}],
            "conferenceData": {"createRequest": {"requestId": f"eco-fusion-{int(time.time())}"}},
        }
        params = {"conferenceDataVersion": 1}
        try:
            resp = requests.post(url, headers=headers, json=body, params=params, timeout=20)
            if resp.status_code in (200, 201):
                data = resp.json()
                hangout_link = data.get("hangoutLink") or (data.get("conferenceData", {}).get("entryPoints", [{}])[0].get("uri"))
                return hangout_link or ""
            logger.warning("Calendar create event failed: %s %s", resp.status_code, resp.text)
            return None
        except Exception as exc:  # noqa: BLE001
            logger.exception("Calendar API error: %s", exc)
            return None

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        # Expect slots: timeline used as requested time; technology/industry/budget as notes
        email = _normalize_text(tracker.get_slot("email")) or _normalize_text(tracker.get_slot("client_email"))
        requested_time = _normalize_text(tracker.get_slot("timeline"))  # simplistic example
        industry = _normalize_text(tracker.get_slot("industry"))
        budget = _normalize_budget(tracker.get_slot("budget"))
        technology = _normalize_text(tracker.get_slot("technology"))

        if not email or not requested_time:
            dispatcher.utter_message(text="To book a meeting, please share your email and preferred date/time.")
            # Fix: Always yield control back to bot after scheduling attempt to prevent infinite loop
            return [FollowupAction("action_listen")]

        # For demo, parse requested_time externally; here we assume ISO strings already
        start_iso = requested_time
        end_iso = requested_time  # real impl: add 30-60 minutes

        description = f"Industry: {industry}\nBudget: {budget}\nTechnology: {technology}"
        link = self._create_event(
            summary="Eco Fusion Consultation",
            description=description,
            start_iso=start_iso,
            end_iso=end_iso,
            attendee_email=email,
        )

        if link:
            dispatcher.utter_message(text=f"Your meeting is booked. Join link: {link}")
        else:
            dispatcher.utter_message(text="I couldn't schedule the meeting right now. Please try again later.")
        # Fix: Always yield control back to bot after scheduling attempt to prevent infinite loop
        return [FollowupAction("action_listen")]


class ActionStoreLead(Action):
    """Store lead info into HubSpot or Postgres via crm_utils."""

    def name(self) -> Text:
        return "action_store_lead"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        name = _normalize_text(tracker.get_slot("name")) or _normalize_text(tracker.get_slot("full_name"))
        email = _normalize_text(tracker.get_slot("email"))
        service = _normalize_text(tracker.get_slot("service"))
        budget = _normalize_budget(tracker.get_slot("budget"))
        timeline = _normalize_text(tracker.get_slot("timeline"))

        payload = {
            "name": name,
            "email": email,
            "service": service,
            "budget": budget,
            "timeline": timeline,
            "source": "rasa",
        }
        ok = store_lead(payload)
        if ok:
            dispatcher.utter_message(text="Thanks! I've saved your details for our team.")
        else:
            dispatcher.utter_message(text="I couldn't save your details right now, but I can proceed with the chat.")
        # Fix: Always yield control back to bot after storing lead to prevent infinite loop
        return [FollowupAction("action_listen")]


class ActionSendEmail(Action):
    """Send email notification with meeting details to admin using SMTP."""

    def name(self) -> Text:
        return "action_send_email"

    def _send(self, subject: str, body: str, to_email: str) -> bool:
        if not (SMTP_HOST and SMTP_USER and SMTP_PASS and to_email):
            logger.warning("SMTP not configured or recipient missing")
            return False
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = SMTP_USER
        msg["To"] = to_email
        msg.set_content(body)
        try:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASS)
                server.send_message(msg)
            return True
        except Exception as exc:  # noqa: BLE001
            logger.exception("SMTP send failed: %s", exc)
            return False

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        email = _normalize_text(tracker.get_slot("email"))
        industry = _normalize_text(tracker.get_slot("industry"))
        budget = _normalize_budget(tracker.get_slot("budget"))
        timeline = _normalize_text(tracker.get_slot("timeline"))
        technology = _normalize_text(tracker.get_slot("technology"))
        meeting_link = _normalize_text(tracker.get_slot("meeting_link"))

        body = (
            f"Lead info:\nEmail: {email}\nIndustry: {industry}\nBudget: {budget}\n"
            f"Timeline: {timeline}\nTechnology: {technology}\nMeeting: {meeting_link or 'N/A'}\n"
        )
        to_admin = ADMIN_EMAIL or email
        ok = self._send("Eco Fusion Booking/Lead", body, to_admin)
        if ok:
            dispatcher.utter_message(text="Notification sent.")
        else:
            dispatcher.utter_message(text="Notification could not be sent.")
        # Fix: Always yield control back to bot after sending email to prevent infinite loop
        return [FollowupAction("action_listen")]


class ActionQuoteEstimator(Action):
    """Generate instant quote based on project requirements."""

    def name(self) -> Text:
        return "action_quote_estimator"

    def _calculate_quote(self, industry: str, budget: str, timeline: str, technology: str,
                        project_size: str = "medium", compliance: str = "none") -> str:
        """Calculate quote based on deterministic ruleset."""
        
        # Base prices for different services
        base_prices = {
            "ai_automation": {"small": 8000, "medium": 15000, "large": 30000},
            "iot_solutions": {"small": 12000, "medium": 25000, "large": 50000},
            "fullstack_dev": {"small": 10000, "medium": 20000, "large": 40000}
        }
        
        # Determine service type from technology/industry
        service_type = "fullstack_dev"  # default
        if any(tech in technology.lower() for tech in ["ai", "chatbot", "rpa", "automation"]):
            service_type = "ai_automation"
        elif any(tech in technology.lower() for tech in ["iot", "sensor", "hardware"]):
            service_type = "iot_solutions"
        
        # Get base price
        base_price = base_prices[service_type][project_size.lower()]
        
        # Apply multipliers
        multipliers = {
            "timeline": {
                "1 month": 1.5, "2 months": 1.3, "3 months": 1.0,
                "6 months": 0.9, "1 year": 0.8
            },
            "compliance": {
                "none": 1.0, "standard": 1.2, "strict": 1.5
            },
            "industry": {
                "healthcare": 1.3, "fintech": 1.4, "manufacturing": 1.1,
                "ecommerce": 1.0, "education": 0.9
            }
        }
        
        # Calculate final price
        final_price = base_price
        
        # Apply timeline multiplier
        for time_key, mult in multipliers["timeline"].items():
            if time_key.lower() in timeline.lower():
                final_price *= mult
                break
        
        # Apply compliance multiplier
        for comp_key, mult in multipliers["compliance"].items():
            if comp_key.lower() in compliance.lower():
                final_price *= mult
                break
        
        # Apply industry multiplier
        for ind_key, mult in multipliers["industry"].items():
            if ind_key.lower() in industry.lower():
                final_price *= mult
                break
        
        # Calculate range (±20%)
        min_price = int(final_price * 0.8)
        max_price = int(final_price * 1.2)
        
        return f"${min_price:,} - ${max_price:,}"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        industry = _normalize_text(tracker.get_slot("industry")) or "general"
        budget = _normalize_budget(tracker.get_slot("budget")) or "flexible"
        timeline = _normalize_text(tracker.get_slot("timeline")) or "3 months"
        technology = _normalize_text(tracker.get_slot("technology")) or "full-stack"
        project_size = _normalize_text(tracker.get_slot("project_size")) or "medium"
        compliance = _normalize_text(tracker.get_slot("compliance")) or "none"
        
        quote_range = self._calculate_quote(industry, budget, timeline, technology, project_size, compliance)
        
        # Track quote generation
        track_quote_generated(industry, budget, timeline, technology, project_size, compliance, quote_range)
        
        response = (
            f"Based on your requirements:\n"
            f"• Industry: {industry}\n"
            f"• Technology: {technology}\n"
            f"• Project Size: {project_size}\n"
            f"• Timeline: {timeline}\n"
            f"• Compliance: {compliance}\n\n"
            f"**Estimated Cost: {quote_range}**\n\n"
            f"This estimate includes development, testing, deployment, and 3 months of support. "
            f"Would you like me to generate a detailed proposal?"
        )
        
        dispatcher.utter_message(text=response)
        return [FollowupAction("action_listen")]


class ActionGenerateProposal(Action):
    """Generate proposal using template + HF polish."""

    def name(self) -> Text:
        return "action_generate_proposal"

    def _create_template(self, industry: str, budget: str, timeline: str, technology: str,
                        project_size: str, compliance: str) -> str:
        """Create proposal template."""
        
        template = f"""
# Eco Fusion Project Proposal

## Project Overview
**Industry:** {industry}
**Technology Stack:** {technology}
**Project Size:** {project_size}
**Timeline:** {timeline}
**Budget Range:** {budget}
**Compliance Requirements:** {compliance}

## Our Approach
Eco Fusion will deliver a comprehensive solution using our proven methodology:

### Phase 1: Discovery & Planning (Week 1-2)
- Requirements gathering and analysis
- Technical architecture design
- Project timeline and milestone planning
- Risk assessment and mitigation strategies

### Phase 2: Development (Week 3-{timeline})
- Agile development with weekly demos
- Regular client feedback sessions
- Quality assurance and testing
- Documentation and training materials

### Phase 3: Deployment & Support (Final Week + 3 months)
- Production deployment
- User training and handover
- 3 months of post-launch support
- Performance monitoring and optimization

## Technology Stack
Based on your requirements, we recommend:
- **Frontend:** Modern responsive framework
- **Backend:** Scalable API architecture
- **Database:** Robust data management
- **Cloud:** Secure cloud deployment
- **Monitoring:** Real-time performance tracking

## Deliverables
- Complete source code and documentation
- Deployment guide and maintenance procedures
- User training materials
- 3 months of post-launch support
- Performance optimization recommendations

## Next Steps
1. Schedule a detailed consultation
2. Sign project agreement
3. Begin discovery phase
4. Regular progress updates

**Ready to start your project? Let's discuss the details!**
        """
        
        return template.strip()

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        industry = _normalize_text(tracker.get_slot("industry")) or "general"
        budget = _normalize_budget(tracker.get_slot("budget")) or "flexible"
        timeline = _normalize_text(tracker.get_slot("timeline")) or "3 months"
        technology = _normalize_text(tracker.get_slot("technology")) or "full-stack"
        project_size = _normalize_text(tracker.get_slot("project_size")) or "medium"
        compliance = _normalize_text(tracker.get_slot("compliance")) or "none"
        
        # Create base template
        template = self._create_template(industry, budget, timeline, technology, project_size, compliance)
        
        # Try to polish with enhanced LLM
        llm_used = False
        if HF_TOKEN or HF_API_KEY:
            try:
                prompt = f"Please polish and enhance this proposal while maintaining the structure and making it more professional and engaging:\n\n{template}"
                polished = call_enhanced_llm(prompt, timeout_seconds=20, retries=1)
                if polished and len(polished) > len(template) * 0.8:  # Ensure we got a reasonable response
                    template = polished
                    llm_used = True
            except Exception as e:
                logger.warning(f"Enhanced LLM polish failed, using template: {e}")
        
        # Save proposal to file
        try:
            from pathlib import Path
            generated_dir = Path("generated")
            generated_dir.mkdir(exist_ok=True)
            
            timestamp = int(time.time())
            filename = f"proposal_{timestamp}.md"
            filepath = generated_dir / filename
            
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(template)
            
            logger.info(f"Proposal saved to {filepath}")
        except Exception as e:
            logger.error(f"Failed to save proposal: {e}")
        
        # Track proposal generation
        track_proposal_generated(industry, budget, timeline, technology, llm_used, len(template))
        
        # Send proposal in chat
        dispatcher.utter_message(text=template)
        
        return [FollowupAction("action_listen")]


class ActionCreateCalendarLink(Action):
    """Create Google Calendar event or fallback to booking link."""

    def name(self) -> Text:
        return "action_create_calendar_link"

    def _create_google_calendar_event(self, industry: str, technology: str, user_email: str) -> Optional[str]:
        """Create a Google Calendar event and return the event link."""
        if not GOOGLE_CALENDAR_AVAILABLE:
            return None
        
        try:
            # Try OAuth2 credentials first, then fallback to API key
            service = None
            
            # Check for OAuth2 credentials file
            credentials_file = os.getenv("GOOGLE_CALENDAR_CREDENTIALS_FILE")
            if credentials_file and os.path.exists(credentials_file):
                try:
                    from google.oauth2 import service_account
                    credentials = service_account.Credentials.from_service_account_file(
                        credentials_file,
                        scopes=['https://www.googleapis.com/auth/calendar']
                    )
                    service = build('calendar', 'v3', credentials=credentials)
                    logger.info("Using OAuth2 service account credentials")
                except Exception as e:
                    logger.warning(f"Failed to load OAuth2 credentials: {e}")
            
            # Fallback to API key (limited functionality)
            if not service and GOOGLE_CALENDAR_API_KEY:
                try:
                    service = build('calendar', 'v3', developerKey=GOOGLE_CALENDAR_API_KEY)
                    logger.info("Using API key (limited functionality)")
                except Exception as e:
                    logger.warning(f"Failed to create service with API key: {e}")
                    return None
            
            if not service:
                logger.warning("No Google Calendar credentials available")
                return None
            
            # Create event details
            event = {
                'summary': f'Eco Fusion Consultation - {industry.title()} Project',
                'description': f'''Consultation for {industry} project using {technology} technology.

Project Details:
- Industry: {industry}
- Technology: {technology}
- Source: Chatbot Lead

This is a 30-minute consultation to discuss project requirements, timeline, and next steps.''',
                'start': {
                    'dateTime': '2024-01-15T10:00:00-07:00',  # Placeholder - in real implementation, show available slots
                    'timeZone': 'America/Los_Angeles',
                },
                'end': {
                    'dateTime': '2024-01-15T10:30:00-07:00',
                    'timeZone': 'America/Los_Angeles',
                },
                'attendees': [
                    {'email': user_email if user_email != "unknown" else ADMIN_EMAIL},
                    {'email': ADMIN_EMAIL}
                ],
                'reminders': {
                    'useDefault': False,
                    'overrides': [
                        {'method': 'email', 'minutes': 24 * 60},
                        {'method': 'popup', 'minutes': 10},
                    ],
                },
            }
            
            # Insert the event
            if GOOGLE_CALENDAR_ID:
                event = service.events().insert(calendarId=GOOGLE_CALENDAR_ID, body=event).execute()
                return event.get('htmlLink')
            else:
                logger.warning("GOOGLE_CALENDAR_ID not configured")
                return None
                
        except Exception as e:
            logger.error(f"Failed to create Google Calendar event: {e}")
            return None

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        industry = _normalize_text(tracker.get_slot("industry")) or "general"
        technology = _normalize_text(tracker.get_slot("technology")) or "full-stack"
        user_email = _normalize_text(tracker.get_slot("email")) or "unknown"
        
        # Try to create Google Calendar event first
        calendar_link = self._create_google_calendar_event(industry, technology, user_email)
        
        if calendar_link:
            # Google Calendar event created successfully
            response = (
                f"Perfect! I've created a Google Calendar event for your consultation.\n\n"
                f"**Calendar Event:** {calendar_link}\n\n"
                f"This 30-minute consultation will cover:\n"
                f"• Your {industry} project requirements\n"
                f"• {technology} implementation details\n"
                f"• Timeline and budget considerations\n"
            )
            dispatcher.utter_message(text=response)
            track_calendar_link_created(user_email if user_email != "unknown" else ADMIN_EMAIL, "consultation")
            return [FollowupAction("action_listen")]

        # No Calendly fallback per project requirement; inform user to provide details
        dispatcher.utter_message(text=(
            "I couldn't create a Google Calendar event right now. Please share a preferred time window and your email, or ensure calendar credentials are configured."
        ))
        dispatcher.utter_message(text=(
            "I'll book it directly on Google Calendar once I have the details."
        ))
        return [FollowupAction("action_listen")]


class ActionPushToCRM(Action):
    """Push lead data to configurable webhook."""

    def name(self) -> Text:
        return "action_push_to_crm"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        if not CRM_WEBHOOK_URL:
            logger.warning("CRM_WEBHOOK_URL not configured")
            dispatcher.utter_message(text="CRM integration not configured.")
            return [FollowupAction("action_listen")]
        
        # Collect lead data
        lead_data = {
            "name": _normalize_text(tracker.get_slot("name")) or _normalize_text(tracker.get_slot("full_name")),
            "email": _normalize_text(tracker.get_slot("email")),
            "industry": _normalize_text(tracker.get_slot("industry")),
            "budget": _normalize_budget(tracker.get_slot("budget")),
            "timeline": _normalize_text(tracker.get_slot("timeline")),
            "technology": _normalize_text(tracker.get_slot("technology")),
            "project_size": _normalize_text(tracker.get_slot("project_size")),
            "compliance": _normalize_text(tracker.get_slot("compliance")),
            "source": "rasa_chatbot",
            "timestamp": time.time()
        }
        
        # Remove None values
        lead_data = {k: v for k, v in lead_data.items() if v is not None}
        
        # Push to CRM webhook with retries
        success = False
        backoff = 1.0
        for attempt in range(3):
            try:
                response = requests.post(
                    CRM_WEBHOOK_URL,
                    json=lead_data,
                    headers={"Content-Type": "application/json"},
                    timeout=10
                )
                if response.status_code in (200, 201, 202):
                    success = True
                    break
                else:
                    logger.warning(f"CRM webhook failed (attempt {attempt + 1}): {response.status_code}")
            except Exception as e:
                logger.warning(f"CRM webhook error (attempt {attempt + 1}): {e}")
            
            if attempt < 2:
                time.sleep(backoff)
                backoff *= 2
        
        # Track CRM push attempt
        track_crm_push_attempted(lead_data, success)
        
        if success:
            dispatcher.utter_message(text="Your information has been saved to our CRM. We'll be in touch soon!")
        else:
            dispatcher.utter_message(text="I couldn't save your information right now, but I can continue helping you.")
        
        return [FollowupAction("action_listen")]


class ActionHandoffToHuman(Action):
    """Handle human handoff with special payload for Rocket.Chat."""

    def name(self) -> Text:
        return "action_handoff_to_human"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        # Track handoff request
        conversation_length = len([e for e in tracker.events if e.get("event") in ["user", "bot"]])
        track_handoff_requested("user_requested", conversation_length)
        
        # Send handoff acknowledgment
        dispatcher.utter_message(response="utter_handoff_ack")
        
        # Send special payload for Rocket.Chat to route to human agent
        dispatcher.utter_message(
            json_message={
                "handoff_to_human": True,
                "conversation_id": tracker.sender_id,
                "user_message": tracker.latest_message.get("text", ""),
                "slots": {
                    "industry": tracker.get_slot("industry"),
                    "budget": tracker.get_slot("budget"),
                    "timeline": tracker.get_slot("timeline"),
                    "technology": tracker.get_slot("technology")
                }
            }
        )
        
        # Send agent coming message
        dispatcher.utter_message(response="utter_agent_coming")
        
        return [FollowupAction("action_listen")]


class ActionHandleChannelSwitch(Action):
    def name(self) -> Text:
        return "action_handle_channel_switch"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        text = (tracker.latest_message.get("text") or "").lower()
        preferred = ""
        if "whatsapp" in text:
            preferred = "whatsapp"
        elif "email" in text or "e-mail" in text:
            preferred = "email"
        elif "telegram" in text:
            preferred = "telegram"
        elif "phone" in text or "call" in text:
            preferred = "phone"
        else:
            preferred = "unspecified"

        if preferred == "whatsapp":
            dispatcher.utter_message(text="Sure — I’ll follow up with you on WhatsApp.")
        elif preferred == "email":
            dispatcher.utter_message(text="Got it — I’ll reach out via email. Please confirm your address if needed.")
        elif preferred == "telegram":
            dispatcher.utter_message(text="Okay — I’ll contact you on Telegram.")
        elif preferred == "phone":
            dispatcher.utter_message(text="No problem — I’ll arrange a phone call.")
        else:
            dispatcher.utter_message(text="I can reach you on WhatsApp, email, Telegram, or phone — which do you prefer?")

        return [SlotSet("preferred_channel", preferred), FollowupAction("action_listen")]
