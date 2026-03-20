import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from app.db.database import db_state

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler(timezone="UTC")

async def reset_daily_taps():
    result = await db_state.db.users.update_many({},
        {"$set": {"taps_today": 0, "tap_pts_today": 0, "energy_used": 0}})
    logger.info(f"Daily tap reset: {result.modified_count} users")

async def recalculate_squad_points():
    async for squad in db_state.db.squads.find({}):
        pipeline = [{"$match": {"telegram_id": {"$in": squad.get("members", [])}}},
                    {"$group": {"_id": None, "total": {"$sum": "$points"}}}]
        result = await db_state.db.users.aggregate(pipeline).to_list(1)
        total = result[0]["total"] if result else 0
        await db_state.db.squads.update_one({"squad_id": squad["squad_id"]},
            {"$set": {"total_points": total, "updated_at": datetime.utcnow()}})

async def expire_boosts():
    now = datetime.utcnow().isoformat()
    await db_state.db.users.update_many(
        {"active_boosts": {"$elemMatch": {"expires_at": {"$lt": now}}}},
        {"$pull": {"active_boosts": {"expires_at": {"$lt": now}}}})

def start_scheduler():
    scheduler.add_job(reset_daily_taps, CronTrigger(hour=0, minute=0), id="reset_taps", replace_existing=True)
    scheduler.add_job(recalculate_squad_points, CronTrigger(minute=0), id="squad_pts", replace_existing=True)
    scheduler.add_job(expire_boosts, CronTrigger(minute="*/5"), id="expire_boosts", replace_existing=True)
    scheduler.start()
    logger.info("Scheduler started")

def stop_scheduler():
    scheduler.shutdown()
