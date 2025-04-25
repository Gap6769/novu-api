from fastapi import Depends, HTTPException, status, Query
from typing import List, Optional
from app.models.source import SourceCreate, SourcePublic, SourceUpdate, PyObjectId
from app.db.database import get_database
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.repositories.source_repository import SourceRepository
from app.routers.base import BaseRouter


class SourcesRouter(BaseRouter):
    def __init__(self):
        super().__init__(prefix="/sources", tags=["sources"])
        self._setup_routes()

    def _setup_routes(self):
        @self.router.post("/", response_model=SourcePublic, status_code=status.HTTP_201_CREATED)
        async def create_source(
            source_in: SourceCreate, source_repository: SourceRepository = Depends(get_source_repository)
        ):
            if await source_repository.get_by_name(source_in.name):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT, detail=f"Source with name {source_in.name} already exists."
                )
            return await source_repository.create(source_in)

        @self.router.get("/", response_model=List[SourcePublic])
        async def get_sources(
            source_repository: SourceRepository = Depends(get_source_repository),
            skip: int = Query(0, ge=0, description="Number of items to skip"),
            limit: int = Query(100, ge=1, le=100, description="Number of items to return"),
            search: Optional[str] = Query(None, description="Search in name and description"),
        ):
            query = {}
            if search:
                query["$or"] = [
                    {"name": {"$regex": search, "$options": "i"}},
                    {"description": {"$regex": search, "$options": "i"}},
                ]
            return await source_repository.filter(query, skip=skip, limit=limit)

        @self.router.get("/{source_id}", response_model=SourcePublic)
        async def get_source_by_id(
            source_id: PyObjectId, source_repository: SourceRepository = Depends(get_source_repository)
        ):
            source = await source_repository.get_by_id(source_id)
            if source is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail=f"Source with id {source_id} not found"
                )
            return source

        @self.router.patch("/{source_id}", response_model=SourcePublic)
        async def update_source(
            source_id: PyObjectId,
            source_update: SourceUpdate,
            source_repository: SourceRepository = Depends(get_source_repository),
        ):
            updated_source = await source_repository.update(source_id, source_update)
            if updated_source is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail=f"Source with id {source_id} not found"
                )
            return updated_source

        @self.router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
        async def delete_source(
            source_id: PyObjectId, source_repository: SourceRepository = Depends(get_source_repository)
        ):
            success = await source_repository.delete(source_id)
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail=f"Source with id {source_id} not found"
                )
            return


def get_source_repository(db: AsyncIOMotorDatabase = Depends(get_database)) -> SourceRepository:
    return SourceRepository(db)


router = SourcesRouter().get_router()
