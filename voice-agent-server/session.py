import asyncio
import audioop
import json
import logging
import base64
import uuid
from datetime import datetime, timezone

import httpx
import numpy as np
import websockets
from sqlalchemy import select
from starlette.websockets import WebSocket, WebSocketDisconnect

from config import settings
from agent_config import build_settings
from models.database import async_session
from models.customer import Customer
from models.call_log import CallLog, Message
from services.twilio_client import send_sms

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
        caller_number: str | None = None,
    ):
        self.twilio_ws = twilio_ws
        self.stream_sid = stream_sid
        self.call_sid = call_sid
        self.customer_id = customer_id
        self.caller_number = caller_number

        self.dg_ws: websockets.WebSocketClientProtocol | None = None
        self.running = False

        self._customer: Customer | None = None
        self._started_at: datetime | None = None
        self._call_log_id: uuid.UUID | None = None
        self._transcript_lines: list[str] = []

    async def run(self) -> None:
        try:
            if self.customer_id:
                await self._load_customer()

            await self._create_call_log()
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
            await self._finalize_call()
            await self._cleanup()

    async def _load_customer(self) -> None:
        async with async_session() as db:
            result = await db.execute(
                select(Customer).where(Customer.id == uuid.UUID(self.customer_id))
            )
            self._customer = result.scalar_one_or_none()
            if self._customer:
                logger.info("Loaded customer %s (%s)", self._customer.business_name, self._customer.id)
            else:
                logger.warning("Customer %s not found, using defaults", self.customer_id)

    async def _create_call_log(self) -> None:
        self._started_at = datetime.now(timezone.utc)
        async with async_session() as db:
            log = CallLog(
                customer_id=uuid.UUID(self.customer_id) if self.customer_id else uuid.uuid4(),
                caller_number=self.caller_number or "unknown",
                call_sid=self.call_sid,
                started_at=self._started_at,
            )
            db.add(log)
            await db.commit()
            self._call_log_id = log.id
            logger.info("Created call log %s", self._call_log_id)

    async def _connect_deepgram(self) -> None:
        headers = {"Authorization": f"Token {settings.deepgram_api_key}"}
        self.dg_ws = await websockets.connect(DG_WS_URL, additional_headers=headers)
        logger.info("Connected to Deepgram for call %s", self.call_sid)

        if self._customer:
            settings_msg = build_settings(
                business_name=self._customer.business_name,
                greeting=self._customer.greeting,
                business_hours=str(self._customer.business_hours or "Monday-Friday 9am-5pm"),
                faqs=str(self._customer.faqs or "No FAQs configured yet."),
                customer_id=str(self._customer.id),
            )
            if self._customer.deepgram_agent_id:
                settings_msg["agent"]["agent_id"] = self._customer.deepgram_agent_id
        else:
            settings_msg = build_settings()

        await self.dg_ws.send(json.dumps(settings_msg))
        logger.info("Sent agent settings to Deepgram")

    async def _twilio_to_deepgram(self) -> None:
        try:
            while self.running:
                try:
                    msg = await asyncio.wait_for(self.twilio_ws.receive_text(), timeout=1.0)
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
                    if media.get("track") == "inbound":
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
                        "media": {"track": "outbound", "payload": payload_b64},
                    })
                    if self.running:
                        await self.twilio_ws.send_text(response)

                elif isinstance(msg, str):
                    try:
                        event = json.loads(msg)
                    except json.JSONDecodeError:
                        continue

                    event_type = event.get("type", "")

                    if event_type == "AgentV1ConversationText":
                        text = event.get("payload", {}).get("text", "")
                        role = event.get("payload", {}).get("role", "unknown")
                        self._transcript_lines.append(f"{role}: {text}")
                        logger.debug("Transcript: [%s] %s", role, text)

                    elif event_type == "AgentV1FunctionCallRequest":
                        await self._handle_function_call(event)

                    elif event_type == "AgentV1UserStartedSpeaking":
                        logger.debug("User started speaking")

                    elif event_type == "AgentV1AgentThinking":
                        logger.debug("Agent thinking")

                    elif event_type == "AgentV1Error":
                        logger.error("Deepgram error: %s", event)

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
            await self._save_message(func_args)
            response_msg = json.dumps({
                "status": "message_taken",
                "message": "Your message has been saved and the owner will be notified.",
            })
        elif func_name == "transfer_to_owner":
            await self._update_call_outcome("transferred")
            response_msg = json.dumps({
                "status": "transferring",
                "message": "Transferring to the owner now.",
            })
        else:
            response_msg = json.dumps({"status": "unknown_function"})

        response = {
            "type": "AgentV1SendFunctionCallResponse",
            "payload": {"call_id": call_id, "response": response_msg},
        }

        if self.dg_ws and self.running:
            await self.dg_ws.send(json.dumps(response))

    async def _save_message(self, args: dict) -> None:
        async with async_session() as db:
            message = Message(
                call_log_id=self._call_log_id,
                customer_id=uuid.UUID(self.customer_id) if self.customer_id else uuid.uuid4(),
                caller_name=args.get("caller_name"),
                caller_number=args.get("callback_number", self.caller_number),
                message_text=args.get("message"),
                urgency=args.get("urgency", "normal"),
            )
            db.add(message)
            await db.commit()
            logger.info("Saved message for customer %s", self.customer_id)

    async def _update_call_outcome(self, outcome: str) -> None:
        if not self._call_log_id:
            return
        async with async_session() as db:
            log = await db.get(CallLog, self._call_log_id)
            if log:
                log.outcome = outcome
                if outcome == "transferred":
                    log.transferred_to_owner = True
                await db.commit()

    async def _finalize_call(self) -> None:
        ended_at = datetime.now(timezone.utc)
        duration = None
        if self._started_at:
            duration = int((ended_at - self._started_at).total_seconds())

        transcript = "\n".join(self._transcript_lines) if self._transcript_lines else ""
        summary = await self._generate_summary(transcript) if transcript else None

        async with async_session() as db:
            log = await db.get(CallLog, self._call_log_id) if self._call_log_id else None
            if log:
                log.ended_at = ended_at
                log.duration_seconds = duration
                if summary:
                    log.summary = summary
                if not log.outcome:
                    log.outcome = "completed"
                await db.commit()
                logger.info("Finalized call log %s (duration: %ss, summary: %s)",
                           self._call_log_id, duration, bool(summary))

        if summary and self._customer and self._customer.phone:
            sms_body = (
                f"AI Receptionist — Call Summary\n"
                f"From: {self.caller_number or 'Unknown'}\n"
                f"Duration: {duration}s\n\n"
                f"{summary}"
            )
            send_sms(self._customer.phone, sms_body)

    async def _generate_summary(self, transcript: str) -> str | None:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{settings.ollama_cloud_endpoint}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {settings.ollama_cloud_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "deepseek-v4-flash",
                        "messages": [
                            {
                                "role": "system",
                                "content": (
                                    "Summarize this phone call transcript in 1-2 sentences. "
                                    "Mention: who called, what they wanted, what was resolved or scheduled."
                                ),
                            },
                            {"role": "user", "content": transcript},
                        ],
                        "temperature": 0.3,
                        "max_tokens": 150,
                    },
                )
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            logger.error("Failed to generate summary: %s", e)
            return None

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
