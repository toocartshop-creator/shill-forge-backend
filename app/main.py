import logging, asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from app.api.v1.router import api_router
from app.core.config import settings
from app.db.database import connect_db, disconnect_db, db_state
from app.utils.rate_limit import limiter, rate_limit_handler
from app.utils.scheduler import start_scheduler, stop_scheduler
from app.utils.telegram_bot import start_bot, stop_bot

logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"🚀 Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    try:
        await connect_db()
        await seed_default_tasks()
        start_scheduler()
        asyncio.create_task(start_bot())
    except Exception as e:
        logger.error(f"Startup error: {e}")
    yield
    await stop_bot()
    stop_scheduler()
    await disconnect_db()
    logger.info("👋 ShillForge API shut down")

async def seed_default_tasks():
    db = db_state.db
    default_tasks = [
        {"task_id": "join_telegram",  "name": "Join Telegram Channel", "description": "Subscribe to @ShillForge_Official", "icon": "📣", "points": 300, "xp": 60,  "is_active": True, "type": "social"},
        {"task_id": "follow_twitter", "name": "Follow on Twitter/X",   "description": "Follow @ShillForge & retweet pin",   "icon": "𝕏",  "points": 250, "xp": 50,  "is_active": True, "type": "social"},
        {"task_id": "follow_instagram","name": "Follow on Instagram",  "description": "Follow @ShillForge on Instagram",     "icon": "📸", "points": 200, "xp": 40,  "is_active": True, "type": "social"},
        {"task_id": "join_discord",   "name": "Join Discord Server",   "description": "Join the ShillForge Discord",         "icon": "🎮", "points": 300, "xp": 60,  "is_active": True, "type": "social"},
        {"task_id": "watch_video",    "name": "Watch & Earn",          "description": "Watch 30s promo video",               "icon": "▶️", "points": 500, "xp": 100, "is_active": True, "type": "video"},
        {"task_id": "invite_friend",  "name": "Invite a Friend",       "description": "Refer someone who joins",             "icon": "👥", "points": 200, "xp": 40,  "is_active": True, "type": "referral"},
        {"task_id": "join_channel_1", "name": "Join News Channel",     "description": "Subscribe to @ShillForge_News",       "icon": "📰", "points": 150, "xp": 30,  "is_active": True, "type": "social"},
        {"task_id": "join_channel_2", "name": "Join Alpha Channel",    "description": "Subscribe to @ShillForge_Alpha",      "icon": "⚡", "points": 150, "xp": 30,  "is_active": True, "type": "social"},
    ]
    for task in default_tasks:
        await db.tasks.update_one({"task_id": task["task_id"]}, {"$setOnInsert": task}, upsert=True)
    logger.info(f"✅ {len(default_tasks)} default tasks seeded")

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME, version=settings.APP_VERSION,
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc", lifespan=lifespan,
    )
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_handler)
    app.add_middleware(SlowAPIMiddleware)
    app.add_middleware(CORSMiddleware, allow_origins=settings.ALLOWED_ORIGINS,
                       allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled error: {exc}", exc_info=True)
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    app.include_router(api_router)

    @app.get("/health", tags=["Health"])
    async def health():
        return {"status": "ok", "service": settings.APP_NAME, "version": settings.APP_VERSION}

    @app.get("/", tags=["Health"])
    async def root():
        return {"message": "⚡ ShillForge API is live 🚀", "docs": "/redoc"}

    return app

app = create_app()
