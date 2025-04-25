from pydantic import BaseModel, Field, HttpUrl
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
    def __get_pydantic_core_schema__(cls, _source_type: Any, _handler: Any) -> core_schema.CoreSchema:
        """
        Return a pydantic_core.CoreSchema that behaves like an ObjectId.
        """
        object_id_schema = core_schema.chain_schema(
            [core_schema.str_schema(), core_schema.no_info_plain_validator_function(cls.validate)]
        )
        # Handle ObjectId serialization
        return core_schema.json_or_python_schema(
            json_schema=object_id_schema,
            python_schema=core_schema.union_schema([core_schema.is_instance_schema(ObjectId), object_id_schema]),
            serialization=core_schema.plain_serializer_function_ser_schema(lambda v: str(v)),
        )

    # Pydantic v2 method for JSON schema generation
    @classmethod
    def __get_pydantic_json_schema__(
        cls,
        _core_schema: core_schema.CoreSchema,
        handler: Any,  # GetJsonSchemaHandler
    ) -> dict[str, Any]:
        # Use the same JSON schema that pydantic generates for strings
        # but override the format to indicate it's an ObjectId string
        json_schema = handler(core_schema.str_schema())
        json_schema.update(format="objectid")  # Optional: add format hint
        return json_schema


class NovelType(str, Enum):
    NOVEL = "novel"
    MANHWA = "manhwa"


class Chapter(BaseModel):
    # Basic chapter structure, can be expanded later
    title: str
    chapter_number: int
    chapter_title: Optional[str] = None  # El título completo del capítulo (ej: "Su Humilde Servidor II")
    url: HttpUrl  # URL to the chapter content
    read: bool = False
    downloaded: bool = False
    # Add more fields as needed, e.g., content, published_date


class NovelBase(BaseModel):
    title: str
    author: Optional[str] = None
    cover_image_url: Optional[HttpUrl] = None
    description: Optional[str] = None
    source_url: HttpUrl
    source_name: str
    source_language: Optional[str] = None
    tags: List[str] = []
    status: Optional[str] = None
    type: NovelType = NovelType.NOVEL


class NovelCreate(NovelBase):
    pass


class NovelUpdate(BaseModel):
    title: Optional[str] = None
    author: Optional[str] = None
    cover_image_url: Optional[HttpUrl] = None
    description: Optional[str] = None
    source_url: Optional[HttpUrl] = None
    source_name: Optional[str] = None
    source_language: Optional[str] = None
    tags: Optional[List[str]] = None
    status: Optional[str] = None
    type: Optional[NovelType] = None


class NovelStats(BaseModel):
    total_chapters: int
    last_chapter_number: int
    read_chapters: int
    downloaded_chapters: int
    reading_progress: float
    last_updated_chapters: Optional[datetime] = None


class NovelInDB(NovelBase):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    added_at: datetime = Field(default_factory=datetime.utcnow)
    last_updated_api: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class NovelDetail(NovelInDB, NovelStats):
    chapters: Optional[List[Chapter]] = None


class NovelSummary(NovelBase, NovelStats):
    id: PyObjectId = Field(alias="_id")
    added_at: datetime

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class ChapterListResponse(BaseModel):
    chapters: List[Chapter]
    total: int
    page: int
    page_size: int
    total_pages: int


class ChapterDownloadResponse(BaseModel):
    success: bool
    message: str
    updated_chapters: List[int]  # List of chapter numbers that were updated
