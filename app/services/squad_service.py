from datetime import datetime
from typing import Dict, List
import uuid, logging
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.models.squad import SquadModel

logger = logging.getLogger(__name__)

class SquadService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.squads = db.squads
        self.users = db.users

    async def create_squad(self, telegram_id: int, name: str, emoji: str = "⚔️") -> Dict:
        user = await self.users.find_one({"telegram_id": telegram_id})
        if not user: return {"success": False, "error": "User not found"}
        if user.get("squad_id"): return {"success": False, "error": "Already in a squad"}
        if await self.squads.find_one({"name": {"$regex": f"^{name}$", "$options": "i"}}):
            return {"success": False, "error": "Squad name already taken"}
        squad = SquadModel(squad_id=str(uuid.uuid4())[:8].upper(), name=name.upper(),
                           emoji=emoji, owner_telegram_id=telegram_id,
                           members=[telegram_id], total_points=user.get("points", 0))
        await self.squads.insert_one(squad.model_dump())
        await self.users.update_one({"telegram_id": telegram_id}, {"$set": {"squad_id": squad.squad_id}})
        return {"success": True, "squad": squad.model_dump()}

    async def join_squad(self, telegram_id: int, invite_code: str) -> Dict:
        user = await self.users.find_one({"telegram_id": telegram_id})
        if not user: return {"success": False, "error": "User not found"}
        if user.get("squad_id"): return {"success": False, "error": "Already in a squad"}
        squad = await self.squads.find_one({"invite_code": invite_code.upper()})
        if not squad: return {"success": False, "error": "Invalid invite code"}
        if len(squad["members"]) >= squad["max_members"]: return {"success": False, "error": "Squad is full"}
        await self.squads.update_one({"squad_id": squad["squad_id"]},
            {"$addToSet": {"members": telegram_id},
             "$inc": {"total_points": user.get("points", 0)},
             "$set": {"updated_at": datetime.utcnow()}})
        await self.users.update_one({"telegram_id": telegram_id}, {"$set": {"squad_id": squad["squad_id"]}})
        return {"success": True, "squad": await self.squads.find_one({"squad_id": squad["squad_id"]}, {"_id": 0})}

    async def leave_squad(self, telegram_id: int) -> Dict:
        user = await self.users.find_one({"telegram_id": telegram_id})
        if not user or not user.get("squad_id"): return {"success": False, "error": "Not in a squad"}
        squad_id = user["squad_id"]
        await self.squads.update_one({"squad_id": squad_id},
            {"$pull": {"members": telegram_id},
             "$inc": {"total_points": -user.get("points", 0)},
             "$set": {"updated_at": datetime.utcnow()}})
        await self.users.update_one({"telegram_id": telegram_id}, {"$set": {"squad_id": None}})
        squad = await self.squads.find_one({"squad_id": squad_id})
        if squad and len(squad["members"]) == 0:
            await self.squads.delete_one({"squad_id": squad_id})
        return {"success": True}

    async def get_squad(self, squad_id: str, telegram_id: int) -> Dict:
        squad = await self.squads.find_one({"squad_id": squad_id}, {"_id": 0})
        if not squad: return {"success": False, "error": "Squad not found"}
        members = []
        for uid in squad["members"][:20]:
            m = await self.users.find_one({"telegram_id": uid},
                {"telegram_id": 1, "username": 1, "first_name": 1, "points": 1, "level": 1, "_id": 0})
            if m: members.append(m)
        members.sort(key=lambda x: x.get("points", 0), reverse=True)
        user = await self.users.find_one({"telegram_id": telegram_id})
        return {"squad": {"squad_id": squad["squad_id"], "name": squad["name"], "emoji": squad["emoji"],
                          "invite_code": squad["invite_code"], "member_count": len(squad["members"]),
                          "total_points": squad["total_points"], "owner_telegram_id": squad["owner_telegram_id"]},
                "members": members, "your_contribution": user.get("points", 0) if user else 0}

    async def get_leaderboard(self, limit: int = 20) -> List[Dict]:
        squads, rank = [], 1
        async for s in self.squads.find({}, {"_id": 0}).sort("total_points", -1).limit(limit):
            squads.append({"rank": rank, "squad_id": s["squad_id"], "name": s["name"],
                           "emoji": s["emoji"], "total_points": s["total_points"],
                           "member_count": len(s.get("members", []))})
            rank += 1
        return squads
