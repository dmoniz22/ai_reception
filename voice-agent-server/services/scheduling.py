import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from sqlalchemy import select

from config import settings
from models.database import async_session
from models.customer import Customer

logger = logging.getLogger(__name__)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_CALENDAR_API = "https://www.googleapis.com/calendar/v3"


async def get_oauth_url(customer_id: str) -> str:
    redirect_uri = f"https://{settings.domain}/api/scheduling/oauth/callback"
    params = {
        "client_id": settings.google_oauth_client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "access_type": "offline",
        "prompt": "consent",
        "scope": "https://www.googleapis.com/auth/calendar",
        "state": customer_id,
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{GOOGLE_AUTH_URL}?{query}"


async def handle_oauth_callback(code: str, customer_id: str) -> None:
    redirect_uri = f"https://{settings.domain}/api/scheduling/oauth/callback"

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": settings.google_oauth_client_id,
                "client_secret": settings.google_oauth_client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            },
        )
        response.raise_for_status()
        tokens = response.json()

    async with async_session() as db:
        customer = await db.get(Customer, uuid.UUID(customer_id))
        if customer:
            customer.calendar_integration = "google_calendar"
            customer.calendar_credentials = {
                "access_token": tokens["access_token"],
                "refresh_token": tokens.get("refresh_token"),
                "expires_at": (
                    datetime.now(timezone.utc) + timedelta(seconds=tokens.get("expires_in", 3600))
                ).isoformat(),
            }
            await db.commit()
            logger.info("Google Calendar connected for customer %s", customer_id)


async def _get_valid_token(customer: Customer) -> str:
    creds = customer.calendar_credentials
    if not creds:
        raise Exception("No calendar credentials for customer")

    access_token = creds.get("access_token")
    expires_at = creds.get("expires_at")
    refresh_token = creds.get("refresh_token")

    if expires_at and datetime.fromisoformat(expires_at) > datetime.now(timezone.utc):
        return access_token

    if not refresh_token:
        raise Exception("No refresh token available, re-authorization required")

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": settings.google_oauth_client_id,
                "client_secret": settings.google_oauth_client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
        response.raise_for_status()
        tokens = response.json()

    new_access_token = tokens["access_token"]
    async with async_session() as db:
        c = await db.get(Customer, customer.id)
        if c:
            c.calendar_credentials = {
                **creds,
                "access_token": new_access_token,
                "expires_at": (
                    datetime.now(timezone.utc) + timedelta(seconds=tokens.get("expires_in", 3600))
                ).isoformat(),
            }
            await db.commit()

    return new_access_token


async def check_availability(customer_id: str, date_str: str) -> dict:
    async with async_session() as db:
        customer = await db.get(Customer, uuid.UUID(customer_id))
        if not customer or not customer.calendar_credentials:
            return {"available": False, "reason": "Calendar not connected", "slots": []}

        access_token = await _get_valid_token(customer)
        business_hours = customer.business_hours or {}

    day_name = datetime.fromisoformat(date_str).strftime("%a").lower()[:3]
    hours = business_hours.get(day_name, business_hours.get("mon", ""))

    if not hours:
        return {"available": False, "reason": "Closed on this day", "slots": []}

    start_hour, end_hour = _parse_hours(hours)
    time_min = f"{date_str}T{start_hour}:00:00"
    time_max = f"{date_str}T{end_hour}:00:00"

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{GOOGLE_CALENDAR_API}/calendars/primary/events",
            headers={"Authorization": f"Bearer {access_token}"},
            params={
                "timeMin": time_min,
                "timeMax": time_max,
                "singleEvents": "true",
                "orderBy": "startTime",
            },
        )
        response.raise_for_status()
        events = response.json().get("items", [])

    busy_slots = []
    for event in events:
        start = event.get("start", {}).get("dateTime")
        end = event.get("end", {}).get("dateTime")
        if start and end:
            busy_slots.append({"start": start, "end": end})

    available = _compute_available_slots(time_min, time_max, busy_slots)
    return {"available": len(available) > 0, "slots": available}


async def book_appointment(
    customer_id: str,
    date: str,
    time: str,
    name: str,
    phone: str,
    service: str = "Appointment",
) -> dict:
    async with async_session() as db:
        customer = await db.get(Customer, uuid.UUID(customer_id))
        if not customer or not customer.calendar_credentials:
            return {"booked": False, "reason": "Calendar not connected"}

        access_token = await _get_valid_token(customer)

    start_dt = f"{date}T{time}:00"
    end_dt = (
        datetime.fromisoformat(start_dt) + timedelta(hours=1)
    ).isoformat()

    event = {
        "summary": f"{service} - {name}",
        "description": f"Phone: {phone}\nService: {service}",
        "start": {"dateTime": start_dt, "timeZone": customer.timezone},
        "end": {"dateTime": end_dt, "timeZone": customer.timezone},
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{GOOGLE_CALENDAR_API}/calendars/primary/events",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json=event,
        )
        response.raise_for_status()
        result = response.json()

    logger.info("Booked appointment for %s at %s (event: %s)", name, start_dt, result.get("id"))
    return {
        "booked": True,
        "event_id": result.get("id"),
        "start": start_dt,
        "end": end_dt,
    }


def _parse_hours(hours: str) -> tuple[str, str]:
    parts = hours.replace(" ", "").split("-")
    if len(parts) == 2:
        start = f"{parts[0]:0>5}" if ":" in parts[0] else f"{parts[0]}:00"
        end = f"{parts[1]:0>5}" if ":" in parts[1] else f"{parts[1]}:00"
        return start, end
    return "09:00:00", "17:00:00"


def _compute_available_slots(
    time_min: str,
    time_max: str,
    busy: list[dict],
    slot_duration_min: int = 60,
) -> list[dict]:
    start = datetime.fromisoformat(time_min)
    end = datetime.fromisoformat(time_max)
    slots = []

    current = start
    while current + timedelta(minutes=slot_duration_min) <= end:
        slot_end = current + timedelta(minutes=slot_duration_min)
        is_busy = False
        for b in busy:
            b_start = datetime.fromisoformat(b["start"])
            b_end = datetime.fromisoformat(b["end"])
            if current < b_end and slot_end > b_start:
                is_busy = True
                break

        if not is_busy:
            slots.append({
                "start": current.isoformat(),
                "time": current.strftime("%I:%M %p").lstrip("0"),
            })

        current += timedelta(minutes=slot_duration_min)

    return slots
