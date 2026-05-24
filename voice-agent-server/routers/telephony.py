import json
import logging

from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.websockets import WebSocket, WebSocketDisconnect

from session import VoiceAgentSession

logger = logging.getLogger(__name__)

TWIML_RESPONSE = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="wss://{host}/twilio" />
    </Connect>
</Response>"""


async def incoming_call(request: Request) -> PlainTextResponse:
    host = request.headers.get("host", request.url.hostname or "localhost")
    twiml = TWIML_RESPONSE.format(host=host)
    return PlainTextResponse(twiml, media_type="application/xml")


async def twilio_websocket(ws: WebSocket) -> None:
    await ws.accept()
    logger.info("Twilio WebSocket connected")

    stream_sid: str | None = None
    call_sid: str | None = None

    try:
        async for message in ws.iter_text():
            data = json.loads(message)
            event = data.get("event")

            if event == "connected":
                logger.info("Twilio stream connected")

            elif event == "start":
                start_data = data.get("start", {})
                stream_sid = start_data.get("streamSid", data.get("streamSid", ""))
                call_sid = start_data.get("callSid", data.get("callSid", ""))

                logger.info(
                    "Call starting: stream_sid=%s call_sid=%s",
                    stream_sid,
                    call_sid,
                )

                session = VoiceAgentSession(
                    twilio_ws=ws,
                    stream_sid=stream_sid,
                    call_sid=call_sid,
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
