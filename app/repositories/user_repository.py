from typing import Optional
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.models.user import UserInDB, UserCreate, UserUpdate, PyObjectId
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class UserRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = self.db.users

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return pwd_context.verify(plain_password, hashed_password)

    def get_password_hash(self, password: str) -> str:
        return pwd_context.hash(password)

    async def create(self, user: UserCreate) -> UserInDB:
        """Create a new user."""
        user_dict = user.model_dump(exclude={"password"})
        user_dict["hashed_password"] = self.get_password_hash(user.password)
        user_dict["created_at"] = datetime.utcnow()

        result = await self.collection.insert_one(user_dict)
        created = await self.collection.find_one({"_id": result.inserted_id})
        return UserInDB(**created)

    async def get_by_id(self, user_id: PyObjectId) -> Optional[UserInDB]:
        """Get a user by ID."""
        user = await self.collection.find_one({"_id": user_id})
        return UserInDB(**user) if user else None

    async def get_by_email(self, email: str) -> Optional[UserInDB]:
        """Get a user by email."""
        user = await self.collection.find_one({"email": email})
        return UserInDB(**user) if user else None

    async def get_by_username(self, username: str) -> Optional[UserInDB]:
        """Get a user by username."""
        user = await self.collection.find_one({"username": username})
        return UserInDB(**user) if user else None

    async def update(self, user_id: PyObjectId, user_update: UserUpdate) -> Optional[UserInDB]:
        """Update a user."""
        update_data = user_update.model_dump(exclude_unset=True)

        if "password" in update_data:
            update_data["hashed_password"] = self.get_password_hash(update_data.pop("password"))

        if not update_data:
            return None

        result = await self.collection.update_one({"_id": user_id}, {"$set": update_data})

        if result.matched_count == 0:
            return None

        updated = await self.collection.find_one({"_id": user_id})
        return UserInDB(**updated)

    async def update_last_login(self, user_id: PyObjectId) -> None:
        """Update the last login timestamp for a user."""
        await self.collection.update_one({"_id": user_id}, {"$set": {"last_login": datetime.utcnow()}})

    async def authenticate(self, email: str, password: str) -> Optional[UserInDB]:
        """Authenticate a user."""
        user = await self.get_by_email(email)
        if not user:
            return None
        if not self.verify_password(password, user.hashed_password):
            return None
        return user

    async def delete(self, user_id: PyObjectId) -> bool:
        """Delete a user."""
        result = await self.collection.delete_one({"_id": user_id})
        return result.deleted_count > 0

    async def update_preferences(self, user_id: PyObjectId, preferences: dict) -> Optional[UserInDB]:
        """Update user preferences."""
        result = await self.collection.update_one({"_id": user_id}, {"$set": {"preferences": preferences}})

        if result.matched_count == 0:
            return None

        updated = await self.collection.find_one({"_id": user_id})
        return UserInDB(**updated)
