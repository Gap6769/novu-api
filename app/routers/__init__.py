from fastapi import APIRouter

# Import and include all routers
from .health import router as health_router
from .novels import router as novels_router
from .chapters import router as chapters_router
from .sources import router as sources_router
from .users import router as users_router

# Create the main API router
api_router = APIRouter()


# Include all routers with their respective prefixes
api_router.include_router(health_router)
api_router.include_router(novels_router, prefix="/novels")
api_router.include_router(chapters_router, prefix="/novels")
api_router.include_router(sources_router, prefix="/sources")
api_router.include_router(users_router, prefix="/users")
