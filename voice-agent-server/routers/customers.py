import json
import logging
import uuid

from starlette.requests import Request
from starlette.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import async_session
from models.customer import Customer
from services.deepgram import create_agent_config, delete_agent_config, update_agent_config
from services.twilio_client import buy_phone_number, configure_voice_url, release_phone_number
from config import settings

logger = logging.getLogger(__name__)


async def list_customers(request: Request) -> JSONResponse:
    async with async_session() as db:
        result = await db.execute(select(Customer).order_by(Customer.created_at.desc()))
        customers = result.scalars().all()
        return JSONResponse([_customer_to_dict(c) for c in customers])


async def create_customer(request: Request) -> JSONResponse:
    body = await request.json()
    async with async_session() as db:
        customer = Customer(
            business_name=body["business_name"],
            owner_name=body.get("owner_name"),
            email=body["email"],
            phone=body.get("phone"),
            timezone=body.get("timezone", "America/Vancouver"),
            business_hours=body.get("business_hours"),
            faqs=body.get("faqs"),
            greeting=body.get("greeting"),
        )
        db.add(customer)
        await db.flush()

        customer_dict = _customer_to_dict(customer)

        try:
            agent_id = await create_agent_config(customer_dict)
            customer.deepgram_agent_id = agent_id
            logger.info("Created Deepgram agent %s for customer %s", agent_id, customer.id)
        except Exception as e:
            logger.error("Failed to create Deepgram agent: %s", e)

        try:
            area_code = body.get("area_code", "604")
            number = buy_phone_number(area_code)
            customer.twilio_phone_number = number["phone_number"]

            voice_url = f"https://{settings.domain}/incoming-call/{customer.id}"
            configure_voice_url(number["sid"], voice_url)
            logger.info("Provisioned number %s for customer %s", number["phone_number"], customer.id)
        except Exception as e:
            logger.error("Failed to provision Twilio number: %s", e)

        await db.commit()
        await db.refresh(customer)

        return JSONResponse(_customer_to_dict(customer), status_code=201)


async def get_customer(request: Request) -> JSONResponse:
    customer_id = request.path_params["customer_id"]
    async with async_session() as db:
        customer = await db.get(Customer, uuid.UUID(customer_id))
        if not customer:
            return JSONResponse({"error": "Customer not found"}, status_code=404)
        return JSONResponse(_customer_to_dict(customer))


async def update_customer(request: Request) -> JSONResponse:
    customer_id = request.path_params["customer_id"]
    body = await request.json()

    async with async_session() as db:
        customer = await db.get(Customer, uuid.UUID(customer_id))
        if not customer:
            return JSONResponse({"error": "Customer not found"}, status_code=404)

        for field in (
            "business_name", "owner_name", "phone", "timezone",
            "business_hours", "faqs", "greeting", "status",
        ):
            if field in body:
                setattr(customer, field, body[field])

        await db.commit()
        await db.refresh(customer)

        if customer.deepgram_agent_id:
            try:
                await update_agent_config(customer.deepgram_agent_id, _customer_to_dict(customer))
            except Exception as e:
                logger.error("Failed to update Deepgram agent: %s", e)

        return JSONResponse(_customer_to_dict(customer))


async def delete_customer(request: Request) -> JSONResponse:
    customer_id = request.path_params["customer_id"]

    async with async_session() as db:
        customer = await db.get(Customer, uuid.UUID(customer_id))
        if not customer:
            return JSONResponse({"error": "Customer not found"}, status_code=404)

        if customer.deepgram_agent_id:
            try:
                await delete_agent_config(customer.deepgram_agent_id)
            except Exception as e:
                logger.error("Failed to delete Deepgram agent: %s", e)

        if customer.twilio_phone_number:
            try:
                release_phone_number(customer.twilio_phone_number)
            except Exception as e:
                logger.error("Failed to release Twilio number: %s", e)

        await db.delete(customer)
        await db.commit()

        return JSONResponse({"status": "deleted"})


async def get_customer_calls(request: Request) -> JSONResponse:
    customer_id = request.path_params["customer_id"]
    async with async_session() as db:
        from models.call_log import CallLog
        result = await db.execute(
            select(CallLog)
            .where(CallLog.customer_id == uuid.UUID(customer_id))
            .order_by(CallLog.started_at.desc())
            .limit(100)
        )
        calls = result.scalars().all()
        return JSONResponse([
            {
                "id": str(c.id),
                "caller_number": c.caller_number,
                "call_sid": c.call_sid,
                "started_at": c.started_at.isoformat() if c.started_at else None,
                "ended_at": c.ended_at.isoformat() if c.ended_at else None,
                "duration_seconds": c.duration_seconds,
                "outcome": c.outcome,
                "summary": c.summary,
            }
            for c in calls
        ])


def _customer_to_dict(c: Customer) -> dict:
    return {
        "id": str(c.id),
        "business_name": c.business_name,
        "owner_name": c.owner_name,
        "email": c.email,
        "phone": c.phone,
        "timezone": c.timezone,
        "twilio_phone_number": c.twilio_phone_number,
        "deepgram_agent_id": c.deepgram_agent_id,
        "business_hours": c.business_hours,
        "faqs": c.faqs,
        "greeting": c.greeting,
        "calendar_integration": c.calendar_integration,
        "stripe_customer_id": c.stripe_customer_id,
        "stripe_subscription_id": c.stripe_subscription_id,
        "status": c.status,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }
