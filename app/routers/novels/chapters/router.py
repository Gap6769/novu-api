from fastapi import Depends, HTTPException, status, Query, Path
from typing import List, Optional
from app.models.novel import NovelType, PyObjectId, NovelUpdate
from app.models.chapter import (
    ChapterCreate,
    ChapterListResponse,
    ChapterDownloadResponse,
    ReadingProgress,
    ReadingProgressCreate,
)
from app.db.database import get_database
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.services.utils.epub_service import epub_service
from app.services.core.scraper_service import scrape_chapters_for_novel, ScraperError, scrape_chapter_content
from fastapi.responses import StreamingResponse
import io
from datetime import datetime
from app.services.utils.translation_service import translation_service
from app.services.core.storage_service import storage_service
from app.repositories.chapter_repository import ChapterRepository
from app.repositories.novel_repository import NovelRepository
from app.repositories.reading_progress_repository import ReadingProgressRepository
from app.routers.auth.router import get_current_user
from app.models.user import UserInDB
from app.routers.base import BaseRouter


class ChaptersRouter(BaseRouter):
    def __init__(self):
        super().__init__(prefix="/{novel_id}/chapters", tags=["chapters"])
        self._setup_routes()

    def _setup_routes(self):
        @self.router.get("", response_model=ChapterListResponse)
        async def get_chapters(
            novel_id: PyObjectId = Path(...),
            page: int = Query(1, ge=1),
            page_size: int = Query(50, ge=1, le=100),
            sort_order: str = Query("desc", pattern="^(asc|desc)$"),
            chapter_repository: ChapterRepository = Depends(get_chapter_repository),
            novel_repository: NovelRepository = Depends(get_novel_repository),
        ):
            novel = await novel_repository.get_by_id(novel_id)
            if novel is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail=f"Novel with id {novel_id} not found"
                )

            skip = (page - 1) * page_size
            chapters, total_chapters = await chapter_repository.get_by_novel_id(
                novel_id, skip=skip, limit=page_size, sort_order=sort_order
            )

            total_pages = (total_chapters + page_size - 1) // page_size

            return ChapterListResponse(
                chapters=chapters, total=total_chapters, page=page, page_size=page_size, total_pages=total_pages
            )

        @self.router.get("/{chapter_number}")
        async def download_chapter(
            novel_id: PyObjectId = Path(...),
            chapter_number: int = Path(...),
            language: str = Query("en", pattern="^(en|es)$"),
            format: str = Query("epub", pattern="^(epub|raw)$"),
            chapter_repository: ChapterRepository = Depends(get_chapter_repository),
            novel_repository: NovelRepository = Depends(get_novel_repository),
        ):
            novel = await novel_repository.get_by_id(novel_id)
            if novel is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail=f"Novel with id {novel_id} not found"
                )

            chapter = await chapter_repository.get_by_number(novel_id, chapter_number)
            if not chapter:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail=f"Chapter {chapter_number} not found"
                )

            try:
                if novel.type == NovelType.MANHWA:
                    content = await scrape_chapter_content(
                        str(chapter.url), novel.source_name, str(novel_id), chapter_number
                    )
                    await chapter_repository.mark_as_downloaded(chapter.id, str(chapter.url))
                    await chapter_repository.mark_as_read(chapter.id)
                    return content

                if format == "epub":
                    epub_bytes, filename = await epub_service.create_epub(
                        novel_id=str(novel_id),
                        novel_title=novel.title,
                        author=novel.author or "Unknown",
                        chapters=[chapter],
                        source_name=novel.source_name,
                        single_chapter=chapter_number,
                        translate=(language == "es"),
                    )
                    await chapter_repository.mark_as_downloaded(chapter.id, str(chapter.url))
                    await chapter_repository.mark_as_read(chapter.id)
                    return StreamingResponse(
                        io.BytesIO(epub_bytes),
                        media_type="application/epub+zip",
                        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
                    )
                else:
                    cached_content = await storage_service.get_chapter(str(novel_id), chapter_number, "raw", language)
                    if cached_content:
                        cleaned_content = cached_content
                    else:
                        raw_content = await epub_service.fetch_chapter_content(
                            chapter_url=str(chapter.url),
                            source_name=novel.source_name,
                            novel_id=str(novel_id),
                            chapter_number=chapter_number,
                        )
                        cleaned_content = epub_service.clean_content(raw_content)

                        if language == "es" and novel.source_language == "en":
                            cleaned_content = await translation_service.translate_text(cleaned_content)

                        await storage_service.save_chapter(
                            str(novel_id), chapter_number, cleaned_content, "raw", language
                        )

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

        @self.router.post("/download", response_model=ChapterDownloadResponse)
        async def download_chapters(
            chapter_numbers: List[int],
            novel_id: PyObjectId = Path(...),
            language: str = Query("en", pattern="^(en|es)$"),
            chapter_repository: ChapterRepository = Depends(get_chapter_repository),
            novel_repository: NovelRepository = Depends(get_novel_repository),
        ):
            novel = await novel_repository.get_by_id(novel_id)
            if novel is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail=f"Novel with id {novel_id} not found"
                )

            chapters = []
            for chapter_number in chapter_numbers:
                chapter = await chapter_repository.get_by_number(novel_id, chapter_number)
                if chapter:
                    chapters.append(chapter)

            if not chapters:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No valid chapters found")

            try:
                if novel.type == NovelType.MANHWA:
                    chapters_content = []
                    for chapter in chapters:
                        content = await scrape_chapter_content(
                            str(chapter.url), novel.source_name, str(novel_id), chapter.chapter_number
                        )
                        chapters_content.append(
                            {"chapter_number": chapter.chapter_number, "title": chapter.title, "content": content}
                        )

                    for chapter in chapters:
                        await chapter_repository.mark_as_downloaded(chapter.id, str(chapter.url))
                        await chapter_repository.mark_as_read(chapter.id)

                    return {"type": "manhwa", "chapters": chapters_content}

                epub_bytes, filename = await epub_service.create_epub(
                    novel_id=str(novel_id),
                    novel_title=novel.title,
                    author=novel.author or "Unknown",
                    chapters=chapters,
                    source_name=novel.source_name,
                    translate=(language == "es"),
                )

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

        @self.router.post("/fetch", response_model=ChapterListResponse)
        async def fetch_chapters_from_source(
            novel_id: PyObjectId = Path(...),
            chapter_repository: ChapterRepository = Depends(get_chapter_repository),
            novel_repository: NovelRepository = Depends(get_novel_repository),
        ):
            novel = await novel_repository.get_by_id(novel_id)
            if novel is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail=f"Novel with id {novel_id} not found"
                )

            try:
                new_chapters = await scrape_chapters_for_novel(str(novel.source_url), novel.source_name)

                if not new_chapters:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND, detail="No chapters found on the source website"
                    )

                # Get existing chapters and create a set of (novel_id, chapter_number) tuples for quick lookup
                existing_chapters, total = await chapter_repository.get_by_novel_id(novel_id, limit=None)
                existing_chapters_set = {(c.novel_id, c.chapter_number) for c in existing_chapters}

                created_chapters = []
                for chapter in new_chapters:
                    # Check if chapter already exists using the set for O(1) lookup
                    if (novel_id, chapter.chapter_number) in existing_chapters_set:
                        continue

                    chapter_dict = {
                        "novel_id": novel_id,
                        "title": chapter.title,
                        "chapter_number": chapter.chapter_number,
                        "chapter_title": chapter.chapter_title,
                        "url": str(chapter.url),
                        "content_type": "novel" if novel.type == NovelType.NOVEL else "manhwa",
                        "language": novel.source_language or "en",
                    }

                    created_chapter = await chapter_repository.create(ChapterCreate(**chapter_dict))
                    created_chapters.append(created_chapter)

                await novel_repository.update(novel_id, NovelUpdate(last_updated_chapters=datetime.utcnow()))

                return ChapterListResponse(
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
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Unexpected error: {str(e)}"
                )

        @self.router.post("/{chapter_number}/progress", response_model=ReadingProgress)
        async def update_reading_progress(
            novel_id: PyObjectId = Path(...),
            chapter_number: int = Path(...),
            progress: float = Query(..., ge=0.0, le=1.0),
            current_user: UserInDB = Depends(get_current_user),
            chapter_repository: ChapterRepository = Depends(get_chapter_repository),
            reading_progress_repository: ReadingProgressRepository = Depends(get_reading_progress_repository),
        ):
            chapter = await chapter_repository.get_by_number(novel_id, chapter_number)
            if not chapter:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail=f"Chapter {chapter_number} not found"
                )

            progress_data = ReadingProgressCreate(user_id=current_user.id, chapter_id=chapter.id, progress=progress)

            return await reading_progress_repository.create_or_update(progress_data)

        @self.router.get("/{chapter_number}/progress", response_model=Optional[ReadingProgress])
        async def get_reading_progress(
            novel_id: PyObjectId = Path(...),
            chapter_number: int = Path(...),
            current_user: UserInDB = Depends(get_current_user),
            chapter_repository: ChapterRepository = Depends(get_chapter_repository),
            reading_progress_repository: ReadingProgressRepository = Depends(get_reading_progress_repository),
        ):
            chapter = await chapter_repository.get_by_number(novel_id, chapter_number)
            if not chapter:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail=f"Chapter {chapter_number} not found"
                )

            return await reading_progress_repository.get_progress(current_user.id, chapter.id)

        @self.router.get("/progress", response_model=List[ReadingProgress])
        async def get_novel_progress(
            novel_id: PyObjectId = Path(...),
            current_user: UserInDB = Depends(get_current_user),
            reading_progress_repository: ReadingProgressRepository = Depends(get_reading_progress_repository),
        ):
            return await reading_progress_repository.get_user_progress(current_user.id, novel_id)


def get_chapter_repository(db: AsyncIOMotorDatabase = Depends(get_database)) -> ChapterRepository:
    return ChapterRepository(db)


def get_novel_repository(db: AsyncIOMotorDatabase = Depends(get_database)) -> NovelRepository:
    return NovelRepository(db)


def get_reading_progress_repository(db: AsyncIOMotorDatabase = Depends(get_database)) -> ReadingProgressRepository:
    return ReadingProgressRepository(db)


router = ChaptersRouter().get_router()
