from __future__ import annotations

import os
import logging
from typing import Any, Dict, Optional

import requests
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

# Environment variables expected:
# HUBSPOT_API_KEY, HUBSPOT_BASE_URL (optional, default https://api.hubapi.com)
# DATABASE_URL e.g. postgresql+psycopg2://user:pass@host:5432/dbname


def get_db_engine() -> Optional[Engine]:
    """Create and return a SQLAlchemy Engine if DATABASE_URL present, else None."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        return None
    try:
        engine = create_engine(database_url, pool_pre_ping=True, pool_size=5, max_overflow=5)
        return engine
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to create DB engine: %s", exc)
        return None


def ensure_leads_table(engine: Engine) -> None:
    """Ensure a simple leads table exists for storing lead info."""
    ddl = """
    CREATE TABLE IF NOT EXISTS leads (
        id SERIAL PRIMARY KEY,
        name TEXT,
        email TEXT,
        service TEXT,
        budget TEXT,
        timeline TEXT,
        source TEXT DEFAULT 'rasa',
        created_at TIMESTAMP DEFAULT NOW()
    )
    """
    with engine.begin() as conn:
        conn.execute(text(ddl))


def store_lead_postgres(payload: Dict[str, Any]) -> bool:
    """Store a lead in Postgres if DATABASE_URL set."""
    engine = get_db_engine()
    if engine is None:
        logger.info("DATABASE_URL not set; skipping Postgres lead storage")
        return False
    ensure_leads_table(engine)
    ins = text(
        """
        INSERT INTO leads (name, email, service, budget, timeline, source)
        VALUES (:name, :email, :service, :budget, :timeline, :source)
        """
    )
    try:
        with engine.begin() as conn:
            conn.execute(
                ins,
                {
                    "name": payload.get("name"),
                    "email": payload.get("email"),
                    "service": payload.get("service"),
                    "budget": payload.get("budget"),
                    "timeline": payload.get("timeline"),
                    "source": payload.get("source", "rasa"),
                },
            )
        return True
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to store lead in Postgres: %s", exc)
        return False


def store_lead_hubspot(payload: Dict[str, Any]) -> bool:
    """Store a lead in HubSpot Contacts API using private app token.

    payload keys: name, email, service, budget, timeline
    """
    api_key = os.getenv("HUBSPOT_API_KEY")
    base_url = os.getenv("HUBSPOT_BASE_URL", "https://api.hubapi.com")
    if not api_key:
        logger.info("HUBSPOT_API_KEY not set; skipping HubSpot storage")
        return False

    url = f"{base_url}/crm/v3/objects/contacts"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    properties = {
        "email": payload.get("email"),
        "firstname": (payload.get("name") or "").split(" ")[0] or None,
        "lastname": (payload.get("name") or "").split(" ")[-1] or None,
        "eco_service": payload.get("service"),
        "eco_budget": payload.get("budget"),
        "eco_timeline": payload.get("timeline"),
        "eco_source": payload.get("source", "rasa"),
    }
    # Remove None values
    properties = {k: v for k, v in properties.items() if v}
    body = {"properties": properties}

    try:
        resp = requests.post(url, headers=headers, json=body, timeout=15)
        if resp.status_code in (200, 201):
            return True
        logger.warning("HubSpot create contact failed: %s %s", resp.status_code, resp.text)
        return False
    except Exception as exc:  # noqa: BLE001
        logger.exception("HubSpot API error: %s", exc)
        return False


def store_lead(payload: Dict[str, Any]) -> bool:
    """Try HubSpot first; if not configured, try Postgres. Returns True if any succeeded."""
    ok_hs = store_lead_hubspot(payload)
    ok_db = store_lead_postgres(payload) if not ok_hs else False
    return ok_hs or ok_db
