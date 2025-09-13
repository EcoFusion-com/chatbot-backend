"""
Configuration Management for Eco Fusion Chatbot
Centralized configuration with environment variable validation
"""

import os
import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class DatabaseConfig:
    """Database configuration"""
    host: str
    port: int
    name: str
    user: str
    password: str

@dataclass
class EmailConfig:
    """Email configuration"""
    admin_email: str
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str

@dataclass
class HuggingFaceConfig:
    """Hugging Face configuration"""
    token: str
    api_key: str
    model_name: str
    router_url: str = "https://router.huggingface.co/v1"

@dataclass
class GoogleCalendarConfig:
    """Google Calendar configuration"""
    api_key: Optional[str] = None
    calendar_id: Optional[str] = None
    credentials_file: Optional[str] = None

@dataclass
class CRMConfig:
    """CRM integration configuration"""
    webhook_url: Optional[str] = None

@dataclass
class ServerConfig:
    """Server configuration"""
    rasa_port: int = 5005
    actions_port: int = 5055
    cors_origins: List[str] = None

@dataclass
class RateLimitConfig:
    """Rate limiting configuration"""
    max_requests: int = 20
    window_seconds: int = 60

@dataclass
class LoggingConfig:
    """Logging configuration"""
    level: str = "INFO"
    analytics_enabled: bool = True

class Config:
    """Main configuration class"""
    
    def __init__(self):
        self._validate_required_env_vars()
        self._load_config()
    
    def _validate_required_env_vars(self) -> None:
        """Validate that required environment variables are set"""
        required_vars = [
            'HF_TOKEN',
            'ADMIN_EMAIL',
            'SMTP_HOST',
            'SMTP_USER',
            'SMTP_PASS'
        ]
        
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        if missing_vars:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing_vars)}\n"
                "Please check your .env file and ensure all required variables are set."
            )
    
    def _load_config(self) -> None:
        """Load configuration from environment variables"""
        
        # Hugging Face configuration
        self.huggingface = HuggingFaceConfig(
            token=os.getenv('HF_TOKEN', ''),
            api_key=os.getenv('HF_API_KEY', '') or os.getenv('HF_TOKEN', ''),
            model_name=os.getenv('HF_MODEL_NAME', 'microsoft/DialoGPT-medium')
        )
        
        # Email configuration
        self.email = EmailConfig(
            admin_email=os.getenv('ADMIN_EMAIL', ''),
            smtp_host=os.getenv('SMTP_HOST', 'smtp.gmail.com'),
            smtp_port=int(os.getenv('SMTP_PORT', '587')),
            smtp_user=os.getenv('SMTP_USER', ''),
            smtp_password=os.getenv('SMTP_PASS', '')
        )
        
        # Google Calendar configuration
        self.google_calendar = GoogleCalendarConfig(
            api_key=os.getenv('GOOGLE_CALENDAR_API_KEY'),
            calendar_id=os.getenv('GOOGLE_CALENDAR_ID'),
            credentials_file=os.getenv('GOOGLE_CALENDAR_CREDENTIALS_FILE')
        )
        
        # CRM configuration
        self.crm = CRMConfig(
            webhook_url=os.getenv('CRM_WEBHOOK_URL')
        )
        
        # Server configuration
        cors_origins_str = os.getenv('CORS_ORIGINS', 'http://localhost:5173,http://localhost:3000')
        self.server = ServerConfig(
            rasa_port=int(os.getenv('RASA_SERVER_PORT', '5005')),
            actions_port=int(os.getenv('ACTIONS_SERVER_PORT', '5055')),
            cors_origins=cors_origins_str.split(',') if cors_origins_str else []
        )
        
        # Rate limiting configuration
        self.rate_limit = RateLimitConfig(
            max_requests=int(os.getenv('RATE_LIMIT_MAX_REQUESTS', '20')),
            window_seconds=int(os.getenv('RATE_LIMIT_WINDOW_SECONDS', '60'))
        )
        
        # Logging configuration
        self.logging = LoggingConfig(
            level=os.getenv('LOG_LEVEL', 'INFO'),
            analytics_enabled=os.getenv('ANALYTICS_ENABLED', 'true').lower() == 'true'
        )
    
    def get_huggingface_headers(self) -> Dict[str, str]:
        """Get Hugging Face API headers"""
        if self.huggingface.token:
            return {"Authorization": f"Bearer {self.huggingface.token}"}
        return {}
    
    def get_router_headers(self) -> Dict[str, str]:
        """Get Hugging Face router headers"""
        if self.huggingface.token:
            return {"Authorization": f"Bearer {self.huggingface.token}"}
        return {}
    
    def is_google_calendar_available(self) -> bool:
        """Check if Google Calendar is properly configured"""
        return bool(self.google_calendar.api_key or self.google_calendar.credentials_file)
    
    def is_crm_available(self) -> bool:
        """Check if CRM integration is available"""
        return bool(self.crm.webhook_url)
    
    def get_cors_origins(self) -> List[str]:
        """Get CORS origins list"""
        return self.server.cors_origins or ['http://localhost:5173']
    
    def validate_config(self) -> None:
        """Validate the entire configuration"""
        logger.info("Validating configuration...")
        
        # Validate email configuration
        if not self.email.admin_email or '@' not in self.email.admin_email:
            raise ValueError("Invalid ADMIN_EMAIL configuration")
        
        # Validate SMTP configuration
        if not self.email.smtp_host or not self.email.smtp_user:
            raise ValueError("Invalid SMTP configuration")
        
        # Validate Hugging Face configuration
        if not self.huggingface.token:
            logger.warning("HF_TOKEN not set - LLM features will be limited")
        
        # Validate Google Calendar if configured
        if self.google_calendar.api_key and not self.google_calendar.calendar_id:
            logger.warning("GOOGLE_CALENDAR_ID not set - calendar features may not work")
        
        logger.info("Configuration validation completed successfully")

# Global configuration instance
config = Config()

# Validate configuration on import
try:
    config.validate_config()
except Exception as e:
    logger.error(f"Configuration validation failed: {e}")
    raise
