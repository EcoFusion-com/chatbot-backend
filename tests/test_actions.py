"""
Unit tests for Eco Fusion chatbot actions.
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any

from actions.actions import (
    ActionQuoteEstimator, ActionGenerateProposal, ActionCreateCalendarLink,
    ActionPushToCRM, ActionHandoffToHuman, ActionHandleRequirements
)
from actions.analytics import track_event, track_quote_generated, get_analytics_summary


class TestActionQuoteEstimator:
    """Test quote estimator action."""
    
    def setup_method(self):
        self.action = ActionQuoteEstimator()
        self.dispatcher = Mock()
        self.tracker = Mock()
        self.domain = {}
    
    def test_calculate_quote_ai_automation_small(self):
        """Test quote calculation for small AI automation project."""
        quote = self.action._calculate_quote(
            industry="healthcare",
            budget="flexible",
            timeline="3 months",
            technology="AI chatbot",
            project_size="small",
            compliance="standard"
        )
        # Base: 8000, healthcare: 1.3, standard compliance: 1.2, 3 months: 1.0
        # Expected: 8000 * 1.3 * 1.2 = 12480, range: 9984-14976
        assert "$9,984 - $14,976" in quote
    
    def test_calculate_quote_iot_large(self):
        """Test quote calculation for large IoT project."""
        quote = self.action._calculate_quote(
            industry="manufacturing",
            budget="100k",
            timeline="6 months",
            technology="IoT sensors",
            project_size="large",
            compliance="none"
        )
        # Base: 50000, manufacturing: 1.1, no compliance: 1.0, 6 months: 0.9
        # Expected: 50000 * 1.1 * 0.9 = 49500, range: 39600-59400
        assert "$39,600 - $59,400" in quote
    
    def test_calculate_quote_fullstack_medium(self):
        """Test quote calculation for medium full-stack project."""
        quote = self.action._calculate_quote(
            industry="ecommerce",
            budget="50k",
            timeline="2 months",
            technology="React Django",
            project_size="medium",
            compliance="none"
        )
        # Base: 20000, ecommerce: 1.0, no compliance: 1.0, 2 months: 1.3
        # Expected: 20000 * 1.3 = 26000, range: 20800-31200
        assert "$20,800 - $31,200" in quote
    
    @patch('actions.actions.track_quote_generated')
    def test_run_with_slots(self, mock_track):
        """Test action run with slot values."""
        self.tracker.get_slot.side_effect = lambda slot: {
            "industry": "healthcare",
            "budget": "50k",
            "timeline": "3 months",
            "technology": "AI",
            "project_size": "medium",
            "compliance": "standard"
        }.get(slot)
        
        self.action.run(self.dispatcher, self.tracker, self.domain)
        
        self.dispatcher.utter_message.assert_called_once()
        mock_track.assert_called_once()


class TestActionGenerateProposal:
    """Test proposal generation action."""
    
    def setup_method(self):
        self.action = ActionGenerateProposal()
        self.dispatcher = Mock()
        self.tracker = Mock()
        self.domain = {}
    
    def test_create_template(self):
        """Test proposal template creation."""
        template = self.action._create_template(
            industry="healthcare",
            budget="50k",
            timeline="3 months",
            technology="AI",
            project_size="medium",
            compliance="standard"
        )
        
        assert "Eco Fusion Project Proposal" in template
        assert "Industry: healthcare" in template
        assert "Technology Stack: AI" in template
        assert "Project Size: medium" in template
    
    @patch('actions.actions.call_hf_llm')
    @patch('actions.actions.track_proposal_generated')
    def test_run_with_hf_polish(self, mock_track, mock_hf):
        """Test proposal generation with HF polish."""
        mock_hf.return_value = "Enhanced proposal content"
        
        self.tracker.get_slot.side_effect = lambda slot: {
            "industry": "healthcare",
            "budget": "50k",
            "timeline": "3 months",
            "technology": "AI",
            "project_size": "medium",
            "compliance": "standard"
        }.get(slot)
        
        with patch.dict('os.environ', {'HF_API_KEY': 'test_key'}):
            self.action.run(self.dispatcher, self.tracker, self.domain)
        
        mock_hf.assert_called_once()
        mock_track.assert_called_once()
        self.dispatcher.utter_message.assert_called_once()
    
    @patch('actions.actions.track_proposal_generated')
    def test_run_without_hf(self, mock_track):
        """Test proposal generation without HF (fallback)."""
        self.tracker.get_slot.side_effect = lambda slot: {
            "industry": "healthcare",
            "budget": "50k",
            "timeline": "3 months",
            "technology": "AI",
            "project_size": "medium",
            "compliance": "standard"
        }.get(slot)
        
        with patch.dict('os.environ', {}, clear=True):
            self.action.run(self.dispatcher, self.tracker, self.domain)
        
        mock_track.assert_called_once()
        self.dispatcher.utter_message.assert_called_once()


class TestActionCreateCalendarLink:
    """Test calendar link creation action."""
    
    def setup_method(self):
        self.action = ActionCreateCalendarLink()
        self.dispatcher = Mock()
        self.tracker = Mock()
        self.domain = {}
    
    @patch('actions.actions.track_calendar_link_created')
    def test_run_with_slots(self, mock_track):
        """Test calendar link creation with slot values."""
        self.tracker.get_slot.side_effect = lambda slot: {
            "industry": "healthcare",
            "technology": "AI",
            "email": "test@example.com"
        }.get(slot)
        
        with patch.dict('actions.actions.CALENDAR_BASE_URL', 'https://calendly.com/ecofusion'):
            self.action.run(self.dispatcher, self.tracker, self.domain)
        
        mock_track.assert_called_once_with("test@example.com", "consultation")
        self.dispatcher.utter_message.assert_called_once()


class TestActionPushToCRM:
    """Test CRM push action."""
    
    def setup_method(self):
        self.action = ActionPushToCRM()
        self.dispatcher = Mock()
        self.tracker = Mock()
        self.domain = {}
    
    @patch('actions.actions.requests.post')
    @patch('actions.actions.track_crm_push_attempted')
    def test_run_success(self, mock_track, mock_post):
        """Test successful CRM push."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        self.tracker.get_slot.side_effect = lambda slot: {
            "name": "John Doe",
            "email": "john@example.com",
            "industry": "healthcare",
            "budget": "50k",
            "timeline": "3 months",
            "technology": "AI"
        }.get(slot)
        
        with patch.dict('actions.actions.CRM_WEBHOOK_URL', 'https://api.example.com/crm'):
            self.action.run(self.dispatcher, self.tracker, self.domain)
        
        mock_post.assert_called_once()
        mock_track.assert_called_once()
        self.dispatcher.utter_message.assert_called_once()
    
    def test_run_no_webhook_url(self):
        """Test CRM push without webhook URL configured."""
        with patch.dict('actions.actions.CRM_WEBHOOK_URL', None):
            self.action.run(self.dispatcher, self.tracker, self.domain)
        
        self.dispatcher.utter_message.assert_called_with(text="CRM integration not configured.")


