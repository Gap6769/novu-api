from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from ..models.novel import NovelCreate, NovelPublic, NovelUpdate, PyObjectId, NovelSummary, NovelDetail, ChapterDownloadResponse, NovelType
from ..db.database import get_database
from ..services.scraper_service import scrape_novel_info, ScraperError
from motor.motor_asyncio import AsyncIOMotorDatabase
from ..repositories.novel_repository import NovelRepository

router = APIRouter()

def get_novel_repository(db: AsyncIOMotorDatabase = Depends(get_database)) -> NovelRepository:
    return NovelRepository(db)

@router.post(
    "/", 
    response_model=NovelPublic, 
    status_code=status.HTTP_201_CREATED,
    tags=["novels"]
)
async def create_novel(
    novel_in: NovelCreate,
    novel_repository: NovelRepository = Depends(get_novel_repository)
):
    """Adds a new novel to the library."""
    # Check if novel with the same source_url already exists
    if await novel_repository.exists_by_source_url(str(novel_in.source_url)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, 
            detail=f"Novel from source URL {novel_in.source_url} already exists."
        )
    
    # Scrape novel info if not provided
    if not novel_in.title or not novel_in.description:
        try:
            novel_info = await scrape_novel_info(str(novel_in.source_url), novel_in.source_name)
            novel_in.title = novel_info['title']
            novel_in.description = novel_info['description']
            novel_in.cover_image_url = novel_info['cover_image_url']
            novel_in.tags = novel_info['tags']
            novel_in.status = novel_info['status']
        except ScraperError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to scrape novel info: {str(e)}"
            )
    
    created_novel = await novel_repository.create(novel_in)
    return NovelPublic(**created_novel.model_dump())

@router.get("/", response_model=List[NovelSummary], tags=["novels"])
async def get_novels(
    novel_repository: NovelRepository = Depends(get_novel_repository),
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(100, ge=1, le=100, description="Number of items to return"),
    type: Optional[NovelType] = Query(None, description="Filter by novel type"),
    status: Optional[str] = Query(None, description="Filter by novel status"),
    source_name: Optional[str] = Query(None, description="Filter by source name"),
    search: Optional[str] = Query(None, description="Search in title and description")
):
    """Retrieves a list of novels with filtering options."""
    query = {}
    
    if type:
        query["type"] = type
    if status:
        query["status"] = status
    if source_name:
        query["source_name"] = source_name
    if search:
        query["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"description": {"$regex": search, "$options": "i"}}
        ]
    
    return await novel_repository.filter(query, skip=skip, limit=limit)

@router.get("/{novel_id}", response_model=NovelDetail, tags=["novels"])
async def get_novel_by_id(
    novel_id: PyObjectId,
    novel_repository: NovelRepository = Depends(get_novel_repository)
):
    """Retrieves a specific novel by its ID with detailed information."""
    novel = await novel_repository.get_by_id(novel_id)
    if novel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Novel with id {novel_id} not found")
    return novel

@router.patch("/{novel_id}", response_model=NovelDetail, tags=["novels"])
async def update_novel(
    novel_id: PyObjectId,
    novel_update: NovelUpdate,
    novel_repository: NovelRepository = Depends(get_novel_repository)
):
    """Updates an existing novel."""
    updated_novel = await novel_repository.update(novel_id, novel_update)
    if updated_novel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Novel with id {novel_id} not found")
    return updated_novel

@router.delete("/{novel_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["novels"])
async def delete_novel(
    novel_id: PyObjectId,
    novel_repository: NovelRepository = Depends(get_novel_repository)
):
    """Deletes a novel from the library."""
    success = await novel_repository.delete(novel_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Novel with id {novel_id} not found")
    return

@router.patch("/{novel_id}/reading-progress", response_model=NovelDetail, tags=["novels"])
async def update_reading_progress(
    novel_id: PyObjectId,
    current_chapter: int = Query(..., description="The current chapter number being read"),
    novel_repository: NovelRepository = Depends(get_novel_repository)
):
    """Update the reading progress of a novel by marking chapters as read and downloaded up to the current chapter."""
    updated_novel = await novel_repository.update_reading_progress(novel_id, current_chapter)
    if updated_novel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Novel with id {novel_id} not found")
    return updated_novel

@router.post("/{novel_id}/metadata", response_model=NovelDetail, tags=["novels"])
async def update_metadata(
    novel_id: PyObjectId,
    novel_repository: NovelRepository = Depends(get_novel_repository)
):
    """Update the metadata of a novel by scraping it from the source website."""
    # Find the novel to get source information
    novel = await novel_repository.get_by_id(novel_id)
    if novel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Novel with id {novel_id} not found")
    
    try:
        # Scrape novel info from source
        novel_info = await scrape_novel_info(str(novel.source_url), novel.source_name)
        
        # Update novel with new metadata
        updated_novel = await novel_repository.update_metadata(novel_id, novel_info)
        if updated_novel is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Novel with id {novel_id} not found")
        return updated_novel
        
    except ScraperError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to scrape novel info: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {str(e)}"
        ) 