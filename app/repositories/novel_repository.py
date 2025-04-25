from typing import List, Optional, Dict, Any
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.models.novel import NovelCreate, NovelInDB, NovelUpdate, NovelSummary, NovelDetail, NovelType, PyObjectId
from app.repositories.chapter_repository import ChapterRepository


class NovelRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = self.db.novels
        self.chapter_repository = ChapterRepository(db)

    async def filter(
        self, query: Dict[str, Any], skip: int = 0, limit: int = 100, return_summary: bool = True
    ) -> List[NovelSummary | NovelInDB]:
        """Filter novels by query parameters."""
        novels_cursor = self.collection.find(query).skip(skip).limit(limit)
        novels = await novels_cursor.to_list(length=limit)

        if return_summary:
            return [await self._create_novel_summary(novel) for novel in novels]
        else:
            return [NovelInDB(**novel) for novel in novels]

    async def _create_novel_summary(self, novel: Dict[str, Any]) -> NovelSummary:
        """Create a NovelSummary from a novel document."""
        # Get chapter statistics
        chapters, _ = await self.chapter_repository.get_by_novel_id(novel["_id"])
        total_chapters = len(chapters)
        last_chapter_number = max(chapter.chapter_number for chapter in chapters) if chapters else 0
        read_chapters = sum(1 for chapter in chapters if chapter.read)
        downloaded_chapters = sum(1 for chapter in chapters if chapter.downloaded)

        return NovelSummary(
            _id=novel["_id"],
            title=novel["title"],
            author=novel.get("author"),
            cover_image_url=novel.get("cover_image_url"),
            status=novel.get("status"),
            type=novel.get("type", NovelType.NOVEL),
            total_chapters=total_chapters,
            last_chapter_number=last_chapter_number,
            read_chapters=read_chapters,
            downloaded_chapters=downloaded_chapters,
            last_updated_chapters=novel.get("last_updated_chapters"),
            added_at=novel["added_at"],
            source_language=novel.get("source_language"),
            source_name=novel["source_name"],
            source_url=novel["source_url"],
        )

    async def exists_by_source_url(self, source_url: str) -> bool:
        """Check if a novel exists with the given source URL."""
        novels = await self.filter({"source_url": source_url}, limit=1)
        return len(novels) > 0

    async def create(self, novel: NovelCreate) -> NovelInDB:
        """Create a new novel."""
        novel_dict = novel.model_dump()

        # Ensure URLs are stored as strings
        if "source_url" in novel_dict:
            novel_dict["source_url"] = str(novel_dict["source_url"])
        if "cover_image_url" in novel_dict and novel_dict["cover_image_url"]:
            novel_dict["cover_image_url"] = str(novel_dict["cover_image_url"])

        # Add timestamps
        novel_dict["added_at"] = datetime.utcnow()
        novel_dict["last_updated_api"] = datetime.utcnow()

        result = await self.collection.insert_one(novel_dict)
        created_novel = await self.collection.find_one({"_id": result.inserted_id})
        return NovelInDB(**created_novel)

    async def get_all(self, skip: int = 0, limit: int = 100, type: Optional[NovelType] = None) -> List[NovelSummary]:
        """Get all novels with summary information."""
        query = {}
        if type:
            query["type"] = type
        return await self.filter(query, skip=skip, limit=limit)

    async def get_by_id(self, novel_id: PyObjectId) -> Optional[NovelDetail]:
        """Get a novel by ID with detailed information."""
        novels = await self.filter({"_id": novel_id}, limit=1, return_summary=False)
        if not novels:
            return None

        novel = novels[0]

        # Get chapter statistics
        chapters, _ = await self.chapter_repository.get_by_novel_id(novel_id)
        total_chapters = len(chapters)
        last_chapter_number = max(chapter.chapter_number for chapter in chapters) if chapters else 0
        read_chapters = sum(1 for chapter in chapters if chapter.read)
        downloaded_chapters = sum(1 for chapter in chapters if chapter.downloaded)

        # Calculate reading progress
        reading_progress = (read_chapters / total_chapters * 100) if total_chapters > 0 else 0

        return NovelDetail(
            _id=novel.id,
            title=novel.title,
            author=novel.author,
            cover_image_url=novel.cover_image_url,
            status=novel.status,
            type=novel.type,
            total_chapters=total_chapters,
            last_chapter_number=last_chapter_number,
            read_chapters=read_chapters,
            downloaded_chapters=downloaded_chapters,
            last_updated_chapters=novel.last_updated_chapters,
            added_at=novel.added_at,
            description=novel.description,
            source_url=novel.source_url,
            source_name=novel.source_name,
            tags=novel.tags,
            reading_progress=reading_progress,
            source_language=novel.source_language,
        )

    async def update(self, novel_id: PyObjectId, novel_update: NovelUpdate) -> Optional[NovelDetail]:
        """Update a novel."""
        update_data = novel_update.model_dump(exclude_unset=True)

        if not update_data:
            return None

        # Ensure URLs are stored as strings if they are being updated
        if "source_url" in update_data and update_data["source_url"]:
            update_data["source_url"] = str(update_data["source_url"])
        if "cover_image_url" in update_data and update_data["cover_image_url"]:
            update_data["cover_image_url"] = str(update_data["cover_image_url"])

        # Update timestamp
        update_data["last_updated_api"] = datetime.utcnow()

        result = await self.collection.update_one({"_id": novel_id}, {"$set": update_data})

        if result.matched_count == 0:
            return None

        return await self.get_by_id(novel_id)

    async def delete(self, novel_id: PyObjectId) -> bool:
        """Delete a novel."""
        result = await self.collection.delete_one({"_id": novel_id})
        return result.deleted_count > 0

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
