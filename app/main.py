from fastapi import FastAPI
from contextlib import asynccontextmanager
from .routers import api_router
from .db.database import connect_to_mongo, close_mongo_connection
from .core.config import settings
from fastapi.middleware.cors import CORSMiddleware
from scalar_fastapi import get_scalar_api_reference
from scalar_fastapi.scalar_fastapi import Layout

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("Starting up...")
    await connect_to_mongo()
    yield
    # Shutdown
    print("Shutting down...")
    await close_mongo_connection()

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="API to manage webnovels and related data.",
    version="0.1.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/scalar", include_in_schema=False)
async def scalar_html():
    return get_scalar_api_reference(
        openapi_url=app.openapi_url,
        title=app.title,
        hide_download_button=False,
        hide_models=True,
        dark_mode=True,
        default_open_all_tags=True,
    )

# Include the main API router
app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/")
async def root():
    return {"message": f"Welcome to the {settings.PROJECT_NAME}"}
