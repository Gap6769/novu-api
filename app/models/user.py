from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Dict
from bson import ObjectId
from datetime import datetime
from .novel import PyObjectId
from enum import Enum


class UserRole(str, Enum):
    USER = "user"
    ADMIN = "admin"


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class UserBase(BaseModel):
    """Base user model."""

    username: str
    email: EmailStr
    full_name: Optional[str] = None
    role: UserRole = UserRole.USER
    is_active: bool = True
    preferences: Dict = {"default_language": "en", "reading_font_size": 16, "reading_line_height": 1.5}


class UserCreate(UserBase):
    """Model for creating a new user."""

    password: str


class UserUpdate(BaseModel):
    """Model for updating a user."""

    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    preferences: Optional[Dict] = None
    refresh_token: Optional[str] = None
    refresh_token_expires: Optional[datetime] = None


class UserInDB(UserBase):
    """User model for the database."""

    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    hashed_password: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_login: Optional[datetime] = None
    refresh_token: Optional[str] = None
    refresh_token_expires: Optional[datetime] = None

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class UserPublic(UserBase):
    """Public user model without sensitive information."""

    id: PyObjectId = Field(alias="_id")
    created_at: datetime

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}
