import json
import logging
import uuid

from sqlalchemy import select
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.websockets import WebSocket, WebSocketDisconnect

from models.database import async_session
from models.customer import Customer
from session import VoiceAgentSession

logger = logging.getLogger(__name__)

TWIML_RESPONSE = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="wss://{host}/twilio/{customer_id}" />
    </Connect>
</Response>"""

TWIML_RESPONSE_NO_CUSTOMER = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="wss://{host}/twilio" />
    </Connect>
</Response>"""


async def incoming_call(request: Request) -> PlainTextResponse:
    host = request.headers.get("host", request.url.hostname or "localhost")
    customer_id = request.path_params.get("customer_id", "")

    if customer_id:
        twiml = TWIML_RESPONSE.format(host=host, customer_id=customer_id)
    else:
        twiml = TWIML_RESPONSE_NO_CUSTOMER.format(host=host)

    return PlainTextResponse(twiml, media_type="application/xml")


async def twilio_websocket(ws: WebSocket) -> None:
    await ws.accept()
    logger.info("Twilio WebSocket connected")

    stream_sid: str | None = None
    call_sid: str | None = None
    customer_id: str | None = None
    caller_number: str | None = None

    try:
        async for message in ws.iter_text():
            try:
                data = json.loads(message)
            except json.JSONDecodeError:
                continue

            event = data.get("event")

            if event == "connected":
                logger.info("Twilio stream connected")

            elif event == "start":
                start_data = data.get("start", {})
                stream_sid = start_data.get("streamSid", data.get("streamSid", ""))
                call_sid = start_data.get("callSid", data.get("callSid", ""))

                custom_params = start_data.get("customParameters", {})
                customer_id = custom_params.get(
                    "customer_id",
                    ws.path_params.get("customer_id", ""),
                )
                caller_number = start_data.get("from", data.get("from", ""))

                logger.info(
                    "Call starting: stream_sid=%s call_sid=%s customer_id=%s caller=%s",
                    stream_sid, call_sid, customer_id, caller_number,
                )

                session = VoiceAgentSession(
                    twilio_ws=ws,
                    stream_sid=stream_sid,
                    call_sid=call_sid,
                    customer_id=customer_id or None,
                    caller_number=caller_number or None,
                )
                await session.run()
                break

            elif event == "stop":
                logger.info("Twilio stream stopped before start")
                break

    except WebSocketDisconnect:
        logger.info("Twilio WebSocket disconnected")
    except Exception:
        logger.exception("Error in Twilio WebSocket handler")
