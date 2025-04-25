from typing import TypeVar, Generic, Type, Optional, List, Dict, Any
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, HttpUrl

T = TypeVar("T", bound=BaseModel)
CreateT = TypeVar("CreateT", bound=BaseModel)
UpdateT = TypeVar("UpdateT", bound=BaseModel)


class BaseRepository(Generic[T, CreateT, UpdateT]):
    def __init__(self, db: AsyncIOMotorDatabase, collection_name: str, model_class: Type[T]):
        self.db = db
        self.collection = getattr(db, collection_name)
        self.model_class = model_class

    def _convert_urls_to_strings(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert HttpUrl objects to strings in a dictionary."""
        result = {}
        for key, value in data.items():
            if isinstance(value, HttpUrl):
                result[key] = str(value)
            elif isinstance(value, dict):
                result[key] = self._convert_urls_to_strings(value)
            elif isinstance(value, list):
                result[key] = [
                    (
                        self._convert_urls_to_strings(item)
                        if isinstance(item, dict)
                        else str(item) if isinstance(item, HttpUrl) else item
                    )
                    for item in value
                ]
            else:
                result[key] = value
        return result

    async def create(self, item: CreateT) -> T:
        """Create a new item."""
        item_dict = item.model_dump()
        item_dict = self._convert_urls_to_strings(item_dict)
        item_dict["added_at"] = datetime.utcnow()
        item_dict["last_updated"] = item_dict["added_at"]

        result = await self.collection.insert_one(item_dict)
        created_item = await self.collection.find_one({"_id": result.inserted_id})
        return self.model_class(**created_item)

    async def get_by_id(self, item_id: Any) -> Optional[T]:
        """Get an item by ID."""
        item = await self.collection.find_one({"_id": item_id})
        return self.model_class(**item) if item else None

    async def update(self, item_id: Any, item_update: UpdateT) -> Optional[T]:
        """Update an item."""
        update_data = item_update.model_dump(exclude_unset=True)
        if not update_data:
            return None

        update_data = self._convert_urls_to_strings(update_data)
        update_data["last_updated"] = datetime.utcnow()

        result = await self.collection.update_one({"_id": item_id}, {"$set": update_data})

        if result.matched_count == 0:
            return None

        updated_item = await self.collection.find_one({"_id": item_id})
        return self.model_class(**updated_item) if updated_item else None

    async def delete(self, item_id: Any) -> bool:
        """Delete an item."""
        result = await self.collection.delete_one({"_id": item_id})
        return result.deleted_count > 0

    async def filter(self, query: Dict[str, Any], skip: int = 0, limit: int = 100) -> List[T]:
        """Filter items by query parameters."""
        cursor = self.collection.find(query).skip(skip).limit(limit)
        items = await cursor.to_list(length=limit)
        return [self.model_class(**item) for item in items]
