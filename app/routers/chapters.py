from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from ..models.novel import NovelType, PyObjectId, NovelUpdate
from ..models.chapter import (
    ChapterCreate,
    ChapterListResponse,
    ChapterDownloadResponse,
    ReadingProgress,
    ReadingProgressCreate,
)
from ..db.database import get_database
from motor.motor_asyncio import AsyncIOMotorDatabase
from ..services.epub_service import epub_service
from ..services.scraper_service import scrape_chapters_for_novel, ScraperError, scrape_chapter_content
from fastapi.responses import StreamingResponse
import io
from datetime import datetime
from ..services.translation_service import translation_service
from ..services.storage_service import storage_service
from ..repositories.chapter_repository import ChapterRepository
from ..repositories.novel_repository import NovelRepository
from ..repositories.reading_progress_repository import ReadingProgressRepository
from ..routers.users import get_current_user
from ..models.user import UserInDB

router = APIRouter()


def get_chapter_repository(db: AsyncIOMotorDatabase = Depends(get_database)) -> ChapterRepository:
    return ChapterRepository(db)


def get_novel_repository(db: AsyncIOMotorDatabase = Depends(get_database)) -> NovelRepository:
    return NovelRepository(db)


def get_reading_progress_repository(db: AsyncIOMotorDatabase = Depends(get_database)) -> ReadingProgressRepository:
    return ReadingProgressRepository(db)


@router.get("/{novel_id}/chapters", response_model=ChapterListResponse, tags=["chapters"])
async def get_chapters(
    novel_id: PyObjectId,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    chapter_repository: ChapterRepository = Depends(get_chapter_repository),
    novel_repository: NovelRepository = Depends(get_novel_repository),
):
    """Get paginated list of chapters for a novel."""
    # Verify novel exists
    novel = await novel_repository.get_by_id(novel_id)
    if novel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Novel with id {novel_id} not found")

    # Get chapters with pagination, sorting and total count in a single query
    skip = (page - 1) * page_size
    chapters, total_chapters = await chapter_repository.get_by_novel_id(
        novel_id, skip=skip, limit=page_size, sort_order=sort_order
    )

    # Calculate total pages
    total_pages = (total_chapters + page_size - 1) // page_size

    return ChapterListResponse(
        chapters=chapters, total=total_chapters, page=page, page_size=page_size, total_pages=total_pages
    )


@router.get("/{novel_id}/chapters/{chapter_number}", tags=["chapters"])
async def download_chapter(
    novel_id: PyObjectId,
    chapter_number: int,
    language: str = Query("en", pattern="^(en|es)$"),
    format: str = Query("epub", pattern="^(epub|raw)$"),
    chapter_repository: ChapterRepository = Depends(get_chapter_repository),
    novel_repository: NovelRepository = Depends(get_novel_repository),
):
    """Download a specific chapter."""
    # Verify novel exists
    novel = await novel_repository.get_by_id(novel_id)
    if novel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Novel with id {novel_id} not found")

    # Get chapter
    chapter = await chapter_repository.get_by_number(novel_id, chapter_number)
    if not chapter:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Chapter {chapter_number} not found")

    try:
        # Si es un manhwa, devolver el contenido en formato raw
        if novel.type == NovelType.MANHWA:
            content = await scrape_chapter_content(str(chapter.url), novel.source_name, str(novel_id), chapter_number)

            # Update chapter status
            await chapter_repository.mark_as_downloaded(chapter.id, str(chapter.url))
            await chapter_repository.mark_as_read(chapter.id)

            return content

        # Para novelas, mantener la lógica existente
        if format == "epub":
            # Generate the EPUB
            epub_bytes, filename = await epub_service.create_epub(
                novel_id=str(novel_id),
                novel_title=novel.title,
                author=novel.author or "Unknown",
                chapters=[chapter],
                source_name=novel.source_name,
                single_chapter=chapter_number,
                translate=(language == "es"),
            )

            # Update chapter status
            await chapter_repository.mark_as_downloaded(chapter.id, str(chapter.url))
            await chapter_repository.mark_as_read(chapter.id)

            return StreamingResponse(
                io.BytesIO(epub_bytes),
                media_type="application/epub+zip",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )
        else:  # format == "raw"
            # Check if we have cached content
            cached_content = await storage_service.get_chapter(str(novel_id), chapter_number, "raw", language)
            if cached_content:
                cleaned_content = cached_content
            else:
                # Get raw chapter content
                raw_content = await epub_service.fetch_chapter_content(
                    chapter_url=str(chapter.url),
                    source_name=novel.source_name,
                    novel_id=str(novel_id),
                    chapter_number=chapter_number,
                )
                cleaned_content = epub_service.clean_content(raw_content)

                if language == "es" and novel.source_language == "en":
                    cleaned_content = await translation_service.translate_text(cleaned_content)

                await storage_service.save_chapter(str(novel_id), chapter_number, cleaned_content, "raw", language)

            # Update chapter status
            await chapter_repository.mark_as_downloaded(chapter.id, str(chapter.url))
            await chapter_repository.mark_as_read(chapter.id)

            return {
                "title": chapter.title,
                "chapter_number": chapter.chapter_number,
                "chapter_title": chapter.chapter_title,
                "content": cleaned_content,
            }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error processing chapter: {str(e)}"
        )


