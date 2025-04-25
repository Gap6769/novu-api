from typing import List, Optional, Dict, Any
from pydantic import HttpUrl
from bs4 import BeautifulSoup
import re
from ..models.novel import Chapter
from .base_scraper import BaseScraper, ScraperConfig

class ManhwaScraper(BaseScraper):
    """Base class for manhwa scrapers."""
    
    def __init__(self, config: ScraperConfig):
        # Ensure content type is manhwa
        config.content_type = "manhwa"
        super().__init__(config)
    
    async def get_novel_info(self, url: str) -> Dict[str, Any]:
        """Get manhwa information from the source."""
        async with self:
            html = await self.fetch_html(url)
            soup = BeautifulSoup(html, 'html.parser')
            
            # Extract manhwa information using selectors from config
            title = self._extract_text(soup, self.config.selectors["title"])
            author = self._extract_text(soup, self.config.selectors["author"])
            description = self._extract_text(soup, self.config.selectors["description"])
            cover_image_url = self._extract_attribute(soup, self.config.selectors["cover_image"], "src")
            
            # Get status
            status_elem = soup.select_one(self.config.selectors["status"])
            status = "Ongoing" if status_elem and "ongoing" in status_elem.text.lower() else "Completed"
            
            # Get tags/genres
            tags = [tag.text.strip() for tag in soup.select(self.config.selectors["tags"])]
            
            return {
                'title': title,
                'author': author,
                'description': description,
                'cover_image_url': cover_image_url,
                'status': status,
                'tags': tags,
                'source_url': url,
                'source_name': self.config.name,
                'type': 'manhwa'
            }
    
    async def get_chapters(self, url: str, max_chapters: int = 50) -> List[Chapter]:
        """Get manhwa chapters from the source."""
        async with self:
            if self.config.use_playwright and self._page:
                await self._page.goto(url)
                await self._page.wait_for_selector(self.config.selectors["chapter_list"])
                await self._scroll_page_to_bottom(self._page)
                html = await self._page.content()
            else:
                html = await self.fetch_html(url)
            
            soup = BeautifulSoup(html, 'html.parser')
            
            chapters = []
            # Find all chapter list items
            chapter_items = soup.select(self.config.selectors["chapter_list"])
            print(f"Total chapter items found: {len(chapter_items)}")
            
            for item in chapter_items:
                link = item.select_one(self.config.selectors["chapter_link"])
                if not link:
                    continue
                    
                chapter_url = link['href']
                chapter_title = link.text.strip()
                
                # Extract chapter number from title
                try:
                    # Try to extract chapter number from title using pattern
                    chapter_number = int(re.search(self.config.patterns["chapter_number"], chapter_title).group(1))
                except (AttributeError, ValueError):
                    # Fallback if chapter number can't be extracted
                    chapter_number = len(chapters) + 1
                
                chapters.append(Chapter(
                    title=chapter_title,
                    chapter_number=chapter_number,
                    chapter_title=chapter_title,  # Store the full title
                    url=chapter_url,
                    read=False,
                    downloaded=False
                ))
            
            # Sort chapters by number and limit to max_chapters
            chapters.sort(key=lambda x: x.chapter_number)
            if max_chapters:
                chapters = chapters[:max_chapters]
            print(f"Total chapters found: {len(chapters)}")
            return chapters
    
    async def get_chapter_content(self, url: str) -> str:
        """Get the content of a specific chapter."""
        async with self:
            html = await self.fetch_html(url)
            soup = BeautifulSoup(html, 'html.parser')
            
            # Extract chapter content
            content_div = soup.select_one(self.config.selectors["chapter_content"])
            if not content_div:
                raise ValueError("Chapter content not found")
            
            # Clean up the content using base class method
            content = self._clean_content(
                str(content_div),
                additional_patterns=self.config.patterns.get("unwanted_text", [])
            )
            
            return content

class AsuraScansScraper(ManhwaScraper):
    """Scraper for Asura Scans website."""
    
    def __init__(self):
        config = ScraperConfig(
            name="asurascans",
            base_url="https://asurascans.com",
            content_type="manhwa",
            selectors={
                "title": ".entry-title",
                "author": ".author a",
                "description": ".entry-content",
                "cover_image": ".thumb img",
                "status": ".status",
                "tags": ".genres a",
                "chapter_list": ".eplister li",
                "chapter_link": "a",
                "chapter_content": ".entry-content",
                "unwanted_elements": [".ad-container", ".advertisement"]
            },
            patterns={
                "chapter_number": r"Chapter\s+(\d+)",
                "unwanted_text": [
                    r"Please support the translation team and read this chapter on our website.*",
                    r"Join our Discord for updates.*",
                    r"Please read this chapter on our website.*"
                ]
            },
            use_playwright=True  # Asura Scans requires JavaScript for chapter list
        )
        super().__init__(config) 