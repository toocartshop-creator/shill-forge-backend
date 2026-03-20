from fastapi import APIRouter, Depends, HTTPException, Request
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.db.database import get_db
from app.core.security import get_current_user_id
from app.services.user_service import UserService
from app.utils.rate_limit import limiter
from pydantic import BaseModel

router = APIRouter(prefix="/users", tags=["Users"])

class WalletConnectRequest(BaseModel):
    wallet_address: str
    wallet_type: str

@router.get("/me", summary="Get my full profile")
async def get_my_profile(telegram_id: int = Depends(get_current_user_id), db: AsyncIOMotorDatabase = Depends(get_db)):
    user = await UserService(db).get_user(telegram_id)
    if not user: raise HTTPException(404, "User not found")
    return user

@router.get("/me/stats", summary="Get my game stats")
async def get_my_stats(telegram_id: int = Depends(get_current_user_id), db: AsyncIOMotorDatabase = Depends(get_db)):
    svc = UserService(db)
    user = await svc.get_user(telegram_id)
    if not user: raise HTTPException(404, "User not found")
    rank = await svc.get_user_rank(telegram_id)
    return {**user, "rank": rank}

@router.post("/me/wallet", summary="Connect wallet")
async def connect_wallet(body: WalletConnectRequest, telegram_id: int = Depends(get_current_user_id), db: AsyncIOMotorDatabase = Depends(get_db)):
    user = await UserService(db).connect_wallet(telegram_id, body.wallet_address, body.wallet_type)
    return {"wallet_address": user["wallet_address"], "wallet_type": user["wallet_type"]}

@router.get("/leaderboard", summary="Global leaderboard")
@limiter.limit("30/minute")
async def leaderboard(request: Request, limit: int = 50, telegram_id: int = Depends(get_current_user_id), db: AsyncIOMotorDatabase = Depends(get_db)):
    return await UserService(db).get_leaderboard(telegram_id, min(limit, 100))

@router.get("/me/referral", summary="Get referral info")
async def get_referral(telegram_id: int = Depends(get_current_user_id), db: AsyncIOMotorDatabase = Depends(get_db)):
    user = await UserService(db).get_user(telegram_id)
    if not user: raise HTTPException(404, "User not found")
    return {"referral_code": user["referral_code"], "referral_count": user.get("referral_count", 0),
            "referral_points_earned": user.get("referral_points_earned", 0),
            "referral_link": f"https://t.me/ShillForgeBot?start={user['referral_code']}"}