class TestActionHandoffToHuman:
    """Test human handoff action."""
    
    def setup_method(self):
        self.action = ActionHandoffToHuman()
        self.dispatcher = Mock()
        self.tracker = Mock()
        self.domain = {}
    
    @patch('actions.actions.track_handoff_requested')
    def test_run(self, mock_track):
        """Test human handoff action."""
        self.tracker.sender_id = "test_user_123"
        self.tracker.latest_message = {"text": "I need a human"}
        self.tracker.events = [{"event": "user"}, {"event": "bot"}, {"event": "user"}]
        self.tracker.get_slot.side_effect = lambda slot: {
            "industry": "healthcare",
            "budget": "50k",
            "timeline": "3 months",
            "technology": "AI"
        }.get(slot)
        
        self.action.run(self.dispatcher, self.tracker, self.domain)
        
        mock_track.assert_called_once_with("user_requested", 3)
        assert self.dispatcher.utter_message.call_count == 3


class TestActionHandleRequirements:
    """Test requirements handling action with slot validation fix."""
    
    def setup_method(self):
        self.action = ActionHandleRequirements()
        self.dispatcher = Mock()
        self.tracker = Mock()
        self.domain = {}
    
    def test_extract_slots_only_industry(self):
        """Test that only mentioned slots are updated."""
        self.tracker.get_slot.side_effect = lambda slot: {
            "industry": "existing_industry",
            "budget": "existing_budget",
            "timeline": "existing_timeline",
            "technology": "existing_technology"
        }.get(slot)
        
        self.tracker.latest_message = {
            "entities": [{"entity": "industry", "value": "new_industry"}]
        }
        
        industry, budget, timeline, technology = self.action._extract_slots(self.tracker)
        
        assert industry == "new_industry"
        assert budget == "existing_budget"
        assert timeline == "existing_timeline"
        assert technology == "existing_technology"
    
    def test_extract_slots_only_budget(self):
        """Test that only budget slot is updated when only budget is mentioned."""
        self.tracker.get_slot.side_effect = lambda slot: {
            "industry": "existing_industry",
            "budget": "existing_budget",
            "timeline": "existing_timeline",
            "technology": "existing_technology"
        }.get(slot)
        
        self.tracker.latest_message = {
            "entities": [{"entity": "budget", "value": "new_budget"}]
        }
        
        industry, budget, timeline, technology = self.action._extract_slots(self.tracker)
        
        assert industry == "existing_industry"
        assert budget == "new_budget"
        assert timeline == "existing_timeline"
        assert technology == "existing_technology"