@router.post("/{novel_id}/chapters/download", response_model=ChapterDownloadResponse, tags=["chapters"])
async def download_chapters(
    novel_id: PyObjectId,
    chapter_numbers: List[int],
    language: str = Query("en", pattern="^(en|es)$"),
    chapter_repository: ChapterRepository = Depends(get_chapter_repository),
    novel_repository: NovelRepository = Depends(get_novel_repository),
):
    """Download multiple chapters."""
    # Verify novel exists
    novel = await novel_repository.get_by_id(novel_id)
    if novel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Novel with id {novel_id} not found")

    # Get chapters
    chapters = []
    for chapter_number in chapter_numbers:
        chapter = await chapter_repository.get_by_number(novel_id, chapter_number)
        if chapter:
            chapters.append(chapter)

    if not chapters:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No valid chapters found")

    try:
        # Si es un manhwa, devolver el contenido de cada capítulo
        if novel.type == NovelType.MANHWA:
            chapters_content = []
            for chapter in chapters:
                content = await scrape_chapter_content(
                    str(chapter.url), novel.source_name, str(novel_id), chapter.chapter_number
                )
                chapters_content.append(
                    {"chapter_number": chapter.chapter_number, "title": chapter.title, "content": content}
                )

            # Update chapter statuses
            for chapter in chapters:
                await chapter_repository.mark_as_downloaded(chapter.id, str(chapter.url))
                await chapter_repository.mark_as_read(chapter.id)

            return {"type": "manhwa", "chapters": chapters_content}

        # Para novelas, mantener la lógica existente
        # Generate the EPUB
        epub_bytes, filename = await epub_service.create_epub(
            novel_id=str(novel_id),
            novel_title=novel.title,
            author=novel.author or "Unknown",
            chapters=chapters,
            source_name=novel.source_name,
            translate=(language == "es"),
        )

        # Update chapter statuses
        for chapter in chapters:
            await chapter_repository.mark_as_downloaded(chapter.id, str(chapter.url))
            await chapter_repository.mark_as_read(chapter.id)

        return StreamingResponse(
            io.BytesIO(epub_bytes),
            media_type="application/epub+zip",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error generating content: {str(e)}"
        )


