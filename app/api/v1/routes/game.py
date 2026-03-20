from fastapi import APIRouter, Depends, HTTPException, Request
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.db.database import get_db
from app.core.security import get_current_user_id
from app.services.game_service import GameService
from app.utils.rate_limit import limiter
from pydantic import BaseModel, Field, validator
from typing import Optional

router = APIRouter(prefix="/game", tags=["Game"])

class TapRequest(BaseModel):
    taps: int = Field(..., ge=1, le=100)
    combo_multiplier: int = Field(1, ge=1, le=10)
    energy_used: int = Field(..., ge=1, le=100)

class ClaimMissionRequest(BaseModel):
    mission_id: str

class BoostPurchaseRequest(BaseModel):
    boost_id: str

class UpgradePurchaseRequest(BaseModel):
    upgrade_id: str

class TaskCompleteRequest(BaseModel):
    task_id: str
    proof: Optional[str] = None

class ThemePurchaseRequest(BaseModel):
    theme_id: str

class ThemeEquipRequest(BaseModel):
    theme_id: str

@router.post("/tap", summary="Submit tap batch")
@limiter.limit("60/minute")
async def tap(request: Request, body: TapRequest,
              telegram_id: int = Depends(get_current_user_id), db: AsyncIOMotorDatabase = Depends(get_db)):
    result = await GameService(db).process_tap(telegram_id, body.taps, body.combo_multiplier, body.energy_used)
    if "error" in result: raise HTTPException(400, result["error"])
    return result

@router.post("/checkin", summary="Daily check-in")
@limiter.limit("5/minute")
async def daily_checkin(request: Request, telegram_id: int = Depends(get_current_user_id), db: AsyncIOMotorDatabase = Depends(get_db)):
    return await GameService(db).daily_checkin(telegram_id)

@router.get("/missions", summary="Get today's missions")
async def get_missions(telegram_id: int = Depends(get_current_user_id), db: AsyncIOMotorDatabase = Depends(get_db)):
    return await GameService(db).get_missions(telegram_id)

@router.post("/missions/claim", summary="Claim completed mission")
@limiter.limit("10/minute")
async def claim_mission(request: Request, body: ClaimMissionRequest,
                        telegram_id: int = Depends(get_current_user_id), db: AsyncIOMotorDatabase = Depends(get_db)):
    result = await GameService(db).claim_mission(telegram_id, body.mission_id)
    if not result["success"]: raise HTTPException(400, result.get("error", "Cannot claim"))
    return result

@router.post("/spin", summary="Daily spin wheel")
@limiter.limit("3/minute")
async def spin_wheel(request: Request, telegram_id: int = Depends(get_current_user_id), db: AsyncIOMotorDatabase = Depends(get_db)):
    return await GameService(db).spin_wheel(telegram_id)

@router.post("/boost/purchase", summary="Purchase a boost")
@limiter.limit("10/minute")
async def purchase_boost(request: Request, body: BoostPurchaseRequest,
                         telegram_id: int = Depends(get_current_user_id), db: AsyncIOMotorDatabase = Depends(get_db)):
    result = await GameService(db).purchase_boost(telegram_id, body.boost_id)
    if not result["success"]: raise HTTPException(400, result.get("error", "Purchase failed"))
    return result

@router.post("/upgrade/purchase", summary="Purchase tap upgrade")
@limiter.limit("10/minute")
async def purchase_upgrade(request: Request, body: UpgradePurchaseRequest,
                           telegram_id: int = Depends(get_current_user_id), db: AsyncIOMotorDatabase = Depends(get_db)):
    result = await GameService(db).purchase_upgrade(telegram_id, body.upgrade_id)
    if not result["success"]: raise HTTPException(400, result.get("error", "Upgrade failed"))
    return result

@router.get("/tasks", summary="Get all tasks with completion status")
async def get_tasks(telegram_id: int = Depends(get_current_user_id), db: AsyncIOMotorDatabase = Depends(get_db)):
    return await GameService(db).get_tasks(telegram_id)

@router.post("/tasks/complete", summary="Mark task complete")
@limiter.limit("20/minute")
async def complete_task(request: Request, body: TaskCompleteRequest,
                        telegram_id: int = Depends(get_current_user_id), db: AsyncIOMotorDatabase = Depends(get_db)):
    result = await GameService(db).complete_task(telegram_id, body.task_id)
    if not result.get("success") and not result.get("already_completed"):
        raise HTTPException(400, result.get("error", "Task failed"))
    return result

@router.post("/theme/purchase", summary="Purchase a theme")
@limiter.limit("10/minute")
async def purchase_theme(request: Request, body: ThemePurchaseRequest,
                         telegram_id: int = Depends(get_current_user_id), db: AsyncIOMotorDatabase = Depends(get_db)):
    result = await GameService(db).purchase_theme(telegram_id, body.theme_id)
    if not result.get("success"): raise HTTPException(400, result.get("error", "Purchase failed"))
    return result

@router.post("/theme/equip", summary="Equip an owned theme")
async def equip_theme(body: ThemeEquipRequest,
                      telegram_id: int = Depends(get_current_user_id), db: AsyncIOMotorDatabase = Depends(get_db)):
    result = await GameService(db).equip_theme(telegram_id, body.theme_id)
    if not result.get("success"): raise HTTPException(400, result.get("error", "Equip failed"))
    return result
