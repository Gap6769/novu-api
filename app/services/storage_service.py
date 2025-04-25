import os
import json
import aiohttp
import aiofiles
from typing import Optional, Union, Dict, Any, List
from pathlib import Path
from ..models.novel import NovelType
from ..db.database import get_database
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId


class StorageService:
    def __init__(self):
        self.base_dir = Path("storage")
        self.novels_dir = self.base_dir / "novels"
        self._ensure_directories()
        self.db = None
    
    def _ensure_directories(self):
        """Ensure all necessary directories exist."""
        self.novels_dir.mkdir(parents=True, exist_ok=True)
    
    async def _get_novel_info(self, novel: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Get novel information from database if only ID is provided."""
        if isinstance(novel, dict):
            return novel
            
        if self.db is None:
            self.db = get_database()
            
        try:
            novel_id = ObjectId(novel)
            novel_doc = await self.db["novels"].find_one({"_id": novel_id})
            if not novel_doc:
                raise ValueError(f"Novel with id {novel} not found")
            return novel_doc
        except Exception as e:
            raise ValueError(f"Invalid novel ID format: {novel}")
    
    async def _get_chapter_path(self, novel: Union[str, Dict[str, Any]], chapter_number: int, content_type: str, language: str = "en") -> Path:
        """Get the path for a specific chapter."""
        novel_info = await self._get_novel_info(novel)
        novel_id = novel_info["_id"]
        novel_title = novel_info["title"]
        novel_dir = self.novels_dir / f"{novel_title} - {str(novel_id)}/chapters"
        
        novel_dir.mkdir(exist_ok=True, parents=True)
        base_path = novel_dir / f"chapter_{chapter_number}_{content_type}_{language}"
        
        # Add the correct extension based on content type
        if content_type == "epub":
            return base_path.with_suffix(".epub")
        elif content_type == "raw":
            return base_path.with_suffix(".txt")
        elif content_type == "manhwa":
            return base_path.with_suffix(".json")
        return base_path
    
    async def _get_manhwa_images_dir(self, novel: Union[str, Dict[str, Any]], chapter_number: int) -> Path:
        """Get the directory for manhwa chapter images."""
        novel_info = await self._get_novel_info(novel)
        novel_id = novel_info["_id"]
        novel_title = novel_info["title"]
        images_dir = self.novels_dir / f"{novel_title} - {str(novel_id)}/chapters/chapter_{chapter_number}_images"
        images_dir.mkdir(exist_ok=True, parents=True)
        return images_dir
    
    async def save_chapter(self, novel: str, chapter_number: int, content: Union[bytes, str, Dict[str, Any]], content_type: str, language: str = "en") -> None:
        """Save a chapter to storage."""
        if content_type == "manhwa":
            await self.save_manhwa_chapter(novel, chapter_number, content)
            return
            
        path = await self._get_chapter_path(novel, chapter_number, content_type, language)
        
        if content_type == "epub":
            with open(path, "wb") as f:
                f.write(content)
        elif content_type == "raw":
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
        elif content_type == "manhwa":
            with open(path, "w", encoding="utf-8") as f:
                json.dump(content, f, ensure_ascii=False, indent=2)
    
    async def get_chapter(self, novel: str, chapter_number: int, content_type: str, language: str = "en") -> Optional[Union[bytes, str, Dict[str, Any]]]:
        """Retrieve a chapter from storage."""
        path = await self._get_chapter_path(novel, chapter_number, content_type, language)
        
        
        if not path.exists():
            return None
            
        if content_type == "epub":
            with open(path.with_suffix(".epub"), "rb") as f:
                return f.read()
        elif content_type == "raw":
            with open(path.with_suffix(".txt"), "r", encoding="utf-8") as f:
                return f.read()
        elif content_type == "manhwa":
            with open(path.with_suffix(".json"), "r", encoding="utf-8") as f:
                return json.load(f)
        
        return None
    
    async def chapter_exists(self, novel: str, chapter_number: int, content_type: str, language: str = "en") -> bool:
        """Check if a chapter exists in storage."""
        path = await self._get_chapter_path(novel, chapter_number, content_type, language)
        return path.exists()
    
    async def save_manhwa_chapter(self, novel: Union[str, Dict[str, Any]], chapter_number: int, content: Dict[str, Any]) -> None:
        """Save a manhwa chapter with its images."""
        # Save images
        images_dir = await self._get_manhwa_images_dir(novel, chapter_number)
        saved_images = []
        
        async with aiohttp.ClientSession() as session:
            for img in content["images"]:
                try:
                    # Download image
                    async with session.get(img["url"]) as response:
                        if response.status == 200:
                            # Generate safe filename
                            ext = os.path.splitext(img["url"])[1] or ".jpg"
                            filename = f"image_{img['index']:03d}{ext}"
                            filepath = images_dir / filename
                            
                            # Save image
                            async with aiofiles.open(filepath, 'wb') as f:
                                await f.write(await response.read())
                            
                            # Update image info with local path
                            saved_img = img.copy()
                            saved_img["local_path"] = str(filepath)
                            saved_images.append(saved_img)
                except Exception as e:
                    print(f"Error downloading image {img['url']}: {str(e)}")
                    # Keep original image info if download fails
                    saved_images.append(img)
        
        # Update content with local paths
        content["images"] = saved_images
        
        # Save metadata
        path = await self._get_chapter_path(novel, chapter_number, "manhwa")
        async with aiofiles.open(path, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(content, ensure_ascii=False, indent=2))
    
    async def get_manhwa_chapter(self, novel: Union[str, Dict[str, Any]], chapter_number: int) -> Optional[Dict[str, Any]]:
        """Retrieve a manhwa chapter with its images."""
        path = await self._get_chapter_path(novel, chapter_number, "manhwa")
        
        if not path.exists():
            return None
            
        async with aiofiles.open(path, 'r', encoding='utf-8') as f:
            content = json.loads(await f.read())
            
        # Prioritize local images
        for img in content["images"]:
            if "local_path" in img:
                local_path = Path(img["local_path"])
                if local_path.exists():
                    # Use local path as primary source
                    img["url"] = str(local_path)
                else:
                    # If local image is missing, remove the local_path
                    img.pop("local_path", None)
        
        return content

storage_service = StorageService() 