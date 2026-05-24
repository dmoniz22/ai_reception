import logging

from starlette.applications import Starlette
from starlette.routing import Route, WebSocketRoute

from config import settings
from routers.telephony import incoming_call, twilio_websocket

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

routes = [
    Route("/incoming-call", incoming_call, methods=["POST"]),
    WebSocketRoute("/twilio", twilio_websocket),
]

app = Starlette(routes=routes)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        log_level="info",
    )
