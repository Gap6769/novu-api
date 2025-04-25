from typing import Optional
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.models.chapter import ReadingProgress, ReadingProgressCreate, PyObjectId


class ReadingProgressRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = self.db.reading_progress

    async def create_or_update(self, progress: ReadingProgressCreate) -> ReadingProgress:
        """Create or update reading progress for a user and chapter."""
        # Convert IDs to strings for MongoDB
        user_id_str = str(progress.user_id)
        chapter_id_str = str(progress.chapter_id)

        # Try to find existing progress
        existing = await self.collection.find_one({"user_id": user_id_str, "chapter_id": chapter_id_str})

        if existing:
            # Update existing progress
            result = await self.collection.update_one(
                {"_id": existing["_id"]}, {"$set": {"progress": progress.progress, "last_updated": datetime.utcnow()}}
            )
            updated = await self.collection.find_one({"_id": existing["_id"]})
            return ReadingProgress(**updated)
        else:
            # Create new progress
            progress_dict = progress.model_dump()
            progress_dict["user_id"] = user_id_str
            progress_dict["chapter_id"] = chapter_id_str
            progress_dict["last_updated"] = datetime.utcnow()

            result = await self.collection.insert_one(progress_dict)
            created = await self.collection.find_one({"_id": result.inserted_id})
            return ReadingProgress(**created)

    async def get_progress(self, user_id: PyObjectId, chapter_id: PyObjectId) -> Optional[ReadingProgress]:
        """Get reading progress for a specific user and chapter."""
        progress = await self.collection.find_one({"user_id": str(user_id), "chapter_id": str(chapter_id)})
        return ReadingProgress(**progress) if progress else None

    async def get_user_progress(self, user_id: PyObjectId, novel_id: PyObjectId) -> list[ReadingProgress]:
        """Get all reading progress for a user in a specific novel."""
        # First get all chapter IDs for the novel
        chapters = await self.db.chapters.find({"novel_id": str(novel_id)}, {"_id": 1}).to_list(length=None)

        chapter_ids = [str(chapter["_id"]) for chapter in chapters]

        # Then get all progress for these chapters
        cursor = self.collection.find({"user_id": str(user_id), "chapter_id": {"$in": chapter_ids}})

        progress_list = await cursor.to_list(length=None)
        return [ReadingProgress(**progress) for progress in progress_list]

    async def delete_progress(self, user_id: PyObjectId, chapter_id: PyObjectId) -> bool:
        """Delete reading progress for a specific user and chapter."""
        result = await self.collection.delete_one({"user_id": str(user_id), "chapter_id": str(chapter_id)})
        return result.deleted_count > 0
