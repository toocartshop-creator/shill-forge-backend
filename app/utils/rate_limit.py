from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi import Request
from fastapi.responses import JSONResponse

limiter = Limiter(key_func=get_remote_address)

async def rate_limit_handler(request: Request, exc):
    return JSONResponse(status_code=429, content={"detail": "Too many requests. Please slow down."})
