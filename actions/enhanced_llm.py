"""
Enhanced LLM Integration for Human-like Conversations
This module provides advanced LLM integration with better context handling
and more human-like response generation.
"""

import os
import time
import logging
import requests
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

from .enhanced_context import context_manager, response_generator

logger = logging.getLogger(__name__)

# Configuration
HF_TOKEN = os.getenv("HF_TOKEN", "")
HF_ROUTER_URL = "https://router.huggingface.co/v1"
HF_ROUTER_HEADERS = {"Authorization": f"Bearer {HF_TOKEN}"} if HF_TOKEN else {}

# Fallback configuration
HF_MODEL_NAME = os.getenv("HF_MODEL_NAME", "microsoft/DialoGPT-medium")
HF_API_URL = f"https://api-inference.huggingface.co/models/{HF_MODEL_NAME}"
HF_API_KEY = os.getenv("HF_API_KEY") or HF_TOKEN
HF_HEADERS = {"Authorization": f"Bearer {HF_API_KEY}"} if HF_API_KEY else {}

# Rate limiting
_RATE_LIMIT_MAX = 20
_RATE_LIMIT_WINDOW_SEC = 60
_rate_call_timestamps: List[float] = []

# Enhanced context for Eco Fusion
ECO_FUSION_CONTEXT = """
You are Eco Fusion's intelligent assistant, specializing in AI & Automation, IoT Solutions, and Full-Stack Development.

CORE SERVICES:
- AI & Automation: AI agents, chatbots, predictive analytics, RPA, CRM/ERP integration
- IoT Solutions: Smart home systems, industrial IoT, energy monitoring, real-time analytics
- Full-Stack Development: SaaS platforms, custom enterprise apps, web & mobile applications

CONVERSATION STYLE:
- Be conversational and human-like, not robotic
- Use natural language with appropriate emojis and expressions
- Acknowledge context from previous messages
- Don't ask repetitive questions - use conversation history
- Be helpful and specific to the user's needs
- Show personality while remaining professional

RESPONSE GUIDELINES:
1. Always consider conversation context and history
2. Acknowledge what the user has already shared
3. Ask follow-up questions naturally
4. Provide specific, actionable information
5. Use the user's preferred communication style (formal/casual)
6. Don't repeat information already provided
7. Be concise but thorough
8. Show understanding of their project requirements

PROJECT UNDERSTANDING:
- Extract and remember: industry, budget, timeline, technology preferences
- Build on previous information shared
- Provide relevant examples and use cases
- Offer next steps when appropriate
"""

