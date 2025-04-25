from motor.motor_asyncio import AsyncIOMotorClient
from ..core.config import settings
from typing import Optional


class Database:
    client: Optional[AsyncIOMotorClient] = None
    db = None

    @classmethod
    async def connect(cls, mongodb_url: Optional[str] = None, mongodb_db: Optional[str] = None):
        """Connect to MongoDB asynchronously."""
        try:
            url = mongodb_url or settings.MONGODB_URL
            db_name = mongodb_db or settings.MONGODB_DB_NAME
            print(f"Connecting to MongoDB at {url}...")
            cls.client = AsyncIOMotorClient(url)
            cls.db = cls.client[db_name]
            # Test the connection
            await cls.db.command("ping")
            print(f"Connected to MongoDB database: {db_name}")
        except Exception as e:
            print(f"Error connecting to MongoDB: {e}")
            raise

    @classmethod
    async def disconnect(cls):
        """Close MongoDB connection asynchronously."""
        print("Closing MongoDB connection...")
        if cls.client:
            cls.client.close()
            cls.client = None
            cls.db = None
        print("MongoDB connection closed.")

    @classmethod
    def get_db(cls):
        """Get the database instance."""
        if cls.db is None:
            raise RuntimeError("Database connection not available. Ensure connect() is called at startup.")
        return cls.db


# Global database manager instance
db_manager = Database()


async def connect_to_mongo():
    """Connect to MongoDB using the global database manager."""
    await db_manager.connect()


async def close_mongo_connection():
    """Close MongoDB connection using the global database manager."""
    await db_manager.disconnect()


def get_database():
    """Get the database instance from the global database manager."""
    return db_manager.get_db()
