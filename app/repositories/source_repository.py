from typing import List, Optional
from bson import ObjectId
from app.models.source import SourceInDB, SourceCreate, SourceUpdate
from app.db.database import get_database
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase

class SourceRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = self.db.sources

    async def get_all(self) -> List[SourceInDB]:
        """Get all sources."""
        sources = await self.collection.find().to_list(length=None)
        return [SourceInDB(**source) for source in sources]

    async def get_by_id(self, source_id: str) -> Optional[SourceInDB]:
        """Get a source by ID."""
        source = await self.collection.find_one({"_id": ObjectId(source_id)})
        return SourceInDB(**source) if source else None

    async def get_by_name(self, name: str) -> Optional[SourceInDB]:
        """Get a source by name."""
        source = await self.collection.find_one({"name": name})
        return SourceInDB(**source) if source else None

    async def create(self, source: SourceCreate) -> SourceInDB:
        """Create a new source."""
        source_dict = source.model_dump()
        source_dict["created_at"] = datetime.utcnow()
        source_dict["updated_at"] = source_dict["created_at"]
        
        result = await self.collection.insert_one(source_dict)
        created_source = await self.collection.find_one({"_id": result.inserted_id})
        return SourceInDB(**created_source)

    async def update(self, source_id: str, source: SourceUpdate) -> Optional[SourceInDB]:
        """Update a source."""
        update_data = source.model_dump(exclude_unset=True)
        update_data["updated_at"] = datetime.utcnow()
        
        result = await self.collection.update_one(
            {"_id": ObjectId(source_id)},
            {"$set": update_data}
        )
        
        if result.modified_count:
            updated_source = await self.collection.find_one({"_id": ObjectId(source_id)})
            return SourceInDB(**updated_source)
        return None

    async def delete(self, source_id: str) -> bool:
        """Delete a source."""
        result = await self.collection.delete_one({"_id": ObjectId(source_id)})
        return result.deleted_count > 0

    async def seed_sources(self, sources: List[SourceCreate]) -> List[SourceInDB]:
        """Seed the database with built-in sources."""
        seeded_sources = []
        
        for source in sources:
            try:
                # Check if source already exists
                existing_source = await self.get_by_name(source.name)
                if existing_source:
                    continue
                
                # Create new source
                source_dict = source.dict()
                source_dict["created_at"] = datetime.datetime.utcnow()
                source_dict["updated_at"] = datetime.datetime.utcnow()
                
                result = await self.collection.insert_one(source_dict)
                source_dict["_id"] = result.inserted_id
                seeded_sources.append(SourceInDB(**source_dict))
            except Exception as e:
                print(f"Error seeding source {source.name}: {str(e)}")
                continue
            
        return seeded_sources 