class EnhancedLLMClient:
    """Enhanced LLM client with better context handling"""
    
    def __init__(self):
        self.context_manager = context_manager
        self.response_generator = response_generator
    
    def generate_contextual_response(
        self, 
        user_id: str, 
        user_message: str, 
        intent: str, 
        entities: List[Dict],
        tracker_context: Dict[str, Any]
    ) -> str:
        """Generate a contextual, human-like response using LLM"""
        
        # Get conversation context
        conversation_summary = self.context_manager.get_conversation_summary(user_id)
        recent_context = self.context_manager.get_recent_context(user_id, num_messages=8)
        
        # Build comprehensive context for LLM
        context_prompt = self._build_context_prompt(
            user_message, intent, entities, tracker_context,
            conversation_summary, recent_context, user_id
        )
        
        # Generate response using LLM
        try:
            llm_response = self._call_enhanced_llm(context_prompt)
            if llm_response and len(llm_response.strip()) > 10:
                return self._post_process_response(llm_response, user_id)
        except Exception as e:
            logger.warning(f"LLM response generation failed: {e}")
        
        # Fallback to template-based response
        return self.response_generator.generate_contextual_response(
            user_id, user_message, intent, entities
        )
    
    def _build_context_prompt(
        self, 
        user_message: str, 
        intent: str, 
        entities: List[Dict],
        tracker_context: Dict[str, Any],
        conversation_summary: str,
        recent_context: str,
        user_id: str
    ) -> str:
        """Build a comprehensive context prompt for the LLM"""
        
        # Get current slots
        slots = {
            "industry": tracker_context.get("industry"),
            "budget": tracker_context.get("budget"),
            "timeline": tracker_context.get("timeline"),
            "technology": tracker_context.get("technology"),
            "project_size": tracker_context.get("project_size"),
            "compliance": tracker_context.get("compliance")
        }
        
        # Filter out None values
        slots = {k: v for k, v in slots.items() if v is not None}
        
        # Build the prompt
        prompt_parts = [
            ECO_FUSION_CONTEXT,
            "\nCONVERSATION CONTEXT:",
            f"Conversation Summary: {conversation_summary}" if conversation_summary else "New conversation",
            f"Recent Messages:\n{recent_context}" if recent_context else "No recent context",
            f"Current Project Info: {slots}" if slots else "No project info yet",
            f"User Intent: {intent}",
            f"Extracted Entities: {entities}" if entities else "No entities",
            "\nCURRENT USER MESSAGE:",
            user_message,
            "\nINSTRUCTIONS:",
            "Generate a natural, contextual response that:",
            "1. Acknowledges the conversation context",
            "2. Addresses the user's current message",
            "3. Uses information from previous messages when relevant",
            "4. Provides helpful, specific information",
            "5. Maintains a conversational, human-like tone",
            "6. Asks follow-up questions when appropriate",
            "7. Doesn't repeat information already shared",
            "\nRESPONSE:"
        ]
        
        return "\n".join(prompt_parts)
    
    def _call_enhanced_llm(self, prompt: str, timeout_seconds: int = 20) -> Optional[str]:
        """Call the enhanced LLM with proper error handling"""
        
        # Try Hugging Face router first
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
                    "max_tokens": 600,
                    "temperature": 0.7,
                    "top_p": 0.9,
                    "frequency_penalty": 0.1,
                    "presence_penalty": 0.1
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
                
                logger.warning(f"Enhanced LLM failed with status {response.status_code}")
                
            except Exception as exc:
                logger.warning(f"Enhanced LLM failed, falling back: {exc}")
        
        # Fallback to old HF API
        return self._call_fallback_llm(prompt, timeout_seconds)
    
    def _call_fallback_llm(self, prompt: str, timeout_seconds: int = 15) -> Optional[str]:
        """Fallback LLM call with rate limiting"""
        
        now = time.time()
        if not self._within_rate_limit(now):
            logger.warning("Rate limit reached")
            return None
        
        try:
            self._register_rate_call(now)
            payload = {"inputs": prompt}
            response = requests.post(
                HF_API_URL, 
                headers=HF_HEADERS, 
                json=payload, 
                timeout=timeout_seconds
            )
            
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list) and data and "generated_text" in data[0]:
                    return str(data[0]["generated_text"]).strip()
                elif isinstance(data, dict) and "generated_text" in data:
                    return str(data["generated_text"]).strip()
            
            logger.warning(f"Fallback LLM failed: {response.status_code}")
            return None
            
        except Exception as exc:
            logger.exception(f"Fallback LLM error: {exc}")
            return None
    
    def _post_process_response(self, response: str, user_id: str) -> str:
        """Post-process LLM response for better quality"""
        
        # Clean up the response
        response = response.strip()
        
        # Remove any "Assistant:" prefixes
        if response.startswith("Assistant:"):
            response = response[10:].strip()
        
        # Remove any "Bot:" prefixes
        if response.startswith("Bot:"):
            response = response[4:].strip()
        
        # Ensure response is not too long
        if len(response) > 500:
            response = response[:497] + "..."
        
        # Add response to memory
        self.context_manager.add_message_to_memory(user_id, {
            'text': response,
            'intent': None,
            'entities': []
        }, is_user=False)
        
        return response
    
    def _within_rate_limit(self, now: float) -> bool:
        """Check if within rate limit"""
        while _rate_call_timestamps and now - _rate_call_timestamps[0] > _RATE_LIMIT_WINDOW_SEC:
            _rate_call_timestamps.pop(0)
        return len(_rate_call_timestamps) < _RATE_LIMIT_MAX
    
    def _register_rate_call(self, now: float) -> None:
        """Register a rate-limited call"""
        _rate_call_timestamps.append(now)

