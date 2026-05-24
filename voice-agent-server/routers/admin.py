import json
import logging

from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse

from config import settings
from services.scheduling import (
    check_availability,
    book_appointment,
    get_oauth_url,
    handle_oauth_callback,
)
from services.billing import check_subscription_active

logger = logging.getLogger(__name__)


def _verify_internal(request: Request) -> bool:
    auth = request.headers.get("Authorization", "")
    expected = f"Bearer {settings.internal_api_key}"
    return auth == expected and bool(settings.internal_api_key)


async def availability(request: Request) -> JSONResponse:
    if not _verify_internal(request):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    customer_id = request.path_params.get("customer_id", "")
    body = await request.json()
    date = body.get("date", "")

    if not customer_id or not date:
        return JSONResponse({"error": "customer_id and date required"}, status_code=400)

    active = await check_subscription_active(customer_id)
    if not active:
        return JSONResponse({"available": False, "reason": "Subscription inactive"})

    result = await check_availability(customer_id, date)
    return JSONResponse(result)


async def book(request: Request) -> JSONResponse:
    if not _verify_internal(request):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    customer_id = request.path_params.get("customer_id", "")
    body = await request.json()
    date = body.get("date", "")
    time = body.get("time", "")
    name = body.get("name", "")
    phone = body.get("phone", "")
    service = body.get("service", "Appointment")

    if not all([customer_id, date, time, name]):
        return JSONResponse({"error": "Missing required fields"}, status_code=400)

    active = await check_subscription_active(customer_id)
    if not active:
        return JSONResponse({"booked": False, "reason": "Subscription inactive"})

    result = await book_appointment(customer_id, date, time, name, phone, service)
    return JSONResponse(result)


async def oauth_authorize(request: Request) -> RedirectResponse:
    customer_id = request.query_params.get("customer_id", "")
    if not customer_id:
        return JSONResponse({"error": "customer_id required"}, status_code=400)

    url = await get_oauth_url(customer_id)
    return RedirectResponse(url, status_code=302)


async def oauth_callback(request: Request) -> JSONResponse:
    code = request.query_params.get("code", "")
    state = request.query_params.get("state", "")

    if not code or not state:
        return JSONResponse({"error": "Missing code or state"}, status_code=400)

    try:
        await handle_oauth_callback(code, state)
        return JSONResponse({"status": "connected"})
    except Exception as e:
        logger.exception("OAuth callback failed")
        return JSONResponse({"error": str(e)}, status_code=500)
