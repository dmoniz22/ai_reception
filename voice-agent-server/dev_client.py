import asyncio
import audioop
import base64
import json
import sys
import wave

import numpy as np
import websockets

try:
    import pyaudio
except ImportError:
    print("pyaudio not installed. Run: pip install pyaudio")
    sys.exit(1)

SERVER_URL = "ws://localhost:8000/twilio"

CHUNK = 320
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 8000

audio = pyaudio.PyAudio()


async def dev_client() -> None:
    print(f"Connecting to {SERVER_URL}...")
    print("Speak into your microphone. Press Ctrl+C to exit.")
    print()

    input_stream = audio.open(
        format=FORMAT,
        channels=CHANNELS,
        rate=RATE,
        input=True,
        frames_per_buffer=CHUNK,
    )

    output_stream = audio.open(
        format=FORMAT,
        channels=CHANNELS,
        rate=RATE,
        output=True,
    )

    async with websockets.connect(SERVER_URL) as ws:
        stream_sid = f"dev_{id(ws)}"
        call_sid = f"dev_{id(ws)}"

        async def send_audio() -> None:
            loop = asyncio.get_event_loop()
            seq = 0
            while True:
                data = await loop.run_in_executor(
                    None, input_stream.read, CHUNK, False
                )

                mulaw_bytes = audioop.lin2ulaw(data, 2)
                payload_b64 = base64.b64encode(mulaw_bytes).decode("ascii")

                msg = {
                    "event": "media",
                    "streamSid": stream_sid,
                    "media": {
                        "track": "inbound",
                        "chunk": str(seq),
                        "payload": payload_b64,
                    },
                }
                seq += 1
                await ws.send(json.dumps(msg))
                await asyncio.sleep(0.02)

        async def recv_audio() -> None:
            loop = asyncio.get_event_loop()
            while True:
                msg = await ws.recv()
                if isinstance(msg, str):
                    try:
                        data = json.loads(msg)
                    except json.JSONDecodeError:
                        continue

                    event = data.get("event")
                    if event == "media":
                        media = data.get("media", {})
                        if media.get("track") == "outbound":
                            payload_b64 = media.get("payload", "")
                            if payload_b64:
                                mulaw_bytes = base64.b64decode(payload_b64)
                                linear16 = audioop.ulaw2lin(mulaw_bytes, 2)
                                await loop.run_in_executor(
                                    None, output_stream.write, linear16
                                )

        try:
            await asyncio.gather(send_audio(), recv_audio())
        except asyncio.CancelledError:
            pass
        finally:
            input_stream.stop_stream()
            input_stream.close()
            output_stream.stop_stream()
            output_stream.close()


if __name__ == "__main__":
    try:
        asyncio.run(dev_client())
    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        audio.terminate()
