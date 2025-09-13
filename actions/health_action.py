"""
Health Check Action
Provides health status and monitoring for the chatbot system
"""

from typing import Any, Dict, List, Text
from rasa_sdk import Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet

from .base_action import _BaseAction as BaseAction
from .config import config

class ActionHealthCheck(BaseAction):
    """Provides system health status"""
    
    def name(self) -> Text:
        return "action_health_check"
    
    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        user_id = self._get_user_id(tracker)
        self._log_action_start(self.name(), user_id)
        
        try:
            # Check system health
            health_status = self._check_system_health()
            
            # Generate health report
            health_message = self._generate_health_message(health_status)
            
            # Send health status
            dispatcher.utter_message(text=health_message)
            
            self._log_action_end(self.name(), user_id, success=True)
            self._track_action(self.name(), user_id, health_status=health_status)
            
            return [self._followup_action("action_listen")]
            
        except Exception as e:
            return self._handle_error(e, self.name(), user_id)
    
    def _check_system_health(self) -> Dict[str, Any]:
        """Check the health of various system components"""
        
        health_status = {
            "overall": "healthy",
            "timestamp": time.time(),
            "components": {}
        }
        
        # Check Hugging Face API
        hf_status = self._check_huggingface_health()
        health_status["components"]["huggingface"] = hf_status
        
        # Check Google Calendar
        calendar_status = self._check_calendar_health()
        health_status["components"]["google_calendar"] = calendar_status
        
        # Check CRM integration
        crm_status = self._check_crm_health()
        health_status["components"]["crm"] = crm_status
        
        # Check email configuration
        email_status = self._check_email_health()
        health_status["components"]["email"] = email_status
        
        # Determine overall health
        component_statuses = [status["status"] for status in health_status["components"].values()]
        if "unhealthy" in component_statuses:
            health_status["overall"] = "degraded"
        if "error" in component_statuses:
            health_status["overall"] = "unhealthy"
        
        return health_status
    
    def _check_huggingface_health(self) -> Dict[str, Any]:
        """Check Hugging Face API health"""
        try:
            if not config.huggingface.token:
                return {"status": "disabled", "message": "No API token configured"}
            
            # Simple connectivity check
            import requests
            response = requests.get(
                "https://huggingface.co/api/whoami",
                headers=config.get_huggingface_headers(),
                timeout=5
            )
            
            if response.status_code == 200:
                return {"status": "healthy", "message": "API accessible"}
            else:
                return {"status": "unhealthy", "message": f"API returned {response.status_code}"}
                
        except Exception as e:
            return {"status": "error", "message": f"Connection failed: {str(e)}"}
    
    def _check_calendar_health(self) -> Dict[str, Any]:
        """Check Google Calendar health"""
        try:
            if not config.is_google_calendar_available():
                return {"status": "disabled", "message": "Calendar not configured"}
            
            return {"status": "healthy", "message": "Calendar configured"}
            
        except Exception as e:
            return {"status": "error", "message": f"Calendar check failed: {str(e)}"}
    
    def _check_crm_health(self) -> Dict[str, Any]:
        """Check CRM integration health"""
        try:
            if not config.is_crm_available():
                return {"status": "disabled", "message": "CRM not configured"}
            
            return {"status": "healthy", "message": "CRM webhook configured"}
            
        except Exception as e:
            return {"status": "error", "message": f"CRM check failed: {str(e)}"}
    
    def _check_email_health(self) -> Dict[str, Any]:
        """Check email configuration health"""
        try:
            if not config.email.admin_email or not config.email.smtp_host:
                return {"status": "unhealthy", "message": "Email configuration incomplete"}
            
            return {"status": "healthy", "message": "Email configured"}
            
        except Exception as e:
            return {"status": "error", "message": f"Email check failed: {str(e)}"}
    
    def _generate_health_message(self, health_status: Dict[str, Any]) -> str:
        """Generate human-readable health status message"""
        
        overall = health_status["overall"]
        components = health_status["components"]
        
        if overall == "healthy":
            status_emoji = "✅"
            status_text = "All systems operational"
        elif overall == "degraded":
            status_emoji = "⚠️"
            status_text = "Some systems degraded"
        else:
            status_emoji = "❌"
            status_text = "System issues detected"
        
        message = f"""
{status_emoji} **System Health Status: {status_text}**

**Component Status:**
"""
        
        for component, status in components.items():
            component_name = component.replace("_", " ").title()
            if status["status"] == "healthy":
                message += f"• {component_name}: ✅ {status['message']}\n"
            elif status["status"] == "disabled":
                message += f"• {component_name}: ⚪ {status['message']}\n"
            elif status["status"] == "unhealthy":
                message += f"• {component_name}: ⚠️ {status['message']}\n"
            else:
                message += f"• {component_name}: ❌ {status['message']}\n"
        
        message += f"\n*Last checked: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(health_status['timestamp']))}*"
        
        return message.strip()

import time
