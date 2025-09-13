"""
Enhanced Context Management for Human-like Conversations
This module provides advanced context handling to make the chatbot more human-like
and better at maintaining conversation flow.
"""

import json
import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

@dataclass
class ConversationContext:
    """Represents the current conversation context"""
    user_id: str
    session_start: datetime
    conversation_topic: Optional[str] = None
    user_intent: Optional[str] = None
    project_context: Optional[Dict[str, Any]] = None
    conversation_mood: Optional[str] = None  # friendly, formal, urgent, etc.
    last_interaction: Optional[datetime] = None
    interaction_count: int = 0
    context_switches: int = 0
    user_preferences: Optional[Dict[str, Any]] = None

@dataclass
class ConversationMemory:
    """Stores conversation history and context"""
    recent_messages: List[Dict[str, Any]]
    key_topics: List[str]
    user_mentions: List[str]
    bot_responses: List[str]
    context_entities: Dict[str, Any]
    conversation_flow: List[str]

class ContextManager:
    """Manages conversation context and memory for human-like interactions"""
    
    def __init__(self, max_history: int = 20):
        self.max_history = max_history
        self.conversations: Dict[str, ConversationContext] = {}
        self.memories: Dict[str, ConversationMemory] = {}
        
    def get_or_create_context(self, user_id: str) -> ConversationContext:
        """Get existing context or create new one"""
        if user_id not in self.conversations:
            self.conversations[user_id] = ConversationContext(
                user_id=user_id,
                session_start=datetime.now()
            )
            self.memories[user_id] = ConversationMemory(
                recent_messages=[],
                key_topics=[],
                user_mentions=[],
                bot_responses=[],
                context_entities={},
                conversation_flow=[]
            )
        return self.conversations[user_id]
    
    def update_context(self, user_id: str, **kwargs) -> None:
        """Update conversation context"""
        context = self.get_or_create_context(user_id)
        for key, value in kwargs.items():
            if hasattr(context, key):
                setattr(context, key, value)
        context.last_interaction = datetime.now()
        context.interaction_count += 1
    
    def add_message_to_memory(self, user_id: str, message: Dict[str, Any], is_user: bool = True) -> None:
        """Add message to conversation memory"""
        memory = self.memories.get(user_id)
        if not memory:
            return
            
        # Add to recent messages
        memory.recent_messages.append({
            'text': message.get('text', ''),
            'timestamp': datetime.now().isoformat(),
            'is_user': is_user,
            'intent': message.get('intent', {}).get('name') if message.get('intent') else None,
            'entities': message.get('entities', [])
        })
        
        # Keep only recent messages
        if len(memory.recent_messages) > self.max_history:
            memory.recent_messages.pop(0)
        
        # Extract key topics and entities
        if is_user:
            text = message.get('text', '').lower()
            entities = message.get('entities', [])
            
            # Extract key topics
            topics = self._extract_topics(text)
            for topic in topics:
                if topic not in memory.key_topics:
                    memory.key_topics.append(topic)
            
            # Extract entities
            for entity in entities:
                memory.context_entities[entity.get('entity')] = entity.get('value')
    
    def get_conversation_summary(self, user_id: str) -> str:
        """Generate a summary of the conversation for context"""
        memory = self.memories.get(user_id)
        context = self.conversations.get(user_id)
        
        if not memory or not context:
            return ""
        
        summary_parts = []
        
        # Add conversation topic
        if context.conversation_topic:
            summary_parts.append(f"Topic: {context.conversation_topic}")
        
        # Add key topics
        if memory.key_topics:
            summary_parts.append(f"Key topics: {', '.join(memory.key_topics[-3:])}")
        
        # Add project context
        if context.project_context:
            summary_parts.append(f"Project: {context.project_context}")
        
        # Add conversation mood
        if context.conversation_mood:
            summary_parts.append(f"Mood: {context.conversation_mood}")
        
        return " | ".join(summary_parts)
    
    def get_recent_context(self, user_id: str, num_messages: int = 6) -> str:
        """Get recent conversation context"""
        memory = self.memories.get(user_id)
        if not memory:
            return ""
        
        recent = memory.recent_messages[-num_messages:] if len(memory.recent_messages) > num_messages else memory.recent_messages
        
        context_lines = []
        for msg in recent:
            role = "User" if msg['is_user'] else "Assistant"
            context_lines.append(f"{role}: {msg['text']}")
        
        return "\n".join(context_lines)
    
    def detect_context_switch(self, user_id: str, current_intent: str) -> bool:
        """Detect if user is switching conversation context"""
        memory = self.memories.get(user_id)
        if not memory or not memory.conversation_flow:
            return False
        
        # Check if current intent is different from recent flow
        recent_intents = memory.conversation_flow[-3:]
        if current_intent not in recent_intents:
            memory.conversation_flow.append(current_intent)
            return True
        
        return False
    
    def _extract_topics(self, text: str) -> List[str]:
        """Extract key topics from text"""
        topics = []
        
        # Define topic keywords
        topic_keywords = {
            'ai': ['ai', 'artificial intelligence', 'machine learning', 'automation', 'chatbot', 'rpa'],
            'iot': ['iot', 'internet of things', 'smart home', 'sensors', 'connected devices'],
            'development': ['development', 'programming', 'coding', 'software', 'app', 'website'],
            'pricing': ['price', 'cost', 'budget', 'quote', 'estimate', 'pricing'],
            'process': ['process', 'methodology', 'timeline', 'delivery', 'agile'],
            'support': ['support', 'help', 'assistance', 'contact', 'human']
        }
        
        text_lower = text.lower()
        for topic, keywords in topic_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                topics.append(topic)
        
        return topics
    
    def analyze_user_mood(self, user_id: str) -> str:
        """Analyze user's conversation mood"""
        memory = self.memories.get(user_id)
        if not memory:
            return "neutral"
        
        # Analyze recent user messages for mood indicators
        recent_user_messages = [msg for msg in memory.recent_messages[-5:] if msg['is_user']]
        
        mood_indicators = {
            'friendly': ['thanks', 'thank you', 'great', 'awesome', 'love', 'like', 'good'],
            'urgent': ['urgent', 'asap', 'quick', 'fast', 'immediately', 'now'],
            'frustrated': ['frustrated', 'annoyed', 'problem', 'issue', 'not working', 'wrong'],
            'formal': ['business', 'professional', 'company', 'enterprise', 'corporate']
        }
        
        text = ' '.join([msg['text'].lower() for msg in recent_user_messages])
        
        for mood, indicators in mood_indicators.items():
            if any(indicator in text for indicator in indicators):
                return mood
        
        return "neutral"

