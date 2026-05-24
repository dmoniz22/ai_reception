from starlette.requests import Request
from starlette.responses import JSONResponse


async def health_check(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})
