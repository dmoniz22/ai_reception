import logging

from starlette.applications import Starlette
from starlette.routing import Route, WebSocketRoute

from config import settings
from routers.telephony import incoming_call, twilio_websocket
from routers.customers import (
    list_customers,
    create_customer,
    get_customer,
    update_customer,
    delete_customer,
    get_customer_calls,
)
from routers.health import health_check

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

routes = [
    Route("/health", health_check, methods=["GET"]),
    Route("/incoming-call/{customer_id:path}", incoming_call, methods=["POST"]),
    Route("/incoming-call", incoming_call, methods=["POST"]),
    WebSocketRoute("/twilio", twilio_websocket),
    WebSocketRoute("/twilio/{customer_id:path}", twilio_websocket),
    Route("/api/customers", list_customers, methods=["GET"]),
    Route("/api/customers", create_customer, methods=["POST"]),
    Route("/api/customers/{customer_id:uuid}", get_customer, methods=["GET"]),
    Route("/api/customers/{customer_id:uuid}", update_customer, methods=["PUT"]),
    Route("/api/customers/{customer_id:uuid}", delete_customer, methods=["DELETE"]),
    Route("/api/customers/{customer_id:uuid}/calls", get_customer_calls, methods=["GET"]),
]

app = Starlette(routes=routes)


@app.on_event("startup")
async def startup() -> None:
    from models.database import init_db
    await init_db()
    logging.getLogger(__name__).info("Database initialized")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        log_level="info",
    )
