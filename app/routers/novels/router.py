from fastapi import Depends, HTTPException, status, Query
from typing import List, Optional
from app.models.novel import NovelInDB, NovelUpdate, PyObjectId, NovelSummary, NovelDetail, NovelType
from app.db.database import get_database
from app.services.core.scraper_service import scrape_novel_info, ScraperError
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.repositories.novel_repository import NovelRepository
from app.routers.base import BaseRouter


class NovelsRouter(BaseRouter):
    def __init__(self):
        super().__init__(prefix="/novels", tags=["novels"])
        self._setup_routes()

    def _setup_routes(self):
        @self.router.post("/", response_model=NovelDetail, status_code=status.HTTP_201_CREATED)
        async def create_novel(novel_in: NovelInDB, novel_repository: NovelRepository = Depends(get_novel_repository)):
            if await novel_repository.exists_by_source_url(str(novel_in.source_url)):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Novel from source URL {novel_in.source_url} already exists.",
                )

            if not novel_in.title or not novel_in.description:
                try:
                    novel_info = await scrape_novel_info(str(novel_in.source_url), novel_in.source_name)
                    novel_in.title = novel_info["title"]
                    novel_in.description = novel_info["description"]
                    novel_in.cover_image_url = novel_info["cover_image_url"]
                    novel_in.tags = novel_info["tags"]
                    novel_in.status = novel_info["status"]
                except ScraperError as e:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to scrape novel info: {str(e)}"
                    )

            created_novel = await novel_repository.create(novel_in)
            return await novel_repository.get_by_id(created_novel.id)

        @self.router.get("/", response_model=List[NovelSummary | NovelInDB])
        async def get_novels(
            novel_repository: NovelRepository = Depends(get_novel_repository),
            skip: int = Query(0, ge=0, description="Number of items to skip"),
            limit: int = Query(100, ge=1, le=100, description="Number of items to return"),
            type: Optional[NovelType] = Query(None, description="Filter by novel type"),
            status: Optional[str] = Query(None, description="Filter by novel status"),
            source_name: Optional[str] = Query(None, description="Filter by source name"),
            search: Optional[str] = Query(None, description="Search in title and description"),
        ):
            query = {}
            if type:
                query["type"] = type
            if status:
                query["status"] = status
            if source_name:
                query["source_name"] = source_name
            if search:
                query["$or"] = [
                    {"title": {"$regex": search, "$options": "i"}},
                    {"description": {"$regex": search, "$options": "i"}},
                ]
            return await novel_repository.filter(query, skip=skip, limit=limit)

        @self.router.get("/{novel_id}", response_model=NovelDetail)
        async def get_novel_by_id(
            novel_id: PyObjectId, novel_repository: NovelRepository = Depends(get_novel_repository)
        ):
            novel = await novel_repository.get_by_id(novel_id)
            if novel is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail=f"Novel with id {novel_id} not found"
                )
            return novel

        @self.router.patch("/{novel_id}", response_model=NovelInDB | NovelDetail | None)
        async def update_novel(
            novel_id: PyObjectId,
            novel_update: NovelUpdate,
            novel_repository: NovelRepository = Depends(get_novel_repository),
        ):
            updated_novel = await novel_repository.update(novel_id, novel_update)
            if updated_novel is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail=f"Novel with id {novel_id} not found"
                )
            return updated_novel

        @self.router.delete("/{novel_id}", status_code=status.HTTP_204_NO_CONTENT)
        async def delete_novel(
            novel_id: PyObjectId, novel_repository: NovelRepository = Depends(get_novel_repository)
        ):
            success = await novel_repository.delete(novel_id)
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail=f"Novel with id {novel_id} not found"
                )
            return

        @self.router.patch("/{novel_id}/reading-progress", response_model=NovelDetail)
        async def update_reading_progress(
            novel_id: PyObjectId,
            current_chapter: int = Query(..., description="The current chapter number being read"),
            novel_repository: NovelRepository = Depends(get_novel_repository),
        ):
            updated_novel = await novel_repository.update_reading_progress(novel_id, current_chapter)
            if updated_novel is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail=f"Novel with id {novel_id} not found"
                )
            return updated_novel

        @self.router.post("/{novel_id}/metadata", response_model=NovelDetail)
        async def update_metadata(
            novel_id: PyObjectId, novel_repository: NovelRepository = Depends(get_novel_repository)
        ):
            novel = await novel_repository.get_by_id(novel_id)
            if novel is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail=f"Novel with id {novel_id} not found"
                )

            try:
                novel_info = await scrape_novel_info(str(novel.source_url), novel.source_name)
                updated_novel = await novel_repository.update_metadata(novel_id, novel_info)
                if updated_novel is None:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND, detail=f"Novel with id {novel_id} not found"
                    )
                return updated_novel
            except ScraperError as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to scrape novel info: {str(e)}"
                )
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Unexpected error: {str(e)}"
                )


def get_novel_repository(db: AsyncIOMotorDatabase = Depends(get_database)) -> NovelRepository:
    return NovelRepository(db)


router = NovelsRouter().get_router()
