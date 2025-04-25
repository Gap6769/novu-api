import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import HttpUrl
from datetime import datetime
from app.models.novel import NovelCreate, NovelUpdate, PyObjectId
from app.db.database import get_database, connect_to_mongo, close_mongo_connection
from app.core.config import settings

async def update_novels():
    # Initialize database connection
    connect_to_mongo()
    
    try:
        # Get database connection
        db = await get_database()
        
        # Update The Beginning After The End
        tbate_update = NovelUpdate(
            title="The Beginning After The End",
            description="King Grey has unrivaled strength, wealth, and prestige in world governed through martial ability. However, solitude lingers closely behind those with great power. Beneath the glamorous exterior of a powerful king lurks the shell of man, devoid of purpose and will. Reincarnated into a new world filled with magic and monsters, the king has a second chance to relive his life. Correcting the mistakes of his past will not be his only challenge, however. Underneath the peace and prosperity of the new world is an undercurrent threatening to destroy everything he has worked for, questioning his role and reason for being born again.",
            cover_image_url=HttpUrl("https://i.gr-assets.com/images/S/compressed.photo.goodreads.com/books/1506190670l/28705056.jpg"),
            tags=["Fantasy", "Manga", "Fiction"],
            status="Ongoing"
        )
        
        # Find TBATE by title
        tbate = await db["novels"].find_one({"title": "The Beginning After The End"})
        if tbate:
            await db["novels"].update_one(
                {"_id": tbate["_id"]},
                {"$set": tbate_update.model_dump(exclude_unset=True)}
            )
            print("Updated The Beginning After The End")
        
        # Create Shadow Slave
        shadow_slave = NovelCreate(
            title="Shadow Slave",
            author="Guiltythree",
            description="Growing up in poverty, Sunny never expected anything good from life. However, even he did not anticipate being chosen by the Nightmare Spell and becoming one of the Awakened - an elite group of people gifted with supernatural powers. Transported into a ruined magical world, he found himself facing against terrible monsters - and other Awakened - in a deadly battle of survival. What's worse, the shadow powers he received happened to possess a small, but potentially fatal side effect...",
            source_url=HttpUrl("https://www.webnovel.com/book/shadow-slave_25000000000000000"),
            source_name="WebNovel.com",
            tags=["Fantasy", "Horror", "Manga"],
            status="Ongoing"
        )
        
        # Check if Shadow Slave already exists
        existing = await db["novels"].find_one({"title": "Shadow Slave"})
        if not existing:
            await db["novels"].insert_one(shadow_slave.model_dump())
            print("Created Shadow Slave")
        else:
            print("Shadow Slave already exists")
    finally:
        # Close database connection
        close_mongo_connection()

if __name__ == "__main__":
    asyncio.run(update_novels()) 