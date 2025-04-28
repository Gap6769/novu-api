from typing import List, Optional, Dict, Any
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.models.novel import NovelInDB, NovelUpdate, NovelSummary, NovelDetail, NovelType, PyObjectId, NovelStats
from app.repositories.chapter_repository import ChapterRepository
from app.repositories.base_repository import BaseRepository


class NovelRepository(BaseRepository[NovelInDB, NovelInDB, NovelUpdate]):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, "novels", NovelInDB)
        self.chapter_repository = ChapterRepository(db)

    async def _calculate_novel_stats(self, novel_id: PyObjectId) -> NovelStats:
        """Calculate statistics for a novel based on its chapters."""
        chapters, _ = await self.chapter_repository.get_by_novel_id(novel_id, limit=None)
        total_chapters = len(chapters)
        last_chapter_number = max(chapter.chapter_number for chapter in chapters) if chapters else 0
        read_chapters = sum(1 for chapter in chapters if chapter.read)
        downloaded_chapters = sum(1 for chapter in chapters if chapter.downloaded)
        reading_progress = (read_chapters / total_chapters * 100) if total_chapters > 0 else 0

        return NovelStats(
            total_chapters=total_chapters,
            last_chapter_number=last_chapter_number,
            read_chapters=read_chapters,
            downloaded_chapters=downloaded_chapters,
            reading_progress=reading_progress,
            last_updated_chapters=datetime.utcnow() if chapters else None,
        )

    async def filter(
        self, query: Dict[str, Any], skip: int = 0, limit: int = 100, return_summary: bool = True
    ) -> List[NovelSummary]:
        """Filter novels by query parameters."""
        novels = await super().filter(query, skip, limit)
        return [await self._create_novel_summary(novel) for novel in novels]

    async def _create_novel_summary(self, novel: NovelInDB) -> NovelSummary:
        """Create a NovelSummary from a novel document."""
        stats = await self._calculate_novel_stats(novel.id)
        novel_dict = novel.model_dump(by_alias=True)
        return NovelSummary(**novel_dict, **stats.model_dump())

    async def exists_by_source_url(self, source_url: str) -> bool:
        """Check if a novel exists with the given source URL."""
        novels = await self.filter({"source_url": source_url}, limit=1)
        return len(novels) > 0

    async def get_all(self, skip: int = 0, limit: int = 100, type: Optional[NovelType] = None) -> List[NovelSummary]:
        """Get all novels with summary information."""
        query = {}
        if type:
            query["type"] = type
        return await self.filter(query, skip=skip, limit=limit)

    async def get_by_id(self, novel_id: PyObjectId) -> Optional[NovelDetail]:
        """Get a novel by ID with detailed information."""
        novel = await super().get_by_id(novel_id)
        if not novel:
            return None

        chapters, _ = await self.chapter_repository.get_by_novel_id(novel_id)
        stats = await self._calculate_novel_stats(novel_id)

        # Convertir los capítulos a diccionarios
        chapters_dict = [chapter.model_dump(by_alias=True) for chapter in chapters]

        return NovelDetail(**novel.model_dump(by_alias=True), **stats.model_dump(), chapters=chapters_dict)

    async def update_metadata(self, novel_id: PyObjectId, novel_info: dict) -> Optional[NovelDetail]:
        """Update the metadata of a novel."""
        update_data = {
            "title": novel_info["title"],
            "author": novel_info["author"],
            "description": novel_info["description"],
            "cover_image_url": novel_info["cover_image_url"],
            "tags": novel_info["tags"],
            "status": novel_info["status"],
            "last_updated_api": datetime.utcnow(),
        }

        # Ensure URLs are stored as strings
        if update_data["cover_image_url"]:
            update_data["cover_image_url"] = str(update_data["cover_image_url"])

        result = await self.collection.update_one({"_id": novel_id}, {"$set": update_data})

        if result.matched_count == 0:
            return None

        return await self.get_by_id(novel_id)
