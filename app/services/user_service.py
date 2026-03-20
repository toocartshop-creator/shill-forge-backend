from datetime import datetime
from typing import Optional, Dict
import logging, uuid
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.core.config import settings
from app.core.security import create_access_token, validate_telegram_init_data
from app.models.user import UserModel, generate_referral_code

logger = logging.getLogger(__name__)

class UserService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.col = db.users

    async def authenticate(self, init_data: str, referral_code: Optional[str] = None) -> Dict:
        tg_user = validate_telegram_init_data(init_data)
        telegram_id = tg_user["id"]
        existing = await self.col.find_one({"telegram_id": telegram_id})
        if existing:
            await self.col.update_one({"telegram_id": telegram_id},
                {"$set": {"last_seen": datetime.utcnow(),
                          "username": tg_user.get("username"),
                          "first_name": tg_user.get("first_name", ""),
                          "photo_url": tg_user.get("photo_url")}})
        else:
            new_user = UserModel(
                telegram_id=telegram_id, username=tg_user.get("username"),
                first_name=tg_user.get("first_name", ""), last_name=tg_user.get("last_name", ""),
                photo_url=tg_user.get("photo_url"), language_code=tg_user.get("language_code", "en"),
                referral_code=generate_referral_code())
            await self.col.insert_one(new_user.model_dump())
            if referral_code:
                await self._process_referral(telegram_id, referral_code)
        user_doc = await self.col.find_one({"telegram_id": telegram_id}, {"_id": 0})
        token = create_access_token(telegram_id, tg_user.get("username", ""))
        return {"access_token": token, "token_type": "bearer", "user": user_doc}

    async def _process_referral(self, new_user_id: int, referral_code: str):
        referrer = await self.col.find_one({"referral_code": referral_code})
        if not referrer or referrer["telegram_id"] == new_user_id: return
        pts = settings.POINTS_PER_REFERRAL
        await self.col.update_one({"telegram_id": referrer["telegram_id"]},
            {"$inc": {"points": pts, "total_points_earned": pts, "referral_count": 1,
                      "referral_points_earned": pts, "xp": pts // 5}})
        await self.col.update_one({"telegram_id": new_user_id},
            {"$set": {"referred_by": referrer["telegram_id"]},
             "$inc": {"points": settings.POINTS_REFERRER_BONUS, "total_points_earned": settings.POINTS_REFERRER_BONUS}})

    async def get_user(self, telegram_id: int) -> Optional[Dict]:
        return await self.col.find_one({"telegram_id": telegram_id}, {"_id": 0})

    async def get_user_rank(self, telegram_id: int) -> int:
        user = await self.col.find_one({"telegram_id": telegram_id})
        if not user: return 0
        return await self.col.count_documents({"points": {"$gt": user["points"]}}) + 1

    async def connect_wallet(self, telegram_id: int, address: str, wallet_type: str) -> Dict:
        await self.col.update_one({"telegram_id": telegram_id},
            {"$set": {"wallet_address": address, "wallet_type": wallet_type, "updated_at": datetime.utcnow()}})
        return await self.col.find_one({"telegram_id": telegram_id}, {"_id": 0})

    async def get_leaderboard(self, telegram_id: int, limit: int = 50) -> Dict:
        cursor = self.col.find({"is_banned": False},
            {"telegram_id": 1, "username": 1, "first_name": 1, "points": 1,
             "level": 1, "level_title": 1, "active_theme": 1, "_id": 0}).sort("points", -1).limit(limit)
        entries, rank, your_rank = [], 1, None
        async for doc in cursor:
            if doc["telegram_id"] == telegram_id: your_rank = rank
            entries.append({**doc, "rank": rank})
            rank += 1
        total = await self.col.count_documents({"is_banned": False})
        user = await self.col.find_one({"telegram_id": telegram_id})
        if your_rank is None: your_rank = await self.get_user_rank(telegram_id)
        return {"entries": entries, "total_players": total, "your_rank": your_rank,
                "your_points": user["points"] if user else 0}
