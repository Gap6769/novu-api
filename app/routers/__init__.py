from fastapi import APIRouter
from app.routers.auth.router import router as auth_router
from app.routers.users.router import router as users_router
from app.routers.novels.router import router as novels_router
from app.routers.novels.chapters.router import router as chapters_router
from app.routers.sources.router import router as sources_router
from app.routers.health.router import router as health_router

# Create the main API router
api_router = APIRouter()


# Include all routers with their respective prefixes
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(novels_router)
api_router.include_router(chapters_router, prefix="/novels")
api_router.include_router(sources_router)
api_router.include_router(health_router)
