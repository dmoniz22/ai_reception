import asyncio
import audioop
import json
import logging
import base64

import numpy as np
import websockets
from starlette.websockets import WebSocket, WebSocketDisconnect

from config import settings
from agent_config import build_settings

logger = logging.getLogger(__name__)

DG_WS_URL = "wss://agent.deepgram.com/v1/agent/converse"
TWILIO_SAMPLE_RATE = 8000
DEEPGRAM_SAMPLE_RATE = 24000


class VoiceAgentSession:
    def __init__(
        self,
        twilio_ws: WebSocket,
        stream_sid: str,
        call_sid: str,
        customer_id: str | None = None,
        agent_id: str | None = None,
        business_name: str = "AI Receptionist",
        greeting: str | None = None,
    ):
        self.twilio_ws = twilio_ws
        self.stream_sid = stream_sid
        self.call_sid = call_sid
        self.customer_id = customer_id
        self.agent_id = agent_id
        self.business_name = business_name
        self.greeting = greeting

        self.dg_ws: websockets.WebSocketClientProtocol | None = None
        self.running = False

    async def run(self) -> None:
        try:
            await self._connect_deepgram()

            self.running = True
            t1 = asyncio.create_task(self._twilio_to_deepgram())
            t2 = asyncio.create_task(self._deepgram_to_twilio())
            t3 = asyncio.create_task(self._keepalive())

            done, pending = await asyncio.wait(
                [t1, t2, t3],
                return_when=asyncio.FIRST_COMPLETED,
            )

            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        except Exception:
            logger.exception("VoiceAgentSession failed for call %s", self.call_sid)
        finally:
            self.running = False
            await self._cleanup()

    async def _connect_deepgram(self) -> None:
        headers = {"Authorization": f"Token {settings.deepgram_api_key}"}

        self.dg_ws = await websockets.connect(DG_WS_URL, additional_headers=headers)
        logger.info("Connected to Deepgram Voice Agent for call %s", self.call_sid)

        settings_msg = build_settings(
            business_name=self.business_name,
            greeting=self.greeting,
        )

        if self.agent_id:
            settings_msg["agent"]["agent_id"] = self.agent_id

        await self.dg_ws.send(json.dumps(settings_msg))
        logger.info("Sent agent settings to Deepgram")

    async def _twilio_to_deepgram(self) -> None:
        try:
            while self.running:
                try:
                    msg = await asyncio.wait_for(
                        self.twilio_ws.receive_text(), timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue
                except WebSocketDisconnect:
                    logger.info("Twilio disconnected for call %s", self.call_sid)
                    self.running = False
                    break

                try:
                    data = json.loads(msg)
                except json.JSONDecodeError:
                    continue

                event = data.get("event")

                if event == "media":
                    media = data.get("media", {})
                    track = media.get("track")

                    if track == "inbound":
                        payload_b64 = media.get("payload", "")
                        if not payload_b64:
                            continue

                        mulaw_bytes = base64.b64decode(payload_b64)
                        linear16 = audioop.ulaw2lin(mulaw_bytes, 2)
                        resampled = _resample_8000_to_24000(linear16)

                        if self.dg_ws and self.running:
                            await self.dg_ws.send(resampled)

                elif event == "stop":
                    logger.info("Call ended: %s", self.call_sid)
                    self.running = False
                    break

        except Exception:
            if self.running:
                logger.exception("Error in Twilio-to-Deepgram bridge")

    async def _deepgram_to_twilio(self) -> None:
        try:
            while self.running and self.dg_ws:
                try:
                    msg = await asyncio.wait_for(self.dg_ws.recv(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue
                except websockets.exceptions.ConnectionClosed:
                    logger.info("Deepgram connection closed for call %s", self.call_sid)
                    self.running = False
                    break

                if isinstance(msg, bytes):
                    resampled = _resample_24000_to_8000(msg)
                    mulaw_bytes = audioop.lin2ulaw(resampled, 2)
                    payload_b64 = base64.b64encode(mulaw_bytes).decode("ascii")

                    response = json.dumps({
                        "event": "media",
                        "streamSid": self.stream_sid,
                        "media": {
                            "track": "outbound",
                            "payload": payload_b64,
                        },
                    })

                    if self.running:
                        await self.twilio_ws.send_text(response)

                elif isinstance(msg, str):
                    try:
                        event = json.loads(msg)
                    except json.JSONDecodeError:
                        continue

                    event_type = event.get("type", "")
                    logger.debug("Deepgram event: %s", event_type)

                    if event_type == "AgentV1FunctionCallRequest":
                        await self._handle_function_call(event)
                    elif event_type == "AgentV1Error":
                        logger.error("Deepgram error: %s", event)
                    elif event_type == "AgentV1ConversationText":
                        logger.info("Conversation: %s", event.get("payload", {}).get("text", ""))

        except Exception:
            if self.running:
                logger.exception("Error in Deepgram-to-Twilio bridge")

    async def _keepalive(self) -> None:
        while self.running and self.dg_ws:
            try:
                await self.dg_ws.send(json.dumps({"type": "KeepAlive"}))
                await asyncio.sleep(5)
            except Exception:
                break

    async def _handle_function_call(self, event: dict) -> None:
        payload = event.get("payload", {})
        func_name = payload.get("function_name", "")
        func_args = payload.get("arguments", {})
        call_id = payload.get("call_id", "")

        logger.info("Function call: %s args=%s", func_name, func_args)

        if func_name == "take_message":
            response_msg = json.dumps({
                "status": "message_taken",
                "message": "Your message has been saved and the owner will be notified.",
            })
        elif func_name == "transfer_to_owner":
            response_msg = json.dumps({
                "status": "transferring",
                "message": "Transferring to the owner now.",
            })
        elif func_name in ("check_availability", "book_appointment"):
            response_msg = json.dumps({
                "status": "unavailable",
                "message": "Scheduling is not yet configured. Please leave a message and we'll call you back.",
            })
        else:
            response_msg = json.dumps({"status": "unknown_function"})

        response = {
            "type": "AgentV1SendFunctionCallResponse",
            "payload": {
                "call_id": call_id,
                "response": response_msg,
            },
        }

        if self.dg_ws and self.running:
            await self.dg_ws.send(json.dumps(response))

    async def _cleanup(self) -> None:
        if self.dg_ws:
            try:
                await self.dg_ws.close()
            except Exception:
                pass
            self.dg_ws = None
        logger.info("Session cleaned up for call %s", self.call_sid)


def _resample_8000_to_24000(linear16: bytes) -> bytes:
    if len(linear16) < 2:
        return b""
    arr = np.frombuffer(linear16, dtype=np.int16).astype(np.float32)
    orig_len = len(arr)
    x_old = np.arange(orig_len)
    x_new = np.linspace(0, orig_len - 1, orig_len * 3)
    resampled = np.interp(x_new, x_old, arr).astype(np.int16)
    return resampled.tobytes()


def _resample_24000_to_8000(linear16: bytes) -> bytes:
    if len(linear16) < 6:
        return b""
    arr = np.frombuffer(linear16, dtype=np.int16).astype(np.float32)
    orig_len = len(arr)
    target_len = orig_len // 3
    if target_len < 2:
        return b""
    x_old = np.arange(orig_len)
    x_new = np.linspace(0, orig_len - 1, target_len)
    resampled = np.interp(x_new, x_old, arr).astype(np.int16)
    return resampled.tobytes()
