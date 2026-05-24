import json
import logging

import httpx

from config import settings
from agent_config import build_settings

logger = logging.getLogger(__name__)

DG_API = "https://api.deepgram.com/v1/projects"


async def create_agent_config(customer: dict) -> str:
    """Create a Deepgram Reusable Agent Configuration. Returns agent_id."""
    settings_msg = build_settings(
        business_name=customer.get("business_name", "AI Receptionist"),
        greeting=customer.get("greeting"),
        business_hours=str(customer.get("business_hours", "Monday-Friday 9am-5pm")),
        faqs=str(customer.get("faqs", "No FAQs configured yet.")),
        customer_id=customer.get("id", ""),
    )

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{DG_API}/{settings.deepgram_project_id}/agents",
            headers={
                "Authorization": f"Token {settings.deepgram_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "name": f"Agent for {customer.get('business_name')}",
                "config": settings_msg,
            },
        )
        response.raise_for_status()
        data = response.json()
        agent_id = data["agent_id"]
        logger.info("Created Deepgram agent config %s", agent_id)
        return agent_id


async def delete_agent_config(agent_id: str) -> None:
    """Delete a Deepgram Reusable Agent Configuration."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.delete(
            f"{DG_API}/{settings.deepgram_project_id}/agents/{agent_id}",
            headers={"Authorization": f"Token {settings.deepgram_api_key}"},
        )
        response.raise_for_status()
        logger.info("Deleted Deepgram agent config %s", agent_id)


async def get_agent_config(agent_id: str) -> dict | None:
    """Retrieve an existing agent configuration."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{DG_API}/{settings.deepgram_project_id}/agents/{agent_id}",
            headers={"Authorization": f"Token {settings.deepgram_api_key}"},
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()


async def update_agent_config(agent_id: str, customer: dict) -> None:
    """Update an existing agent configuration."""
    settings_msg = build_settings(
        business_name=customer.get("business_name", "AI Receptionist"),
        greeting=customer.get("greeting"),
        business_hours=str(customer.get("business_hours", "Monday-Friday 9am-5pm")),
        faqs=str(customer.get("faqs", "No FAQs configured yet.")),
        customer_id=customer.get("id", ""),
    )

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.put(
            f"{DG_API}/{settings.deepgram_project_id}/agents/{agent_id}",
            headers={
                "Authorization": f"Token {settings.deepgram_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "name": f"Agent for {customer.get('business_name')}",
                "config": settings_msg,
            },
        )
        response.raise_for_status()
        logger.info("Updated Deepgram agent config %s", agent_id)