class TestAnalytics:
    """Test analytics functionality."""
    
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.analytics_file = Path(self.temp_dir) / "analytics.jsonl"
    
    def teardown_method(self):
        import shutil
        shutil.rmtree(self.temp_dir)
    
    @patch('actions.analytics.ANALYTICS_FILE')
    def test_track_event(self, mock_file):
        """Test event tracking."""
        mock_file.__str__ = lambda: str(self.analytics_file)
        mock_file.parent.mkdir = Mock()
        mock_file.exists.return_value = False
        
        success = track_event("test_event", {"key": "value"})
        
        assert success
        assert self.analytics_file.exists()
        
        with open(self.analytics_file, 'r') as f:
            line = f.readline().strip()
            data = json.loads(line)
            assert data["event"] == "test_event"
            assert data["payload"]["key"] == "value"
    
    @patch('actions.analytics.ANALYTICS_FILE')
    def test_track_quote_generated(self, mock_file):
        """Test quote generation tracking."""
        mock_file.__str__ = lambda: str(self.analytics_file)
        mock_file.parent.mkdir = Mock()
        mock_file.exists.return_value = False
        
        success = track_quote_generated(
            industry="healthcare",
            budget="50k",
            timeline="3 months",
            technology="AI",
            project_size="medium",
            compliance="standard",
            quote_range="$10k - $15k"
        )
        
        assert success
        assert self.analytics_file.exists()
    
    @patch('actions.analytics.ANALYTICS_FILE')
    def test_get_analytics_summary(self, mock_file):
        """Test analytics summary generation."""
        mock_file.__str__ = lambda: str(self.analytics_file)
        
        # Create test analytics file
        test_data = [
            {"event": "quote_generated", "timestamp": 1234567890},
            {"event": "proposal_generated", "timestamp": 1234567891},
            {"event": "quote_generated", "timestamp": 1234567892}
        ]
        
        with open(self.analytics_file, 'w') as f:
            for data in test_data:
                f.write(json.dumps(data) + '\n')
        
        summary = get_analytics_summary()
        
        assert summary["total_events"] == 3
        assert summary["events"]["quote_generated"] == 2
        assert summary["events"]["proposal_generated"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
