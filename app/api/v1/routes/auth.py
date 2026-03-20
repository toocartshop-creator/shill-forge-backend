from fastapi import APIRouter, Depends, HTTPException, Request
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.db.database import get_db
from app.services.user_service import UserService
from app.utils.rate_limit import limiter
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/auth", tags=["Auth"])

class TelegramAuthRequest(BaseModel):
    init_data: str
    referral_code: Optional[str] = None

@router.post("/telegram", summary="Authenticate via Telegram Mini App")
@limiter.limit("10/minute")
async def telegram_auth(request: Request, body: TelegramAuthRequest, db: AsyncIOMotorDatabase = Depends(get_db)):
    svc = UserService(db)
    return await svc.authenticate(body.init_data, body.referral_code)
