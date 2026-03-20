from fastapi import APIRouter, Depends, HTTPException, Request, Header
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.db.database import get_db
from app.core.security import get_admin_user, create_admin_token
from app.core.config import settings
from app.utils.rate_limit import limiter
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

router = APIRouter(prefix="/admin", tags=["Admin"])

class AdminLoginRequest(BaseModel):
    secret_key: str
    telegram_id: int

class BanUserRequest(BaseModel):
    telegram_id: int
    reason: Optional[str] = None

class AdjustPointsRequest(BaseModel):
    telegram_id: int
    points: int
    reason: Optional[str] = None

class BroadcastRequest(BaseModel):
    message: str

class CreateTaskRequest(BaseModel):
    task_id: str
    name: str
    description: str
    icon: str
    points: int
    type: str

@router.post("/login", summary="Admin login")
@limiter.limit("5/minute")
async def admin_login(request: Request, body: AdminLoginRequest):
    if body.secret_key != settings.ADMIN_SECRET_KEY:
        raise HTTPException(401, "Invalid admin secret key")
    token = create_admin_token(body.telegram_id)
    return {"access_token": token, "token_type": "bearer"}

@router.get("/stats", summary="Dashboard stats")
async def get_stats(admin_id: int = Depends(get_admin_user), db: AsyncIOMotorDatabase = Depends(get_db)):
    total_users = await db.users.count_documents({})
    active_today = await db.users.count_documents({"last_seen": {"$gte": datetime(datetime.utcnow().year, datetime.utcnow().month, datetime.utcnow().day)}})
    banned = await db.users.count_documents({"is_banned": True})
    pipeline = [{"$group": {"_id": None, "total_pts": {"$sum": "$total_points_earned"}, "total_taps": {"$sum": "$taps_total"}}}]
    agg = await db.users.aggregate(pipeline).to_list(1)
    total_pts = agg[0]["total_pts"] if agg else 0
    total_taps = agg[0]["total_taps"] if agg else 0
    total_squads = await db.squads.count_documents({})
    return {"total_users": total_users, "active_today": active_today, "banned_users": banned,
            "total_points_earned": total_pts, "total_taps": total_taps, "total_squads": total_squads}

@router.get("/users", summary="List users")
async def list_users(page: int = 1, limit: int = 50, search: Optional[str] = None,
                     admin_id: int = Depends(get_admin_user), db: AsyncIOMotorDatabase = Depends(get_db)):
    query = {}
    if search:
        query = {"$or": [{"username": {"$regex": search, "$options": "i"}},
                         {"first_name": {"$regex": search, "$options": "i"}}]}
    skip = (page - 1) * limit
    cursor = db.users.find(query, {"_id": 0}).sort("points", -1).skip(skip).limit(limit)
    users = await cursor.to_list(limit)
    total = await db.users.count_documents(query)
    return {"users": users, "total": total, "page": page, "pages": (total + limit - 1) // limit}

@router.get("/users/{telegram_id}", summary="Get user detail")
async def get_user_detail(telegram_id: int, admin_id: int = Depends(get_admin_user), db: AsyncIOMotorDatabase = Depends(get_db)):
    user = await db.users.find_one({"telegram_id": telegram_id}, {"_id": 0})
    if not user: raise HTTPException(404, "User not found")
    completed_tasks = await db.user_tasks.find({"telegram_id": telegram_id}, {"_id": 0}).to_list(100)
    return {"user": user, "completed_tasks": completed_tasks}

@router.post("/users/ban", summary="Ban/unban user")
async def ban_user(body: BanUserRequest, admin_id: int = Depends(get_admin_user), db: AsyncIOMotorDatabase = Depends(get_db)):
    user = await db.users.find_one({"telegram_id": body.telegram_id})
    if not user: raise HTTPException(404, "User not found")
    new_status = not user.get("is_banned", False)
    await db.users.update_one({"telegram_id": body.telegram_id}, {"$set": {"is_banned": new_status}})
    return {"success": True, "is_banned": new_status, "telegram_id": body.telegram_id}

@router.post("/users/adjust-points", summary="Adjust user points")
async def adjust_points(body: AdjustPointsRequest, admin_id: int = Depends(get_admin_user), db: AsyncIOMotorDatabase = Depends(get_db)):
    user = await db.users.find_one({"telegram_id": body.telegram_id})
    if not user: raise HTTPException(404, "User not found")
    await db.users.update_one({"telegram_id": body.telegram_id},
        {"$inc": {"points": body.points, "total_points_earned": max(body.points, 0)}})
    user_after = await db.users.find_one({"telegram_id": body.telegram_id})
    return {"success": True, "new_points": user_after["points"]}

@router.get("/tasks", summary="List all tasks")
async def list_tasks(admin_id: int = Depends(get_admin_user), db: AsyncIOMotorDatabase = Depends(get_db)):
    tasks = await db.tasks.find({}, {"_id": 0}).to_list(100)
    return {"tasks": tasks}

@router.post("/tasks", summary="Create task")
async def create_task(body: CreateTaskRequest, admin_id: int = Depends(get_admin_user), db: AsyncIOMotorDatabase = Depends(get_db)):
    existing = await db.tasks.find_one({"task_id": body.task_id})
    if existing: raise HTTPException(400, "Task ID already exists")
    task = {**body.model_dump(), "is_active": True, "xp": body.points // 5, "created_at": datetime.utcnow()}
    await db.tasks.insert_one(task)
    return {"success": True, "task_id": body.task_id}

@router.delete("/tasks/{task_id}", summary="Toggle task active/inactive")
async def toggle_task(task_id: str, admin_id: int = Depends(get_admin_user), db: AsyncIOMotorDatabase = Depends(get_db)):
    task = await db.tasks.find_one({"task_id": task_id})
    if not task: raise HTTPException(404, "Task not found")
    new_status = not task.get("is_active", True)
    await db.tasks.update_one({"task_id": task_id}, {"$set": {"is_active": new_status}})
    return {"success": True, "is_active": new_status}

@router.get("/leaderboard", summary="Full leaderboard for admin")
async def admin_leaderboard(limit: int = 100, admin_id: int = Depends(get_admin_user), db: AsyncIOMotorDatabase = Depends(get_db)):
    cursor = db.users.find({}, {"telegram_id": 1, "username": 1, "first_name": 1, "points": 1,
                                 "taps_total": 1, "level": 1, "referral_count": 1, "is_banned": 1, "_id": 0}).sort("points", -1).limit(limit)
    users, rank = [], 1
    async for u in cursor:
        users.append({**u, "rank": rank})
        rank += 1
    return {"users": users}
