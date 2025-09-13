"""
Analytics tracking utility for Eco Fusion chatbot.
Tracks key events and appends JSON lines to logs/analytics.jsonl.
"""

import os
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Analytics configuration
ANALYTICS_FILE = Path("logs/analytics.jsonl")
MAX_FILE_SIZE_MB = 10
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024


def ensure_logs_directory() -> None:
    """Ensure the logs directory exists."""
    ANALYTICS_FILE.parent.mkdir(exist_ok=True)


def rotate_file_if_needed() -> None:
    """Rotate analytics file if it exceeds size limit."""
    if not ANALYTICS_FILE.exists():
        return
    
    try:
        if ANALYTICS_FILE.stat().st_size > MAX_FILE_SIZE_BYTES:
            timestamp = int(time.time())
            backup_file = ANALYTICS_FILE.parent / f"analytics_{timestamp}.jsonl"
            ANALYTICS_FILE.rename(backup_file)
            logger.info(f"Rotated analytics file to {backup_file}")
    except Exception as e:
        logger.error(f"Failed to rotate analytics file: {e}")


def track_event(event_name: str, payload: Optional[Dict[str, Any]] = None) -> bool:
    """
    Track an event by appending a JSON line to the analytics file.
    
    Args:
        event_name: Name of the event to track
        payload: Optional dictionary of event data
        
    Returns:
        True if tracking was successful, False otherwise
    """
    try:
        ensure_logs_directory()
        rotate_file_if_needed()
        
        event_data = {
            "timestamp": time.time(),
            "event": event_name,
            "payload": payload or {}
        }
        
        with open(ANALYTICS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(event_data, ensure_ascii=False) + "\n")
        
        logger.debug(f"Tracked event: {event_name}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to track event {event_name}: {e}")
        return False


def track_quote_generated(industry: str, budget: str, timeline: str, technology: str, 
                         project_size: str, compliance: str, quote_range: str) -> bool:
    """Track quote generation event."""
    return track_event("quote_generated", {
        "industry": industry,
        "budget": budget,
        "timeline": timeline,
        "technology": technology,
        "project_size": project_size,
        "compliance": compliance,
        "quote_range": quote_range
    })


def track_proposal_generated(industry: str, budget: str, timeline: str, technology: str,
                           llm_used: bool, proposal_length: int) -> bool:
    """Track proposal generation event."""
    return track_event("proposal_generated", {
        "industry": industry,
        "budget": budget,
        "timeline": timeline,
        "technology": technology,
        "llm_used": llm_used,
        "proposal_length": proposal_length
    })


def track_calendar_link_created(user_email: str, meeting_type: str) -> bool:
    """Track calendar link creation event."""
    return track_event("calendar_link_created", {
        "user_email": user_email,
        "meeting_type": meeting_type
    })


def track_crm_push_attempted(lead_data: Dict[str, Any], success: bool) -> bool:
    """Track CRM push attempt event."""
    return track_event("crm_push_attempted", {
        "lead_data": lead_data,
        "success": success
    })


def track_handoff_requested(reason: str, conversation_length: int) -> bool:
    """Track human handoff request event."""
    return track_event("handoff_requested", {
        "reason": reason,
        "conversation_length": conversation_length
    })


def get_analytics_summary() -> Dict[str, Any]:
    """Get a summary of analytics data."""
    try:
        if not ANALYTICS_FILE.exists():
            return {"total_events": 0, "events": {}}
        
        events = {}
        total_events = 0
        
        with open(ANALYTICS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    data = json.loads(line.strip())
                    event_name = data.get("event", "unknown")
                    events[event_name] = events.get(event_name, 0) + 1
                    total_events += 1
                except json.JSONDecodeError:
                    continue
        
        return {
            "total_events": total_events,
            "events": events
        }
        
    except Exception as e:
        logger.error(f"Failed to get analytics summary: {e}")
        return {"total_events": 0, "events": {}, "error": str(e)}
