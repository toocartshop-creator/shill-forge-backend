import hashlib, hmac, json, time
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.config import settings

bearer_scheme = HTTPBearer(auto_error=False)

def create_access_token(telegram_id: int, username: str = "") -> str:
    payload = {
        "sub": str(telegram_id), "username": username,
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(minutes=settings.JWT_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

async def get_current_user_id(credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme)) -> int:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authorization header missing")
    payload = decode_access_token(credentials.credentials)
    try:
        return int(payload["sub"])
    except (KeyError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Malformed token payload")

async def get_admin_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme)) -> int:
    if not credentials:
        raise HTTPException(status_code=401, detail="Admin auth required")
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.ADMIN_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        if not payload.get("is_admin"):
            raise HTTPException(status_code=403, detail="Not an admin")
        return int(payload["sub"])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid admin token")

def create_admin_token(telegram_id: int) -> str:
    payload = {
        "sub": str(telegram_id), "is_admin": True,
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(hours=12),
    }
    return jwt.encode(payload, settings.ADMIN_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

def validate_telegram_init_data(init_data: str) -> dict:
    params = {}
    for part in init_data.split("&"):
        if "=" in part:
            k, v = part.split("=", 1)
            params[k] = v
    received_hash = params.pop("hash", None)
    if not received_hash:
        raise HTTPException(status_code=400, detail="Missing hash in init_data")
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
    secret_key = hmac.new(b"WebAppData", settings.TELEGRAM_BOT_TOKEN.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(computed_hash, received_hash):
        raise HTTPException(status_code=401, detail="Invalid Telegram signature")
    auth_date = int(params.get("auth_date", 0))
    if time.time() - auth_date > 86400:
        raise HTTPException(status_code=401, detail="Telegram init_data expired")
    try:
        return json.loads(params.get("user", "{}"))
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Malformed user object")
