from pydantic import BaseModel, Field, HttpUrl
from typing import Dict, Optional, List, Any
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

class ContentType(str, Enum):
    NOVEL = "novel"
    MANHWA = "manhwa"

class SourceBase(BaseModel):
    name: str
    base_url: str
    content_type: ContentType
    selectors: Dict[str, str]
    patterns: Dict[str, Any]
    use_playwright: bool = False
    headers: Dict[str, str] = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    timeout: float = 10.0
    max_retries: int = 3
    special_actions: Dict[str, Dict[str, Any]] = {
        "view_all": {
            "enabled": False,
            "selector": None,
            "wait_after_click": 0,
            "scroll_after_click": False
        }
    }
    is_active: bool = True

class SourceCreate(SourceBase):
    pass

class SourceUpdate(BaseModel):
    name: Optional[str] = None
    base_url: Optional[str] = None
    content_type: Optional[ContentType] = None
    selectors: Optional[Dict[str, str]] = None
    patterns: Optional[Dict[str, Any]] = None
    use_playwright: Optional[bool] = None
    headers: Optional[Dict[str, str]] = None
    timeout: Optional[float] = None
    max_retries: Optional[int] = None
    special_actions: Optional[Dict[str, Dict[str, Any]]] = None
    is_active: Optional[bool] = None

class SourceInDB(SourceBase):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

class SourcePublic(SourceInDB):
    pass 