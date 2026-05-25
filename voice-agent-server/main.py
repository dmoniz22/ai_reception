import logging

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.routing import Route, WebSocketRoute

from config import settings
from middleware.rate_limit import RateLimitMiddleware
from middleware.logging import setup_logging
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
from routers.admin import availability, book, oauth_authorize, oauth_callback

setup_logging("INFO")

logger = logging.getLogger(__name__)

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
    Route("/api/scheduling/{customer_id:path}/availability", availability, methods=["POST"]),
    Route("/api/scheduling/{customer_id:path}/book", book, methods=["POST"]),
    Route("/api/scheduling/oauth/authorize", oauth_authorize, methods=["GET"]),
    Route("/api/scheduling/oauth/callback", oauth_callback, methods=["GET"]),
]

middleware = [
    Middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3002", f"https://{settings.domain}"],
        allow_methods=["*"],
        allow_headers=["*"],
    ),
    Middleware(RateLimitMiddleware),
]

app = Starlette(routes=routes, middleware=middleware)


@app.on_event("startup")
async def startup() -> None:
    from models.database import init_db
    await init_db()
    logger.info("Database initialized")
    logger.info("Server ready on %s:%s", settings.host, settings.port)


@app.on_event("shutdown")
async def shutdown() -> None:
    logger.info("Server shutting down gracefully")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        log_config=None,
        log_level="info",
    )
