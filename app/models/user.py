from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Any
from bson import ObjectId
from datetime import datetime
from pydantic_core import core_schema
from enum import Enum

class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v: Any, *args, **kwargs) -> ObjectId:
        if isinstance(v, ObjectId):
            return v
        if ObjectId.is_valid(v):
            return ObjectId(v)
        raise ValueError("Invalid ObjectId")

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        _source_type: Any,
        _handler: Any
    ) -> core_schema.CoreSchema:
        """
        Return a pydantic_core.CoreSchema that behaves like an ObjectId.
        """
        object_id_schema = core_schema.chain_schema([
            core_schema.str_schema(),
            core_schema.no_info_plain_validator_function(cls.validate),
        ])
        # Handle ObjectId serialization
        return core_schema.json_or_python_schema(
            json_schema=object_id_schema,
            python_schema=core_schema.union_schema([
                core_schema.is_instance_schema(ObjectId),
                object_id_schema
            ]),
            serialization=core_schema.plain_serializer_function_ser_schema(lambda v: str(v)),
        )

    # Pydantic v2 method for JSON schema generation
    @classmethod
    def __get_pydantic_json_schema__(
        cls,
        _core_schema: core_schema.CoreSchema,
        handler: Any # GetJsonSchemaHandler
    ) -> dict[str, Any]:
        # Use the same JSON schema that pydantic generates for strings
        # but override the format to indicate it's an ObjectId string
        json_schema = handler(core_schema.str_schema())
        json_schema.update(format="objectid") # Optional: add format hint
        return json_schema

class UserRole(str, Enum):
    USER = "user"
    ADMIN = "admin"

class UserBase(BaseModel):
    username: str
    email: EmailStr
    full_name: Optional[str] = None
    role: UserRole = UserRole.USER
    is_active: bool = True
    preferences: dict = {
        "default_language": "en",
        "theme": "light",
        "reading_font_size": 16,
        "reading_font_family": "Arial",
        "reading_line_height": 1.5
    }

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None
    preferences: Optional[dict] = None

class UserInDB(UserBase):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    hashed_password: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_login: Optional[datetime] = None

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

class UserPublic(UserBase):
    id: PyObjectId = Field(alias="_id")
    created_at: datetime
    last_login: Optional[datetime] = None 