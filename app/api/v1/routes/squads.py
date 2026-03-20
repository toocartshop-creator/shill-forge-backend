from fastapi import APIRouter, Depends, HTTPException, Request
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.db.database import get_db
from app.core.security import get_current_user_id
from app.services.squad_service import SquadService
from app.utils.rate_limit import limiter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/squads", tags=["Squads"])

class CreateSquadRequest(BaseModel):
    name: str = Field(..., min_length=3, max_length=30)
    emoji: str = "⚔️"

class JoinSquadRequest(BaseModel):
    invite_code: str

@router.post("/create", summary="Create a new squad")
@limiter.limit("3/minute")
async def create_squad(request: Request, body: CreateSquadRequest,
                       telegram_id: int = Depends(get_current_user_id), db: AsyncIOMotorDatabase = Depends(get_db)):
    result = await SquadService(db).create_squad(telegram_id, body.name, body.emoji)
    if not result["success"]: raise HTTPException(400, result["error"])
    return result

@router.post("/join", summary="Join squad via invite code")
@limiter.limit("5/minute")
async def join_squad(request: Request, body: JoinSquadRequest,
                     telegram_id: int = Depends(get_current_user_id), db: AsyncIOMotorDatabase = Depends(get_db)):
    result = await SquadService(db).join_squad(telegram_id, body.invite_code)
    if not result["success"]: raise HTTPException(400, result["error"])
    return result

@router.post("/leave", summary="Leave current squad")
async def leave_squad(telegram_id: int = Depends(get_current_user_id), db: AsyncIOMotorDatabase = Depends(get_db)):
    result = await SquadService(db).leave_squad(telegram_id)
    if not result["success"]: raise HTTPException(400, result["error"])
    return result

@router.get("/mine", summary="Get my squad details")
async def get_my_squad(telegram_id: int = Depends(get_current_user_id), db: AsyncIOMotorDatabase = Depends(get_db)):
    user = await db.users.find_one({"telegram_id": telegram_id})
    if not user or not user.get("squad_id"): raise HTTPException(404, "Not in a squad")
    return await SquadService(db).get_squad(user["squad_id"], telegram_id)

@router.get("/leaderboard", summary="Squad leaderboard")
@limiter.limit("30/minute")
async def squad_leaderboard(request: Request, telegram_id: int = Depends(get_current_user_id), db: AsyncIOMotorDatabase = Depends(get_db)):
    return await SquadService(db).get_leaderboard()
