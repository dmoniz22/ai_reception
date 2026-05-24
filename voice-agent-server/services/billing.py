import logging
import uuid

import stripe
from sqlalchemy import select

from config import settings
from models.database import async_session
from models.customer import Customer

logger = logging.getLogger(__name__)

stripe.api_key = settings.stripe_secret_key or "sk_dummy"


async def check_subscription_active(customer_id: str) -> bool:
    async with async_session() as db:
        customer = await db.get(Customer, uuid.UUID(customer_id))
        if not customer:
            return False
        return customer.status == "active"


async def create_checkout_session(customer_id: str, success_url: str, cancel_url: str) -> dict:
    async with async_session() as db:
        customer = await db.get(Customer, uuid.UUID(customer_id))
        if not customer:
            return {"error": "Customer not found"}

        stripe_customer_id = customer.stripe_customer_id
        if not stripe_customer_id:
            stripe_customer = stripe.Customer.create(
                email=customer.email,
                metadata={"customer_id": str(customer.id)},
            )
            stripe_customer_id = stripe_customer.id
            customer.stripe_customer_id = stripe_customer_id
            await db.commit()

    session = stripe.checkout.Session.create(
        customer=stripe_customer_id,
        payment_method_types=["card"],
        mode="subscription",
        line_items=[{
            "price": "price_REPLACE_ME",
            "quantity": 1,
        }],
        success_url=success_url,
        cancel_url=cancel_url,
    )

    return {"url": session.url, "session_id": session.id}


async def handle_webhook(payload: bytes, signature: str) -> dict:
    if not settings.stripe_webhook_secret:
        logger.warning("No Stripe webhook secret configured")
        return {"status": "unconfigured"}

    try:
        event = stripe.Webhook.construct_event(
            payload, signature, settings.stripe_webhook_secret
        )
    except (ValueError, stripe.error.SignatureVerificationError) as e:
        logger.error("Invalid Stripe webhook: %s", e)
        return {"status": "invalid"}

    logger.info("Stripe webhook: %s", event.type)

    if event.type == "checkout.session.completed":
        await _handle_checkout_completed(event.data.object)
    elif event.type == "customer.subscription.deleted":
        await _handle_subscription_deleted(event.data.object)
    elif event.type == "customer.subscription.updated":
        await _handle_subscription_updated(event.data.object)

    return {"status": "processed"}


async def _handle_checkout_completed(session: dict) -> None:
    stripe_customer_id = session.get("customer")
    subscription_id = session.get("subscription")

    async with async_session() as db:
        result = await db.execute(
            select(Customer).where(Customer.stripe_customer_id == stripe_customer_id)
        )
        customer = result.scalar_one_or_none()
        if customer:
            customer.stripe_subscription_id = subscription_id
            customer.status = "active"
            await db.commit()
            logger.info("Subscription active for customer %s", customer.id)


async def _handle_subscription_deleted(subscription: dict) -> None:
    stripe_customer_id = subscription.get("customer")

    async with async_session() as db:
        result = await db.execute(
            select(Customer).where(Customer.stripe_customer_id == stripe_customer_id)
        )
        customer = result.scalar_one_or_none()
        if customer:
            customer.status = "cancelled"
            customer.stripe_subscription_id = None
            await db.commit()
            logger.info("Subscription cancelled for customer %s", customer.id)


async def _handle_subscription_updated(subscription: dict) -> None:
    stripe_customer_id = subscription.get("customer")
    status = subscription.get("status")

    if status in ("active", "past_due", "canceled", "unpaid"):
        async with async_session() as db:
            result = await db.execute(
                select(Customer).where(Customer.stripe_customer_id == stripe_customer_id)
            )
            customer = result.scalar_one_or_none()
            if customer:
                customer.status = "active" if status == "active" else status
                await db.commit()
                logger.info("Subscription %s for customer %s", status, customer.id)
