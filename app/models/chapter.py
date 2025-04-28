from pydantic import BaseModel, Field, HttpUrl, field_validator
from typing import Optional, List
from bson import ObjectId
from datetime import datetime
from .novel import PyObjectId


class Chapter(BaseModel):
    """Chapter model for the separate collection."""

    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    novel_id: PyObjectId
    title: str
    chapter_number: int
    chapter_title: Optional[str] = None  # El título completo del capítulo (ej: "Su Humilde Servidor II")
    url: HttpUrl  # URL to the chapter content
    read: bool = False
    downloaded: bool = False
    content_type: str  # "novel", "manhwa"
    language: str = "en"
    added_at: datetime = Field(default_factory=datetime.utcnow)
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    reading_progress: float = 0.0  # Progress percentage (0.0 to 1.0)

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class ChapterCreate(BaseModel):
    """Model for creating a new chapter."""

    novel_id: PyObjectId
    title: str
    chapter_number: int
    chapter_title: Optional[str] = None
    url: str  # Changed from HttpUrl to str
    content_type: str
    language: str = "en"

    @field_validator("url")
    def validate_url(cls, v):
        """Convert string URL to HttpUrl for validation."""
        if isinstance(v, str):
            return v
        return str(v)


class ChapterUpdate(BaseModel):
    """Model for updating a chapter."""

    title: Optional[str] = None
    chapter_title: Optional[str] = None
    url: Optional[str] = None  # Changed from HttpUrl to str
    read: Optional[bool] = None
    downloaded: Optional[bool] = None
    content_type: Optional[str] = None
    language: Optional[str] = None


class ChapterListResponse(BaseModel):
    """Response model for paginated chapter lists."""

    chapters: Optional[List[Chapter]] = None
    total: int
    page: int
    page_size: int
    total_pages: int


class ChapterDownloadResponse(BaseModel):
    """Response model for chapter downloads."""

    type: str  # "novel" or "manhwa"
    chapters: List[dict]  # List of chapter content


class ReadingProgress(BaseModel):
    """Model to track reading progress per user and chapter."""

    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    user_id: PyObjectId
    chapter_id: PyObjectId
    progress: float = 0.0  # Progress percentage (0.0 to 1.0)
    last_updated: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class ReadingProgressCreate(BaseModel):
    """Model for creating reading progress."""

    user_id: PyObjectId
    chapter_id: PyObjectId
    progress: float


class ReadingProgressUpdate(BaseModel):
    """Model for updating reading progress."""

    progress: float