class ContextualResponseGenerator:
    """Generates contextual responses based on conversation state"""
    
    def __init__(self):
        self.llm_client = EnhancedLLMClient()
        self.context_manager = context_manager
    
    def generate_response(
        self, 
        user_id: str, 
        user_message: str, 
        intent: str, 
        entities: List[Dict],
        tracker_context: Dict[str, Any]
    ) -> str:
        """Generate the best possible response based on context"""
        
        # Update context with current interaction
        self.context_manager.update_context(
            user_id,
            user_intent=intent,
            last_interaction=datetime.now()
        )
        
        # Add user message to memory
        self.context_manager.add_message_to_memory(user_id, {
            'text': user_message,
            'intent': {'name': intent},
            'entities': entities
        }, is_user=True)
        
        # Try LLM-based response first
        try:
            llm_response = self.llm_client.generate_contextual_response(
                user_id, user_message, intent, entities, tracker_context
            )
            if llm_response:
                return llm_response
        except Exception as e:
            logger.warning(f"LLM response failed: {e}")
        
        # Fallback to template-based response
        return self._generate_template_response(intent, entities, tracker_context)
    
    def _generate_template_response(
        self, 
        intent: str, 
        entities: List[Dict], 
        tracker_context: Dict[str, Any]
    ) -> str:
        """Generate template-based response as fallback"""
        
        # Extract project info
        industry = tracker_context.get("industry")
        budget = tracker_context.get("budget")
        timeline = tracker_context.get("timeline")
        technology = tracker_context.get("technology")
        
        # Intent-specific responses
        if intent == "greet":
            return "Hi there! 👋 I'm Eco Fusion's assistant. How can I help you today?"
        
        elif intent == "ask_services":
            return (
                "Eco Fusion specializes in three core areas:\n\n"
                "🤖 **AI & Automation**: Chatbots, predictive analytics, RPA, and CRM integration\n"
                "🌐 **IoT Solutions**: Smart home systems, industrial IoT, and energy monitoring\n"
                "💻 **Full-Stack Development**: SaaS platforms, enterprise apps, and custom solutions\n\n"
                "Which area interests you most?"
            )
        
        elif intent == "ask_ai_automation":
            return (
                "Our AI & Automation services include:\n\n"
                "• **AI Agents & Chatbots** - Intelligent conversational interfaces\n"
                "• **Predictive Analytics** - Data-driven insights and forecasting\n"
                "• **RPA (Robotic Process Automation)** - Automated workflow solutions\n"
                "• **CRM/ERP Integration** - Seamless system connectivity\n\n"
                "What specific AI solution are you looking for?"
            )
        
        elif intent == "ask_iot_solutions":
            return (
                "Our IoT Solutions cover:\n\n"
                "• **Smart Home Systems** - Connected home automation\n"
                "• **Industrial IoT** - Manufacturing and industrial monitoring\n"
                "• **Energy Monitoring** - Real-time energy management\n"
                "• **Real-time Analytics** - Live data processing and insights\n\n"
                "What type of IoT project do you have in mind?"
            )
        
        elif intent == "ask_fullstack_dev":
            return (
                "Our Full-Stack Development services include:\n\n"
                "• **SaaS Platforms** - Scalable software-as-a-service solutions\n"
                "• **Custom Enterprise Apps** - Tailored business applications\n"
                "• **Web & Mobile Apps** - Cross-platform development\n"
                "• **API Development** - Robust backend services\n\n"
                "What kind of application are you looking to build?"
            )
        
        elif intent == "provide_requirements":
            # Check what information we have
            missing = []
            if not industry:
                missing.append("industry/domain")
            if not budget:
                missing.append("budget range")
            if not timeline:
                missing.append("timeline")
            if not technology:
                missing.append("technology preferences")
            
            if missing:
                return f"Great! To help you better, could you tell me about your {', '.join(missing)}?"
            else:
                return (
                    f"Perfect! I have your {industry} project details:\n"
                    f"• Technology: {technology}\n"
                    f"• Timeline: {timeline}\n"
                    f"• Budget: {budget}\n\n"
                    "Would you like me to generate a detailed quote or schedule a consultation?"
                )
        
        else:
            return (
                "I understand you're interested in our services. "
                "Could you tell me more about your project requirements? "
                "I'd love to help you find the right solution!"
            )

# Global instances
enhanced_llm_client = EnhancedLLMClient()
contextual_response_generator = ContextualResponseGenerator()
