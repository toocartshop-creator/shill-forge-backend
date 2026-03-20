from datetime import datetime, date, timedelta
from typing import Optional, Dict, List
import random, logging, uuid
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.core.config import settings

logger = logging.getLogger(__name__)

UPGRADE_CONFIGS = {
    "u1": {"name": "Turbo Tap",     "base_cost": 500,  "max_lvl": 3, "cost_mult": 1.8},
    "u2": {"name": "Energy Tank",   "base_cost": 800,  "max_lvl": 3, "cost_mult": 1.8},
    "u3": {"name": "Combo Igniter", "base_cost": 600,  "max_lvl": 3, "cost_mult": 1.8},
    "u4": {"name": "Rocket Boost",  "base_cost": 1200, "max_lvl": 2, "cost_mult": 1.8},
}
BOOST_CONFIGS = {
    "b1": {"name": "2X TAP BOOST",  "cost": 400, "duration_mins": 5, "type": "2x"},
    "b2": {"name": "FULL ENERGY",   "cost": 300, "duration_mins": 0, "type": "energy"},
    "b3": {"name": "MEGA COMBO",    "cost": 600, "duration_mins": 3, "type": "megacombo"},
    "b4": {"name": "ENERGY SHIELD", "cost": 800, "duration_mins": 3, "type": "shield"},
}
SPIN_PRIZES = [
    {"label": "+100 PTS",  "type": "pts",    "value": 100,  "xp": 50,  "weight": 20},
    {"label": "+50 PTS",   "type": "pts",    "value": 50,   "xp": 20,  "weight": 30},
    {"label": "+500 PTS",  "type": "pts",    "value": 500,  "xp": 200, "weight": 5},
    {"label": "2X BOOST",  "type": "boost",  "value": 0,    "xp": 0,   "weight": 8},
    {"label": "+250 PTS",  "type": "pts",    "value": 250,  "xp": 100, "weight": 12},
    {"label": "ENERGY+",   "type": "energy", "value": 200,  "xp": 0,   "weight": 10},
    {"label": "+1000 PTS", "type": "pts",    "value": 1000, "xp": 400, "weight": 2},
    {"label": "+75 PTS",   "type": "pts",    "value": 75,   "xp": 30,  "weight": 25},
]
MISSION_POOL = [
    {"id": "m1", "icon": "👆", "name": "TAP MASTER",   "desc": "Tap 50 times today",          "target": 50,  "field": "taps_today",    "reward": 150, "xp": 80},
    {"id": "m2", "icon": "🔥", "name": "COMBO KING",   "desc": "Hit a x5 combo",               "target": 5,   "field": "best_combo",    "reward": 200, "xp": 120},
    {"id": "m3", "icon": "💰", "name": "POINT GRIND",  "desc": "Earn 500 pts by tapping today","target": 500, "field": "tap_pts_today", "reward": 250, "xp": 150},
    {"id": "m4", "icon": "🚀", "name": "COMBO STREAK", "desc": "Hit a x8 combo",               "target": 8,   "field": "best_combo",    "reward": 400, "xp": 200},
    {"id": "m5", "icon": "🌟", "name": "DEEP FORGE",   "desc": "Tap 100 times today",          "target": 100, "field": "taps_today",    "reward": 300, "xp": 180},
    {"id": "m6", "icon": "⚡", "name": "ENERGY DRAIN", "desc": "Use 200 energy today",         "target": 200, "field": "energy_used",   "reward": 120, "xp": 60},
]
THEME_COSTS = {
    "default": 0, "ice": 300, "forest": 300, "crimson": 350, "silver": 400, "plasma": 800,
    "sunset": 900, "toxic": 1000, "ocean": 1000, "rust": 1100, "nebula": 2000, "inferno": 2200,
    "void": 2500, "aurora": 2800, "hologram": 3000, "solar": 5000, "galaxy": 6000,
    "dragon": 7500, "matrix": 8000, "godmode": 10000,
}
LEVELS = [
    {"lvl": 1,  "title": "SHILL ROOKIE",  "xp_needed": 500,   "reward": 100},
    {"lvl": 2,  "title": "SHILL CADET",   "xp_needed": 1200,  "reward": 200},
    {"lvl": 3,  "title": "SHILL AGENT",   "xp_needed": 2500,  "reward": 400},
    {"lvl": 4,  "title": "SHILL VETERAN", "xp_needed": 5000,  "reward": 700},
    {"lvl": 5,  "title": "SHILL ELITE",   "xp_needed": 9000,  "reward": 1200},
    {"lvl": 6,  "title": "SHILL MASTER",  "xp_needed": 15000, "reward": 2000},
    {"lvl": 7,  "title": "SHILL LEGEND",  "xp_needed": 25000, "reward": 3500},
    {"lvl": 8,  "title": "SHILL GOD",     "xp_needed": 40000, "reward": 6000},
    {"lvl": 9,  "title": "FORGE LORD",    "xp_needed": 65000, "reward": 10000},
    {"lvl": 10, "title": "FORGE DEITY",   "xp_needed": 999999,"reward": 0},
]

