from typing import List, Optional, Dict, Any
from bson import ObjectId
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.models.chapter import Chapter, ChapterCreate, ChapterUpdate, PyObjectId

class ChapterRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = self.db.chapters

    async def create(self, chapter: ChapterCreate) -> Chapter:
        """Create a new chapter."""
        chapter_dict = chapter.model_dump()
        
        # Store novel_id as string
        chapter_dict["novel_id"] = str(chapter_dict["novel_id"])
            
        chapter_dict["added_at"] = datetime.utcnow()
        chapter_dict["last_updated"] = chapter_dict["added_at"]
        
        result = await self.collection.insert_one(chapter_dict)
        created_chapter = await self.collection.find_one({"_id": result.inserted_id})
        return Chapter(**created_chapter)

    async def get_by_id(self, chapter_id: PyObjectId) -> Optional[Chapter]:
        """Get a chapter by ID."""
        chapter = await self.collection.find_one({"_id": chapter_id})
        return Chapter(**chapter) if chapter else None

    async def get_by_novel_id(self, novel_id: PyObjectId, skip: int = 0, limit: int = 100, sort_order: str = "desc") -> tuple[List[Chapter], int]:
        """Get all chapters for a novel and the total count."""
        # Convert novel_id to string for comparison
        novel_id_str = str(novel_id)
            
        # Get total count
        total = await self.collection.count_documents({"novel_id": novel_id_str})
        
        # Get paginated chapters with sorting
        sort_direction = -1 if sort_order == "desc" else 1
        cursor = self.collection.find({"novel_id": novel_id_str})\
            .sort("chapter_number", sort_direction)\
            .skip(skip)\
            .limit(limit)
            
        chapters = await cursor.to_list(length=limit)
        
        return [Chapter(**chapter) for chapter in chapters], total

    async def get_by_number(self, novel_id: PyObjectId, chapter_number: int) -> Optional[Chapter]:
        """Get a chapter by its number for a specific novel."""
        novel_id_str = str(novel_id)
        chapter = await self.collection.find_one({
            "novel_id": novel_id_str,
            "chapter_number": chapter_number
        })
        return Chapter(**chapter) if chapter else None

    async def update(self, chapter_id: PyObjectId, chapter_update: ChapterUpdate) -> Optional[Chapter]:
        """Update a chapter."""
        update_data = chapter_update.model_dump(exclude_unset=True)
        if not update_data:
            return None
            
        update_data["last_updated"] = datetime.utcnow()
        
        result = await self.collection.update_one(
            {"_id": chapter_id},
            {"$set": update_data}
        )
        
        if result.matched_count == 0:
            return None
            
        updated_chapter = await self.collection.find_one({"_id": chapter_id})
        return Chapter(**updated_chapter)

    async def delete(self, chapter_id: PyObjectId) -> bool:
        """Delete a chapter."""
        result = await self.collection.delete_one({"_id": chapter_id})
        return result.deleted_count > 0

    async def delete_by_novel_id(self, novel_id: PyObjectId) -> int:
        """Delete all chapters for a novel."""
        result = await self.collection.delete_many({"novel_id": novel_id})
        return result.deleted_count

    async def mark_as_read(self, chapter_id: PyObjectId) -> Optional[Chapter]:
        """Mark a chapter as read."""
        return await self.update(chapter_id, ChapterUpdate(read=True))

    async def mark_as_downloaded(self, chapter_id: PyObjectId, local_path: str) -> Optional[Chapter]:
        """Mark a chapter as downloaded and set its local path."""
        return await self.update(chapter_id, ChapterUpdate(downloaded=True, local_path=local_path))

    async def get_next_chapter(self, novel_id: PyObjectId, current_chapter_number: int) -> Optional[Chapter]:
        """Get the next chapter after the current one."""
        chapter = await self.collection.find_one({
            "novel_id": novel_id,
            "chapter_number": {"$gt": current_chapter_number}
        }, sort=[("chapter_number", 1)])
        return Chapter(**chapter) if chapter else None

    async def get_previous_chapter(self, novel_id: PyObjectId, current_chapter_number: int) -> Optional[Chapter]:
        """Get the previous chapter before the current one."""
        chapter = await self.collection.find_one({
            "novel_id": novel_id,
            "chapter_number": {"$lt": current_chapter_number}
        }, sort=[("chapter_number", -1)])
        return Chapter(**chapter) if chapter else None 