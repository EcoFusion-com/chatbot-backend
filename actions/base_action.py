"""
Base Action Class for Eco Fusion Chatbot
Provides common functionality for all custom actions
"""

import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Text
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, FollowupAction

from .config import config
# from .analytics import track_action_execution  # Not needed for base action

logger = logging.getLogger(__name__)

class _BaseAction(Action, ABC):
    """Base class for all custom actions with common functionality"""
    
    def __init__(self):
        super().__init__()
        self.config = config
        self.logger = logger
    
    @abstractmethod
    def name(self) -> Text:
        """Override in subclasses"""
        pass
    
    @abstractmethod
    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        """Override in subclasses"""
        pass
    
    def _normalize_text(self, value: Optional[str]) -> Optional[str]:
        """Normalize text input"""
        if value is None:
            return None
        v = str(value).strip()
        return v or None
    
    def _normalize_budget(self, value: Optional[str]) -> Optional[str]:
        """Normalize budget input"""
        if value is None:
            return None
        v = str(value).strip().replace("$", "").replace(",", "")
        return v or None
    
    def _get_user_id(self, tracker: Tracker) -> str:
        """Get user ID from tracker"""
        return tracker.sender_id
    
    def _get_user_text(self, tracker: Tracker) -> str:
        """Get latest user message text"""
        return (tracker.latest_message.get("text") or "").lower()
    
    def _get_slot_value(self, tracker: Tracker, slot_name: str) -> Optional[str]:
        """Get slot value with normalization"""
        value = tracker.get_slot(slot_name)
        return self._normalize_text(value)
    
    def _set_slot(self, slot_name: str, value: Any) -> SlotSet:
        """Create a SlotSet event"""
        return SlotSet(slot_name, value)
    
    def _followup_action(self, action_name: str) -> FollowupAction:
        """Create a FollowupAction event"""
        return FollowupAction(action_name)
    
    def _log_action_start(self, action_name: str, user_id: str) -> None:
        """Log action start"""
        self.logger.info(f"Starting action: {action_name} for user: {user_id}")
    
    def _log_action_end(self, action_name: str, user_id: str, success: bool = True) -> None:
        """Log action end"""
        status = "completed" if success else "failed"
        self.logger.info(f"Action {action_name} {status} for user: {user_id}")
    
    def _handle_error(self, error: Exception, action_name: str, user_id: str) -> List[Dict[Text, Any]]:
        """Handle errors consistently"""
        self.logger.error(f"Error in {action_name} for user {user_id}: {error}")
        self._log_action_end(action_name, user_id, success=False)
        
        # Return a safe fallback response
        return [
            self._followup_action("action_listen")
        ]
    
    def _extract_entities_from_text(self, text: str, entity_patterns: Dict[str, List[str]]) -> Dict[str, str]:
        """Extract entities from text using keyword patterns"""
        extracted = {}
        
        for entity, keywords in entity_patterns.items():
            for keyword in keywords:
                if keyword in text:
                    extracted[entity] = keyword
                    break
        
        return extracted
    
    def _validate_required_slots(self, tracker: Tracker, required_slots: List[str]) -> List[str]:
        """Validate that required slots are filled"""
        missing = []
        
        for slot in required_slots:
            value = self._get_slot_value(tracker, slot)
            if not value:
                missing.append(slot)
        
        return missing
    
    def _create_buttons(self, buttons: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Create button payloads for dispatcher"""
        return [{"title": btn["title"], "payload": btn["payload"]} for btn in buttons]