def today_str() -> str:
    return date.today().isoformat()

class GameService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.users = db.users

    async def _regen_energy(self, user: Dict) -> int:
        max_e = settings.TAP_ENERGY_MAX + user.get("tap_upgrades", {}).get("u2", 0) * 200
        cur = user.get("tap_energy", 0)
        if cur >= max_e:
            return cur
        last = user.get("tap_energy_last_update", datetime.utcnow())
        if isinstance(last, str):
            last = datetime.fromisoformat(last)
        elapsed = (datetime.utcnow() - last).total_seconds()
        regen = min(int(elapsed / 2), max_e - cur)
        new_e = cur + regen
        if regen > 0:
            await self.users.update_one({"telegram_id": user["telegram_id"]},
                {"$set": {"tap_energy": new_e, "tap_energy_last_update": datetime.utcnow()}})
        return new_e

    async def _check_level_up(self, user: Dict) -> Dict:
        xp = user.get("xp", 0)
        current = user.get("level", 1)
        levelled_up = False
        new_level, new_title = current, user.get("level_title", "SHILL ROOKIE")
        for lvl in LEVELS:
            if lvl["lvl"] > current and xp >= LEVELS[lvl["lvl"] - 2]["xp_needed"]:
                new_level, new_title = lvl["lvl"], lvl["title"]
                bonus = LEVELS[lvl["lvl"] - 2]["reward"]
                await self.users.update_one({"telegram_id": user["telegram_id"]},
                    {"$set": {"level": new_level, "level_title": new_title},
                     "$inc": {"points": bonus, "total_points_earned": bonus}})
                levelled_up = True
                break
        return {"levelled_up": levelled_up, "new_level": new_level, "new_title": new_title}

    async def process_tap(self, telegram_id: int, taps: int, combo: int, energy_used: int) -> Dict:
        user = await self.users.find_one({"telegram_id": telegram_id})
        if not user:
            return {"error": "User not found"}
        cur_energy = await self._regen_energy(user)
        max_e = settings.TAP_ENERGY_MAX + user.get("tap_upgrades", {}).get("u2", 0) * 200
        if cur_energy < energy_used:
            energy_used = cur_energy
            taps = energy_used
        if taps <= 0:
            return {"error": "No energy", "new_energy": cur_energy}
        max_daily = settings.DAILY_TAP_LIMIT + user.get("tap_upgrades", {}).get("u4", 0) * 500
        taps_today = user.get("taps_today", 0)
        remaining = max_daily - taps_today
        if remaining <= 0:
            return {"error": "Daily limit reached", "daily_limit_reached": True, "new_energy": cur_energy}
        taps = min(taps, remaining)
        tap_base = user.get("tap_pts_base", 1)
        combo = max(1, min(combo, 10))
        now = datetime.utcnow()
        boost_mult = 1
        valid_boosts = []
        for b in user.get("active_boosts", []):
            exp = b.get("expires_at")
            if exp:
                if isinstance(exp, str): exp = datetime.fromisoformat(exp)
                if exp > now:
                    valid_boosts.append(b)
                    if b.get("type") == "2x": boost_mult = 2
            else:
                valid_boosts.append(b)
        points_earned = tap_base * combo * boost_mult * taps
        xp_earned = points_earned // 5
        new_energy = max(0, cur_energy - energy_used)
        await self.users.update_one({"telegram_id": telegram_id}, {
            "$inc": {"points": points_earned, "total_points_earned": points_earned,
                     "xp": xp_earned, "taps_today": taps, "taps_total": taps,
                     "sfg_tokens_estimated": points_earned / settings.TOKENS_PER_POINTS_RATIO,
                     "tap_pts_today": points_earned, "energy_used": energy_used},
            "$max": {"best_combo": combo},
            "$set": {"tap_energy": new_energy, "tap_energy_last_update": now,
                     "active_boosts": valid_boosts, "updated_at": now},
        })
        user_after = await self.users.find_one({"telegram_id": telegram_id})
        lvl_info = await self._check_level_up(user_after)
        return {"points_earned": points_earned, "new_points": user_after["points"],
                "new_energy": new_energy, "taps_today": user_after["taps_today"],
                "daily_limit_reached": user_after["taps_today"] >= max_daily,
                "xp_earned": xp_earned, "new_xp": user_after["xp"],
                "level_up": lvl_info["levelled_up"], "new_level": lvl_info["new_level"],
                "new_level_title": lvl_info["new_title"]}

    async def daily_checkin(self, telegram_id: int) -> Dict:
        today = today_str()
        if await self.db.daily_checkins.find_one({"telegram_id": telegram_id, "date": today}):
            return {"success": False, "already_claimed": True, "streak": 0, "points_earned": 0}
        user = await self.users.find_one({"telegram_id": telegram_id})
        streak = user.get("checkin_streak", 0)
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        streak = min(streak + 1, 7) if user.get("checkin_last_date") == yesterday else 1
        pts = [50, 75, 100, 125, 150, 175, 500][min(streak - 1, 6)]
        xp = pts // 5
        await self.db.daily_checkins.insert_one({"telegram_id": telegram_id, "date": today, "streak": streak, "points_earned": pts})
        await self.users.update_one({"telegram_id": telegram_id},
            {"$set": {"checkin_streak": streak, "checkin_last_date": today, "updated_at": datetime.utcnow()},
             "$inc": {"points": pts, "total_points_earned": pts, "xp": xp,
                      "sfg_tokens_estimated": pts / settings.TOKENS_PER_POINTS_RATIO}})
        user_after = await self.users.find_one({"telegram_id": telegram_id})
        return {"success": True, "already_claimed": False, "points_earned": pts,
                "new_points": user_after["points"], "streak": streak, "day_of_streak": streak, "xp_earned": xp}

    async def spin_wheel(self, telegram_id: int) -> Dict:
        today = today_str()
        if await self.db.spin_logs.find_one({"telegram_id": telegram_id, "date": today}):
            return {"success": False, "already_spun_today": True, "prize_index": 0, "prize_label": "",
                    "prize_type": "", "prize_value": 0, "new_points": 0}
        weights = [p["weight"] for p in SPIN_PRIZES]
        idx = random.choices(range(len(SPIN_PRIZES)), weights=weights, k=1)[0]
        prize = SPIN_PRIZES[idx]
        pts, xp = 0, prize.get("xp", 0)
        if prize["type"] == "pts":
            pts = prize["value"]
            await self.users.update_one({"telegram_id": telegram_id},
                {"$inc": {"points": pts, "total_points_earned": pts, "xp": xp,
                           "sfg_tokens_estimated": pts / settings.TOKENS_PER_POINTS_RATIO}})
        elif prize["type"] == "energy":
            max_e = settings.TAP_ENERGY_MAX
            user = await self.users.find_one({"telegram_id": telegram_id})
            new_e = min(user.get("tap_energy", 0) + prize["value"], max_e)
            await self.users.update_one({"telegram_id": telegram_id}, {"$set": {"tap_energy": new_e}})
        elif prize["type"] == "boost":
            exp = (datetime.utcnow() + timedelta(minutes=5)).isoformat()
            await self.users.update_one({"telegram_id": telegram_id},
                {"$push": {"active_boosts": {"type": "2x", "expires_at": exp}}})
        await self.db.spin_logs.insert_one({"telegram_id": telegram_id, "date": today, "prize_index": idx, "prize": prize})
        user_after = await self.users.find_one({"telegram_id": telegram_id})
        return {"success": True, "prize_index": idx, "prize_label": prize["label"],
                "prize_type": prize["type"], "prize_value": prize["value"],
                "new_points": user_after["points"], "already_spun_today": False}

    async def get_missions(self, telegram_id: int) -> Dict:
        today = today_str()
        existing = await self.db.user_missions.find_one({"telegram_id": telegram_id, "date": today, "slot": "set"})
        if existing:
            mission_ids = existing["mission_ids"]
        else:
            seed = sum(ord(c) for c in today)
            shuffled = sorted(MISSION_POOL, key=lambda m: (seed * len(m["id"]) * 31) % 97)
            mission_ids = [m["id"] for m in shuffled[:3]]
            await self.db.user_missions.insert_one({"telegram_id": telegram_id, "date": today, "slot": "set", "mission_ids": mission_ids})
        user = await self.users.find_one({"telegram_id": telegram_id})
        claimed_doc = await self.db.user_missions.find_one({"telegram_id": telegram_id, "date": today, "slot": "claimed"})
        claimed_ids = claimed_doc["claimed_ids"] if claimed_doc else []
        missions = []
        for mid in mission_ids:
            m = next((x for x in MISSION_POOL if x["id"] == mid), None)
            if not m: continue
            progress = user.get(m["field"], 0)
            missions.append({"mission_id": m["id"], "name": m["name"], "description": m["desc"],
                             "icon": m["icon"], "target": m["target"], "progress": min(progress, m["target"]),
                             "reward_pts": m["reward"], "xp_reward": m["xp"],
                             "is_complete": progress >= m["target"], "is_claimed": mid in claimed_ids})
        tomorrow = datetime.combine(date.today() + timedelta(days=1), datetime.min.time())
        return {"missions": missions, "resets_at": tomorrow.isoformat()}

    async def claim_mission(self, telegram_id: int, mission_id: str) -> Dict:
        data = await self.get_missions(telegram_id)
        m = next((x for x in data["missions"] if x["mission_id"] == mission_id), None)
        if not m: return {"success": False, "error": "Mission not found"}
        if not m["is_complete"]: return {"success": False, "error": "Mission not completed"}
        if m["is_claimed"]: return {"success": False, "error": "Already claimed"}
        today = today_str()
        await self.db.user_missions.update_one(
            {"telegram_id": telegram_id, "date": today, "slot": "claimed"},
            {"$addToSet": {"claimed_ids": mission_id}}, upsert=True)
        pts, xp = m["reward_pts"], m["xp_reward"]
        await self.users.update_one({"telegram_id": telegram_id},
            {"$inc": {"points": pts, "total_points_earned": pts, "xp": xp,
                      "sfg_tokens_estimated": pts / settings.TOKENS_PER_POINTS_RATIO}})
        user_after = await self.users.find_one({"telegram_id": telegram_id})
        return {"success": True, "points_earned": pts, "xp_earned": xp, "new_points": user_after["points"]}

    async def purchase_upgrade(self, telegram_id: int, upgrade_id: str) -> Dict:
        if upgrade_id not in UPGRADE_CONFIGS:
            return {"success": False, "error": "Invalid upgrade"}
        user = await self.users.find_one({"telegram_id": telegram_id})
        upgrades = user.get("tap_upgrades", {"u1": 0, "u2": 0, "u3": 0, "u4": 0})
        cur_lvl = upgrades.get(upgrade_id, 0)
        cfg = UPGRADE_CONFIGS[upgrade_id]
        if cur_lvl >= cfg["max_lvl"]: return {"success": False, "error": "Already max level"}
        cost = int(cfg["base_cost"] * (cfg["cost_mult"] ** cur_lvl))
        if user["points"] < cost: return {"success": False, "error": "Not enough points"}
        new_lvl = cur_lvl + 1
        new_cost = int(cfg["base_cost"] * (cfg["cost_mult"] ** new_lvl))
        update = {"$inc": {"points": -cost}, "$set": {f"tap_upgrades.{upgrade_id}": new_lvl, "updated_at": datetime.utcnow()}}
        if upgrade_id == "u1":
            update["$set"]["tap_pts_base"] = min(user.get("tap_pts_base", 1) * 2, 8)
        await self.users.update_one({"telegram_id": telegram_id}, update)
        user_after = await self.users.find_one({"telegram_id": telegram_id})
        return {"success": True, "upgrade_id": upgrade_id, "new_level": new_lvl, "new_cost": new_cost,
                "new_points": user_after["points"], "effect_applied": cfg["name"]}

    async def purchase_boost(self, telegram_id: int, boost_id: str) -> Dict:
        if boost_id not in BOOST_CONFIGS: return {"success": False, "error": "Invalid boost"}
        user = await self.users.find_one({"telegram_id": telegram_id})
        cfg = BOOST_CONFIGS[boost_id]
        if user["points"] < cfg["cost"]: return {"success": False, "error": "Not enough points"}
        expires_at = None
        if cfg["type"] == "energy":
            max_e = settings.TAP_ENERGY_MAX + user.get("tap_upgrades", {}).get("u2", 0) * 200
            await self.users.update_one({"telegram_id": telegram_id},
                {"$set": {"tap_energy": max_e, "tap_energy_last_update": datetime.utcnow()}})
        else:
            expires_at = datetime.utcnow() + timedelta(minutes=cfg["duration_mins"])
            await self.users.update_one({"telegram_id": telegram_id},
                {"$push": {"active_boosts": {"type": cfg["type"], "boost_id": boost_id, "expires_at": expires_at.isoformat()}}})
        await self.users.update_one({"telegram_id": telegram_id}, {"$inc": {"points": -cfg["cost"]}})
        user_after = await self.users.find_one({"telegram_id": telegram_id})
        return {"success": True, "boost_id": boost_id, "boost_name": cfg["name"],
                "expires_at": expires_at.isoformat() if expires_at else None,
                "new_points": user_after["points"], "active_boosts": user_after.get("active_boosts", [])}

    async def purchase_theme(self, telegram_id: int, theme_id: str) -> Dict:
        cost = THEME_COSTS.get(theme_id)
        if cost is None: return {"success": False, "error": "Invalid theme"}
        user = await self.users.find_one({"telegram_id": telegram_id})
        if theme_id in user.get("owned_themes", []): return {"success": False, "error": "Already owned"}
        if cost > 0 and user["points"] < cost: return {"success": False, "error": "Not enough points"}
        await self.users.update_one({"telegram_id": telegram_id},
            {"$inc": {"points": -cost}, "$addToSet": {"owned_themes": theme_id}})
        user_after = await self.users.find_one({"telegram_id": telegram_id})
        return {"success": True, "active_theme": user_after["active_theme"],
                "owned_themes": user_after["owned_themes"], "points_remaining": user_after["points"]}

    async def equip_theme(self, telegram_id: int, theme_id: str) -> Dict:
        user = await self.users.find_one({"telegram_id": telegram_id})
        if theme_id not in user.get("owned_themes", []): return {"success": False, "error": "Theme not owned"}
        await self.users.update_one({"telegram_id": telegram_id},
            {"$set": {"active_theme": theme_id, "updated_at": datetime.utcnow()}})
        user_after = await self.users.find_one({"telegram_id": telegram_id})
        return {"success": True, "active_theme": theme_id,
                "owned_themes": user_after["owned_themes"], "points_remaining": user_after["points"]}

    async def complete_task(self, telegram_id: int, task_id: str) -> Dict:
        if await self.db.user_tasks.find_one({"telegram_id": telegram_id, "task_id": task_id}):
            return {"success": False, "already_completed": True, "points_earned": 0, "xp_earned": 0, "new_points": 0}
        task = await self.db.tasks.find_one({"task_id": task_id, "is_active": True})
        if not task: return {"success": False, "error": "Task not found", "already_completed": False, "points_earned": 0, "xp_earned": 0, "new_points": 0}
        await self.db.user_tasks.insert_one({"telegram_id": telegram_id, "task_id": task_id, "completed_at": datetime.utcnow()})
        pts, xp = task["points"], task["points"] // 5
        await self.users.update_one({"telegram_id": telegram_id},
            {"$inc": {"points": pts, "total_points_earned": pts, "xp": xp,
                      "sfg_tokens_estimated": pts / settings.TOKENS_PER_POINTS_RATIO},
             "$addToSet": {"completed_tasks": task_id}})
        user_after = await self.users.find_one({"telegram_id": telegram_id})
        return {"success": True, "points_earned": pts, "xp_earned": xp,
                "new_points": user_after["points"], "already_completed": False}

    async def get_tasks(self, telegram_id: int) -> List[Dict]:
        tasks = []
        async for t in self.db.tasks.find({"is_active": True}, {"_id": 0}):
            done = await self.db.user_tasks.find_one({"telegram_id": telegram_id, "task_id": t["task_id"]})
            tasks.append({**t, "is_completed": bool(done)})
        return tasks
