from app.routers.novels.router import router
from app.routers.novels.chapters.router import router as chapters_router

__all__ = ["router", "chapters_router"]
