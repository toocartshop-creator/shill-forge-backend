from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import IndexModel, ASCENDING, DESCENDING
from typing import Optional
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

class Database:
    client: Optional[AsyncIOMotorClient] = None
    db: Optional[AsyncIOMotorDatabase] = None

db_state = Database()

async def connect_db():
    logger.info("Connecting to MongoDB...")
    db_state.client = AsyncIOMotorClient(settings.MONGODB_URL, serverSelectionTimeoutMS=5000, maxPoolSize=20, minPoolSize=2)
    db_state.db = db_state.client[settings.MONGODB_DB_NAME]
    await create_indexes()
    logger.info(f"Connected to MongoDB: {settings.MONGODB_DB_NAME}")

async def disconnect_db():
    if db_state.client:
        db_state.client.close()
        logger.info("MongoDB connection closed")

async def create_indexes():
    db = db_state.db
    await db.users.create_indexes([
        IndexModel([("telegram_id", ASCENDING)], unique=True),
        IndexModel([("referral_code", ASCENDING)], unique=True, sparse=True),
        IndexModel([("points", DESCENDING)]),
        IndexModel([("squad_id", ASCENDING)]),
        IndexModel([("is_banned", ASCENDING)]),
    ])
    await db.tasks.create_indexes([IndexModel([("task_id", ASCENDING)], unique=True)])
    await db.user_tasks.create_indexes([IndexModel([("telegram_id", ASCENDING), ("task_id", ASCENDING)], unique=True)])
    await db.tap_sessions.create_indexes([IndexModel([("telegram_id", ASCENDING), ("date", ASCENDING)], unique=True)])
    await db.daily_checkins.create_indexes([IndexModel([("telegram_id", ASCENDING), ("date", ASCENDING)], unique=True)])
    await db.spin_logs.create_indexes([IndexModel([("telegram_id", ASCENDING), ("date", ASCENDING)], unique=True)])
    await db.squads.create_indexes([
        IndexModel([("squad_id", ASCENDING)], unique=True),
        IndexModel([("invite_code", ASCENDING)], unique=True),
        IndexModel([("total_points", DESCENDING)]),
    ])
    await db.user_missions.create_indexes([IndexModel([("telegram_id", ASCENDING), ("date", ASCENDING), ("slot", ASCENDING)], unique=True)])
    logger.info("MongoDB indexes ensured")

def get_db() -> AsyncIOMotorDatabase:
    return db_state.db
