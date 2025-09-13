"""
Requirements Handling Action
Handles project requirements collection and processing
"""

import re
from typing import Any, Dict, List, Optional, Text
from rasa_sdk import Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, FollowupAction

from .base_action import _BaseAction as BaseAction

class ActionHandleRequirements(BaseAction):
    """Handles project requirements collection and processing"""
    
    def name(self) -> Text:
        return "action_handle_requirements"
    
    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        user_id = self._get_user_id(tracker)
        self._log_action_start(self.name(), user_id)
        
        try:
            # Get user text for enhanced extraction
            user_text = self._get_user_text(tracker)
            
            # Extract and normalize current slot values
            industry = self._get_slot_value(tracker, "industry")
            budget = self._normalize_budget(self._get_slot_value(tracker, "budget"))
            timeline = self._get_slot_value(tracker, "timeline")
            technology = self._get_slot_value(tracker, "technology")
            
            # Enhanced extraction with more context
            industry = self._extract_industry(user_text, industry)
            budget = self._extract_budget(user_text, budget)
            timeline = self._extract_timeline(user_text, timeline)
            technology = self._extract_technology(user_text, technology)
            
            # Create events to update slots
            events = []
            
            if industry:
                events.append(self._set_slot("industry", industry))
            if budget:
                events.append(self._set_slot("budget", budget))
            if timeline:
                events.append(self._set_slot("timeline", timeline))
            if technology:
                events.append(self._set_slot("technology", technology))
            
            # Check if we have enough information
            required_info = [industry, budget, timeline, technology]
            missing_count = sum(1 for info in required_info if not info)
            
            if missing_count == 0:
                # All information collected
                dispatcher.utter_message(response="utter_confirm_requirements")
                events.append(self._followup_action("action_quote_estimator"))
            elif missing_count <= 2:
                # Some information missing, ask for specific details
                missing_fields = []
                if not industry:
                    missing_fields.append("industry")
                if not budget:
                    missing_fields.append("budget range")
                if not timeline:
                    missing_fields.append("timeline")
                if not technology:
                    missing_fields.append("technology preferences")
                
                dispatcher.utter_message(
                    text=f"Great! I have some information. Could you tell me about your {', '.join(missing_fields)}?"
                )
                events.append(self._followup_action("action_listen"))
            else:
                # Need more information
                dispatcher.utter_message(response="utter_ask_requirements")
                events.append(self._followup_action("action_listen"))
            
            self._log_action_end(self.name(), user_id, success=True)
            self._track_action(self.name(), user_id, 
                             industry=industry, budget=budget, 
                             timeline=timeline, technology=technology)
            
            return events
            
        except Exception as e:
            return self._handle_error(e, self.name(), user_id)
    
    def _extract_industry(self, text: str, current: Optional[str]) -> Optional[str]:
        """Extract industry from text"""
        if current:
            return current
        
        industry_keywords = {
            "healthcare": ["health", "medical", "hospital", "patient", "healthcare"],
            "finance": ["finance", "banking", "fintech", "financial"],
            "retail": ["retail", "ecommerce", "shopping", "store"],
            "education": ["education", "learning", "school", "university"],
            "iot": ["iot", "smart", "sensor", "connected"],
            "ai": ["ai", "machine learning", "automation", "predict", "artificial intelligence"],
            "manufacturing": ["manufacturing", "factory", "production"],
            "logistics": ["logistics", "supply chain", "shipping"]
        }
        
        for industry, keywords in industry_keywords.items():
            if any(keyword in text for keyword in keywords):
                return industry
        
        return None
    
    def _extract_budget(self, text: str, current: Optional[str]) -> Optional[str]:
        """Extract budget from text"""
        if current:
            return current
        
        budget_patterns = [
            r"\$?\s?(\d+\s*(k|k\+|\,?\d{3})?)",
            r"(\d+)\s*(thousand|k)",
            r"budget.*?(\d+)",
            r"cost.*?(\d+)",
            r"(\d+k)",
            r"(\d+\s*k)"
        ]
        
        for pattern in budget_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0)
        
        return None
    
    def _extract_timeline(self, text: str, current: Optional[str]) -> Optional[str]:
        """Extract timeline from text"""
        if current:
            return current
        
        timeline_patterns = [
            (r"(\d+)\s*month", lambda m: f"{m.group(1)} month{'s' if int(m.group(1)) > 1 else ''}"),
            (r"(\d+)\s*week", lambda m: f"{m.group(1)} week{'s' if int(m.group(1)) > 1 else ''}"),
            (r"(\d+)\s*day", lambda m: f"{m.group(1)} day{'s' if int(m.group(1)) > 1 else ''}"),
        ]
        
        for pattern, formatter in timeline_patterns:
            match = re.search(pattern, text)
            if match:
                return formatter(match)
        
        # Fallback to keyword matching
        timeline_keywords = {
            "urgent": ["urgent", "asap", "immediately", "quick"],
            "1 month": ["1 month", "one month", "monthly"],
            "3 months": ["3 months", "quarterly", "three months"],
            "6 months": ["6 months", "half year", "six months"],
            "1 year": ["1 year", "yearly", "annual"]
        }
        
        for timeline, keywords in timeline_keywords.items():
            if any(keyword in text for keyword in keywords):
                return timeline
        
        return None
    
    def _extract_technology(self, text: str, current: Optional[str]) -> Optional[str]:
        """Extract technology preferences from text"""
        if current:
            return current
        
        tech_keywords = {
            "react": ["react", "reactjs", "javascript", "js"],
            "python": ["python", "django", "flask", "fastapi"],
            "node": ["node", "nodejs", "express", "javascript"],
            "ai": ["ai", "machine learning", "tensorflow", "pytorch"],
            "iot": ["iot", "arduino", "raspberry pi", "sensors"],
            "mobile": ["mobile", "ios", "android", "react native", "flutter"]
        }
        
        for tech, keywords in tech_keywords.items():
            if any(keyword in text for keyword in keywords):
                return tech
        
        return None