@router.post("/{novel_id}/chapters/fetch", response_model=ChapterListResponse, tags=["chapters"])
async def fetch_chapters_from_source(
    novel_id: PyObjectId,
    chapter_repository: ChapterRepository = Depends(get_chapter_repository),
    novel_repository: NovelRepository = Depends(get_novel_repository),
):
    """Fetch and update chapters from the source website."""
    # Verify novel exists
    novel = await novel_repository.get_by_id(novel_id)
    if novel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Novel with id {novel_id} not found")

    try:
        # Fetch chapters from source
        new_chapters = await scrape_chapters_for_novel(str(novel.source_url), novel.source_name)

        if not new_chapters:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="No chapters found on the source website"
            )

        # Get existing chapters to preserve their states
        existing_chapters, total = await chapter_repository.get_by_novel_id(novel_id)
        existing_chapters_dict = {c.chapter_number: c for c in existing_chapters}

        # Create new chapters
        created_chapters = []
        for chapter in new_chapters:
            chapter_dict = {
                "novel_id": novel_id,
                "title": chapter.title,
                "chapter_number": chapter.chapter_number,
                "chapter_title": chapter.chapter_title,
                "url": str(chapter.url),
                "content_type": "novel" if novel.type == NovelType.NOVEL else "manhwa",
                "language": novel.source_language or "en",
            }

            # If chapter exists, preserve its state
            if chapter.chapter_number in existing_chapters_dict:
                existing_chapter = existing_chapters_dict[chapter.chapter_number]
                chapter_dict["read"] = existing_chapter.read
                chapter_dict["downloaded"] = existing_chapter.downloaded
                chapter_dict["local_path"] = existing_chapter.local_path

            created_chapter = await chapter_repository.create(ChapterCreate(**chapter_dict))
            created_chapters.append(created_chapter)

        # Update novel's last_updated_chapters
        await novel_repository.update(novel_id, NovelUpdate(last_updated_chapters=datetime.utcnow()))

        # Return the updated chapters
        return ChapterListResponse(
            chapters=created_chapters,
            total=len(created_chapters),
            page=1,
            page_size=len(created_chapters),
            total_pages=1,
        )

    except ScraperError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error scraping chapters: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Unexpected error: {str(e)}")


@router.post("/{novel_id}/chapters/{chapter_number}/progress", response_model=ReadingProgress, tags=["chapters"])
async def update_reading_progress(
    novel_id: PyObjectId,
    chapter_number: int,
    progress: float = Query(..., ge=0.0, le=1.0),
    current_user: UserInDB = Depends(get_current_user),
    chapter_repository: ChapterRepository = Depends(get_chapter_repository),
    reading_progress_repository: ReadingProgressRepository = Depends(get_reading_progress_repository),
):
    """Update reading progress for a chapter."""
    # Get the chapter
    chapter = await chapter_repository.get_by_number(novel_id, chapter_number)
    if not chapter:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Chapter {chapter_number} not found")

    # Create or update progress
    progress_data = ReadingProgressCreate(user_id=current_user.id, chapter_id=chapter.id, progress=progress)

    return await reading_progress_repository.create_or_update(progress_data)


@router.get(
    "/{novel_id}/chapters/{chapter_number}/progress", response_model=Optional[ReadingProgress], tags=["chapters"]
)
async def get_reading_progress(
    novel_id: PyObjectId,
    chapter_number: int,
    current_user: UserInDB = Depends(get_current_user),
    chapter_repository: ChapterRepository = Depends(get_chapter_repository),
    reading_progress_repository: ReadingProgressRepository = Depends(get_reading_progress_repository),
):
    """Get reading progress for a chapter."""
    # Get the chapter
    chapter = await chapter_repository.get_by_number(novel_id, chapter_number)
    if not chapter:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Chapter {chapter_number} not found")

    return await reading_progress_repository.get_progress(current_user.id, chapter.id)


@router.get("/{novel_id}/progress", response_model=List[ReadingProgress], tags=["chapters"])
async def get_novel_progress(
    novel_id: PyObjectId,
    current_user: UserInDB = Depends(get_current_user),
    reading_progress_repository: ReadingProgressRepository = Depends(get_reading_progress_repository),
):
    """Get all reading progress for a novel."""
    return await reading_progress_repository.get_user_progress(current_user.id, novel_id)
