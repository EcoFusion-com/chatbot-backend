"""
Quote Estimation Action
Handles project quote generation based on requirements
"""

from typing import Any, Dict, List, Text
from rasa_sdk import Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, FollowupAction

from .base_action import _BaseAction as BaseAction
from .analytics import track_quote_generated

class ActionQuoteEstimator(BaseAction):
    """Generates project quotes based on requirements"""
    
    def name(self) -> Text:
        return "action_quote_estimator"
    
    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        user_id = self._get_user_id(tracker)
        self._log_action_start(self.name(), user_id)
        
        try:
            # Get project requirements
            industry = self._get_slot_value(tracker, "industry") or "general"
            budget = self._normalize_budget(self._get_slot_value(tracker, "budget")) or "flexible"
            timeline = self._get_slot_value(tracker, "timeline") or "3 months"
            technology = self._get_slot_value(tracker, "technology") or "full-stack"
            
            # Calculate quote
            quote_data = self._calculate_quote(industry, budget, timeline, technology)
            
            # Generate quote message
            quote_message = self._generate_quote_message(quote_data)
            
            # Send quote to user
            dispatcher.utter_message(text=quote_message)
            
            # Track quote generation
            track_quote_generated(
                industry=industry,
                budget=budget,
                timeline=timeline,
                technology=technology,
                estimated_cost=quote_data["estimated_cost"],
                confidence=quote_data["confidence"]
            )
            
            # Ask if user wants to proceed
            dispatcher.utter_message(
                text="Would you like me to generate a detailed proposal or schedule a consultation?",
                buttons=self._create_buttons([
                    {"title": "Generate Proposal", "payload": "/ask_quote"},
                    {"title": "Schedule Consultation", "payload": "/book_meeting"},
                    {"title": "Ask Questions", "payload": "/ask_services"}
                ])
            )
            
            self._log_action_end(self.name(), user_id, success=True)
            self._track_action(self.name(), user_id, 
                             industry=industry, budget=budget, 
                             timeline=timeline, technology=technology,
                             estimated_cost=quote_data["estimated_cost"])
            
            return [self._followup_action("action_listen")]
            
        except Exception as e:
            return self._handle_error(e, self.name(), user_id)
    
    def _calculate_quote(self, industry: str, budget: str, timeline: str, technology: str) -> Dict[str, Any]:
        """Calculate project quote based on requirements"""
        
        # Base pricing by technology
        base_prices = {
            "ai": {"min": 15000, "max": 50000},
            "iot": {"min": 10000, "max": 40000},
            "react": {"min": 8000, "max": 25000},
            "python": {"min": 10000, "max": 35000},
            "node": {"min": 8000, "max": 25000},
            "mobile": {"min": 12000, "max": 40000},
            "full-stack": {"min": 15000, "max": 50000}
        }
        
        # Industry multipliers
        industry_multipliers = {
            "healthcare": 1.3,  # Higher due to compliance requirements
            "finance": 1.4,     # Higher due to security requirements
            "retail": 1.1,      # Standard
            "education": 0.9,   # Slightly lower
            "iot": 1.2,         # Specialized
            "ai": 1.5,          # High complexity
            "manufacturing": 1.2,
            "logistics": 1.1,
            "general": 1.0
        }
        
        # Timeline multipliers
        timeline_multipliers = {
            "urgent": 1.5,      # Rush job
            "1 month": 1.3,     # Fast delivery
            "3 months": 1.0,    # Standard
            "6 months": 0.9,    # More time
            "1 year": 0.8       # Long term
        }
        
        # Get base price for technology
        tech_prices = base_prices.get(technology, base_prices["full-stack"])
        base_min = tech_prices["min"]
        base_max = tech_prices["max"]
        
        # Apply multipliers
        industry_mult = industry_multipliers.get(industry, 1.0)
        timeline_mult = timeline_multipliers.get(timeline, 1.0)
        
        # Calculate final range
        final_min = int(base_min * industry_mult * timeline_mult)
        final_max = int(base_max * industry_mult * timeline_mult)
        
        # Calculate confidence based on how much info we have
        confidence = 0.8
        if budget == "flexible":
            confidence -= 0.1
        if industry == "general":
            confidence -= 0.1
        if technology == "full-stack":
            confidence -= 0.1
        
        return {
            "estimated_cost": f"${final_min:,} - ${final_max:,}",
            "min_cost": final_min,
            "max_cost": final_max,
            "confidence": confidence,
            "timeline": timeline,
            "industry": industry,
            "technology": technology
        }
    
    def _generate_quote_message(self, quote_data: Dict[str, Any]) -> str:
        """Generate human-readable quote message"""
        
        confidence_percent = int(quote_data["confidence"] * 100)
        
        message = f"""
📊 **Project Quote Estimate**

**Estimated Cost:** {quote_data["estimated_cost"]}
**Timeline:** {quote_data["timeline"]}
**Industry:** {quote_data["industry"].title()}
**Technology:** {quote_data["technology"].title()}

**Confidence Level:** {confidence_percent}%

This estimate is based on your requirements and includes:
• Full project development
• Testing and quality assurance
• Deployment and setup
• 3 months of post-launch support
• Documentation and training

*Note: Final pricing may vary based on detailed requirements and project scope.*
        """.strip()
        
        return message
