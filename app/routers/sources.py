from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any
from ..models.source import SourceInDB, SourceCreate, SourceUpdate, ContentType
from ..services.scraper_service import SCRAPER_REGISTRY, get_scraper_for_source, ScraperError
from ..services.base_scraper import ScraperConfig
from ..services.generic_scraper import GenericScraper
from ..repositories.source_repository import SourceRepository
from ..db.database import get_database
from motor.motor_asyncio import AsyncIOMotorDatabase
import datetime
import uuid

router = APIRouter(tags=["sources"])

async def get_source_repository(db: AsyncIOMotorDatabase = Depends(get_database)) -> SourceRepository:
    return SourceRepository(db)

@router.get("/", response_model=List[SourceInDB])
async def list_sources(source_repository: SourceRepository = Depends(get_source_repository)):
    """List all available sources."""
    # Get sources from database
    db_sources = await source_repository.get_all()
    
    # Convert built-in scrapers to sources
    built_in_sources = []
    for name, scraper_class in SCRAPER_REGISTRY.items():
        try:
            # Try to create the scraper with default config
            scraper = scraper_class()
            # Convert selectors to strings if they are lists
            selectors = {}
            for key, value in scraper.config.selectors.items():
                if isinstance(value, list):
                    selectors[key] = ", ".join(value)
                else:
                    selectors[key] = value

            source = SourceCreate(
                name=name,
                base_url=scraper.config.base_url,
                content_type=ContentType.NOVEL if scraper.config.content_type == "novel" else ContentType.MANHWA,
                selectors=selectors,
                patterns=scraper.config.patterns,
                use_playwright=scraper.config.use_playwright,
                headers=scraper.config.headers,
                timeout=scraper.config.timeout,
                max_retries=scraper.config.max_retries,
                special_actions=scraper.config.special_actions
            )
            built_in_sources.append(source)
        except Exception as e:
            print(f"Error creating source for {name}: {str(e)}")
            continue
    
    return db_sources

@router.post("/", response_model=SourceInDB)
async def create_source(
    source: SourceCreate,
    source_repository: SourceRepository = Depends(get_source_repository)
):
    """Create a new source."""
    # Check if source with same name exists
    existing = await source_repository.get_by_name(source.name)
    if existing:
        raise HTTPException(status_code=400, detail="Source with this name already exists")
    
    # Validate the source configuration by trying to create a scraper
    try:
        config = ScraperConfig(
            name=source.name,
            base_url=source.base_url,
            content_type=source.content_type.value,
            selectors=source.selectors,
            patterns=source.patterns,
            use_playwright=source.use_playwright,
            headers=source.headers,
            timeout=source.timeout,
            max_retries=source.max_retries,
            special_actions=source.special_actions
        )
        scraper = GenericScraper(
            name=config.name,
            base_url=config.base_url,
            content_type=config.content_type,
            selectors=config.selectors,
            patterns=config.patterns,
            use_playwright=config.use_playwright,
            headers=config.headers,
            timeout=config.timeout,
            max_retries=config.max_retries,
            special_actions=config.special_actions
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid source configuration: {str(e)}")
    
    return await source_repository.create(source)

@router.get("/{source_id}", response_model=SourceInDB)
async def get_source(
    source_id: str,
    source_repository: SourceRepository = Depends(get_source_repository)
):
    """Get a specific source by ID."""
    source = await source_repository.get_by_id(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    return source

@router.put("/{source_id}", response_model=SourceInDB)
async def update_source(
    source_id: str,
    source: SourceUpdate,
    source_repository: SourceRepository = Depends(get_source_repository)
):
    """Update a source."""
    updated_source = await source_repository.update(source_id, source)
    if not updated_source:
        raise HTTPException(status_code=404, detail="Source not found")
    return updated_source

@router.delete("/{source_id}")
async def delete_source(
    source_id: str,
    source_repository: SourceRepository = Depends(get_source_repository)
):
    """Delete a source."""
    success = await source_repository.delete(source_id)
    if not success:
        raise HTTPException(status_code=404, detail="Source not found")
    return {"message": "Source deleted successfully"}

@router.post("/{source_id}/test")
async def test_source(
    source_id: str,
    url: str,
    source_repository: SourceRepository = Depends(get_source_repository)
):
    """Test a source configuration by attempting to scrape a URL."""
    try:
        if source_id.startswith("builtin_"):
            name = source_id.replace("builtin_", "")
            scraper = get_scraper_for_source(name)
        else:
            source = await source_repository.get_by_id(source_id)
            if not source:
                raise HTTPException(status_code=404, detail="Source not found")
            
            config = ScraperConfig(
                name=source.name,
                base_url=source.base_url,
                content_type=source.content_type.value,
                selectors=source.selectors,
                patterns=source.patterns,
                use_playwright=source.use_playwright,
                headers=source.headers,
                timeout=source.timeout,
                max_retries=source.max_retries,
                special_actions=source.special_actions
            )
            scraper = GenericScraper(
                name=config.name,
                base_url=config.base_url,
                content_type=config.content_type,
                selectors=config.selectors,
                patterns=config.patterns,
                use_playwright=config.use_playwright,
                headers=config.headers,
                timeout=config.timeout,
                max_retries=config.max_retries,
                special_actions=config.special_actions
            )
        
        # Try to get novel info to test the configuration
        novel_info = await scraper.get_novel_info(url)
        return {"success": True, "novel_info": novel_info}
    except ScraperError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error testing source: {str(e)}")

@router.post("/seed", response_model=List[SourceInDB])
async def seed_sources(source_repository: SourceRepository = Depends(get_source_repository)):
    """Seed the database with built-in sources."""
    sources_to_seed = []
    
    for name, scraper_class in SCRAPER_REGISTRY.items():
        try:
            scraper = scraper_class()
            # Convert selectors to strings if they are lists
            selectors = {}
            for key, value in scraper.config.selectors.items():
                if isinstance(value, list):
                    selectors[key] = ", ".join(value)
                else:
                    selectors[key] = value

            source = SourceCreate(
                name=name,
                base_url=scraper.config.base_url,
                content_type=ContentType.NOVEL if scraper.config.content_type == "novel" else ContentType.MANHWA,
                selectors=selectors,
                patterns=scraper.config.patterns,
                use_playwright=scraper.config.use_playwright,
                headers=scraper.config.headers,
                timeout=scraper.config.timeout,
                max_retries=scraper.config.max_retries,
                special_actions=scraper.config.special_actions
            )
            sources_to_seed.append(source)
        except Exception as e:
            print(f"Error creating source for {name}: {str(e)}")
            continue
    
    return await source_repository.seed_sources(sources_to_seed) 