class HumanizedResponseGenerator:
    """Generates more human-like responses"""
    
    def __init__(self):
        self.context_manager = ContextManager()
        self.response_templates = {
            'greeting': [
                "Hi there! 👋 How can I help you today?",
                "Hello! I'm here to assist you with Eco Fusion's services.",
                "Hey! What brings you to Eco Fusion today?"
            ],
            'acknowledgment': [
                "I understand you're interested in {topic}. Let me help you with that.",
                "Got it! {topic} is definitely something we can help with.",
                "Perfect! {topic} is one of our specialties."
            ],
            'clarification': [
                "Could you tell me a bit more about {topic}?",
                "I'd love to help with {topic}. What specific aspects are you looking for?",
                "Great question about {topic}! What would you like to know?"
            ],
            'transition': [
                "Now, about {topic}...",
                "Speaking of {topic}...",
                "On that note, regarding {topic}..."
            ]
        }
    
    def generate_contextual_response(self, user_id: str, user_message: str, intent: str, entities: List[Dict]) -> str:
        """Generate a contextual, human-like response"""
        context = self.context_manager.get_or_create_context(user_id)
        
        # Update context with current interaction
        self.context_manager.update_context(
            user_id,
            user_intent=intent,
            last_interaction=datetime.now()
        )
        
        # Add message to memory
        self.context_manager.add_message_to_memory(user_id, {
            'text': user_message,
            'intent': {'name': intent},
            'entities': entities
        }, is_user=True)
        
        # Analyze mood
        mood = self.context_manager.analyze_user_mood(user_id)
        self.context_manager.update_context(user_id, conversation_mood=mood)
        
        # Detect context switch
        context_switch = self.context_manager.detect_context_switch(user_id, intent)
        
        # Generate appropriate response based on context
        if intent == 'greet':
            return self._get_greeting_response(context, mood)
        elif context_switch:
            return self._get_context_switch_response(intent, entities)
        else:
            return self._get_continuation_response(intent, entities, context)
    
    def _get_greeting_response(self, context: ConversationContext, mood: str) -> str:
        """Generate greeting response based on context and mood"""
        if context.interaction_count > 1:
            return "Welcome back! How can I continue helping you today?"
        
        if mood == 'urgent':
            return "Hi! I'm here to help quickly. What do you need?"
        elif mood == 'formal':
            return "Good day! I'm Eco Fusion's assistant. How may I help you today?"
        else:
            import random
            return random.choice(self.response_templates['greeting'])
    
    def _get_context_switch_response(self, intent: str, entities: List[Dict]) -> str:
        """Generate response for context switch"""
        topic = self._extract_topic_from_intent(intent, entities)
        return f"Sure! Let's talk about {topic}. What would you like to know?"
    
    def _get_continuation_response(self, intent: str, entities: List[Dict], context: ConversationContext) -> str:
        """Generate continuation response"""
        topic = self._extract_topic_from_intent(intent, entities)
        
        if context.conversation_mood == 'urgent':
            return f"Got it! Let me get you the {topic} information quickly."
        else:
            return f"I understand you're interested in {topic}. Let me help you with that."
    
    def _extract_topic_from_intent(self, intent: str, entities: List[Dict]) -> str:
        """Extract topic from intent and entities"""
        topic_mapping = {
            'ask_ai_automation': 'AI & Automation',
            'ask_iot_solutions': 'IoT Solutions',
            'ask_fullstack_dev': 'Full-Stack Development',
            'ask_pricing': 'pricing',
            'ask_process': 'our process',
            'ask_services': 'our services'
        }
        
        return topic_mapping.get(intent, 'that topic')

# Global instance
context_manager = ContextManager()
response_generator = HumanizedResponseGenerator()
