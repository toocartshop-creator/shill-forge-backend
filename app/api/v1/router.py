from fastapi import APIRouter
from app.api.v1.routes import auth, users, game, squads, admin

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(game.router)
api_router.include_router(squads.router)
api_router.include_router(admin.router)
