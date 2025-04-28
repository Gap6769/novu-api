from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from bson import ObjectId

from app.core.config import settings
from app.models.user import UserInDB, UserUpdate, Token
from app.repositories.user_repository import UserRepository


class AuthService:
    def __init__(self, user_repository: UserRepository):
        self.user_repository = user_repository

    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None) -> str:
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=15)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        return encoded_jwt

    def create_refresh_token(self, data: dict, expires_delta: Optional[timedelta] = None) -> str:
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, settings.REFRESH_SECRET_KEY, algorithm=settings.ALGORITHM)
        return encoded_jwt

    async def authenticate_user(self, username: str, password: str) -> Optional[UserInDB]:
        return await self.user_repository.authenticate(username, password)

    async def login(self, username: str, password: str) -> Token:
        user = await self.authenticate_user(username, password)
        if not user:
            raise ValueError("Incorrect username or password")

        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        refresh_token_expires = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

        access_token = self.create_access_token(data={"sub": str(user.id)}, expires_delta=access_token_expires)
        refresh_token = self.create_refresh_token(data={"sub": str(user.id)}, expires_delta=refresh_token_expires)

        # Store refresh token in database
        user_update = UserUpdate(
            refresh_token=refresh_token, refresh_token_expires=datetime.utcnow() + refresh_token_expires
        )
        await self.user_repository.update(user.id, user_update)

        return Token(access_token=access_token, refresh_token=refresh_token, token_type="bearer")

    async def refresh_access_token(self, refresh_token: str) -> Token:
        try:
            payload = jwt.decode(refresh_token, settings.REFRESH_SECRET_KEY, algorithms=[settings.ALGORITHM])
            user_id: str = payload.get("sub")
            if user_id is None:
                raise ValueError("Invalid refresh token")

            user_id_obj = ObjectId(user_id)
            user = await self.user_repository.get_by_id(user_id_obj)

            if user is None or user.refresh_token != refresh_token:
                raise ValueError("Invalid refresh token")

            if user.refresh_token_expires and user.refresh_token_expires < datetime.utcnow():
                raise ValueError("Refresh token has expired")

            access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
            access_token = self.create_access_token(data={"sub": str(user.id)}, expires_delta=access_token_expires)

            return Token(access_token=access_token, refresh_token=refresh_token, token_type="bearer")

        except JWTError:
            raise ValueError("Invalid refresh token")

    async def get_current_user(self, token: str) -> UserInDB:
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            user_id: str = payload.get("sub")
            if user_id is None:
                raise ValueError("Could not validate credentials")

            user_id_obj = ObjectId(user_id)
            user = await self.user_repository.get_by_id(user_id_obj)
            if user is None:
                raise ValueError("Could not validate credentials")

            return user
        except JWTError:
            raise ValueError("Could not validate credentials")
