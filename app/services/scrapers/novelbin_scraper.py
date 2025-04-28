from bs4 import BeautifulSoup
from typing import List, Dict, Any
from app.models.novel import Chapter
import re
from ..core.base_scraper import BaseScraper, ScraperConfig


class NovelBinScraper(BaseScraper):
    BASE_URL = "https://novelbin.com"

    def __init__(self):
        config = ScraperConfig(
            name="novelbin",
            base_url=self.BASE_URL,
            content_type="novel",
            selectors={
                "title": "a.novel-title",
                "author": ".author span",
                "description": ".desc-text",
                "cover_image": ".book-img img",
                "status": ".status",
                "tags": ".categories a",
                "chapter_list": ".list-chapter li",
                "chapter_link": "a",
                "chapter_content": "#chr-content",
                "unlock_buttons": ".unlock-buttons",
            },
            patterns={
                "chapter_number": r"Chapter\s+(\d+)",
                "unwanted_text": [
                    r"Enhance your reading experience by removing ads.*",
                    r"This material may be protected by copyright.*",
                    r"Excerpt From.*",
                    r"Remove Ads From.*",
                ],
            },
            use_playwright=True,  # NovelBin requires JavaScript for chapter list
        )
        super().__init__(config)

    async def get_novel_info(self, url: str) -> Dict[str, Any]:
        """Get novel information from NovelBin."""
        async with self:
            html = await self.fetch_html(url + "#tab-chapters-title")
            soup = BeautifulSoup(html, "html.parser")

            # Extract novel information using selectors from config
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
                "title": title,
                "author": author,
                "description": description,
                "cover_image_url": cover_image_url,
                "status": status,
                "tags": tags,
                "source_url": url,
                "source_name": "NovelBin",
            }

    async def get_chapters(self, url: str, max_chapters: int = 50) -> List[Chapter]:
        """Get novel chapters from NovelBin."""
        async with self:
            if not self._page:
                raise RuntimeError("Playwright page not initialized")

            # Navigate to the page
            await self._page.goto(url + "#tab-chapters-title")

            # Wait for the chapter list to load
            await self._page.wait_for_selector(self.config.selectors["chapter_list"])

            # Wait for loading div to disappear
            try:
                await self._page.wait_for_selector(
                    "#chapter-archive > div:nth-child(2)", state="hidden", timeout=30000
                )
            except Exception as e:
                print(f"Loading div not found or timeout: {e}")

            # Get the page content after loading is complete
            content = await self._page.content()
            soup = BeautifulSoup(content, "html.parser")

            print("novelbin scrapper")

            chapters = []
            # Find all chapter list items
            chapter_items = soup.select(self.config.selectors["chapter_list"])
            print(f"Total chapter items found: {len(chapter_items)}")

            for item in chapter_items:
                link = item.select_one(self.config.selectors["chapter_link"])
                if not link:
                    continue

                chapter_url = link["href"]
                chapter_title = link.text.strip()

                # Extract chapter number from title
                try:
                    # Try to extract chapter number from title using pattern
                    chapter_number = int(re.search(self.config.patterns["chapter_number"], chapter_title).group(1))
                except (AttributeError, ValueError):
                    # Fallback if chapter number can't be extracted
                    chapter_number = len(chapters) + 1

                chapters.append(
                    Chapter(
                        title=chapter_title,
                        chapter_number=chapter_number,
                        chapter_title=chapter_title,  # Store the full title
                        url=chapter_url,
                        read=False,
                        downloaded=False,
                    )
                )

            # Sort chapters by number and limit to max_chapters
            chapters.sort(key=lambda x: x.chapter_number)
            print(f"Total chapters found: {len(chapters)}")
            return chapters

    async def get_chapter_content(self, url: str, *args, **kwargs) -> str:
        """Get the content of a specific chapter."""
        async with self:
            html = await self.fetch_html(url)
            soup = BeautifulSoup(html, "html.parser")

            # Extract chapter content
            content_div = soup.select_one(self.config.selectors["chapter_content"])
            if not content_div:
                raise ValueError("Chapter content not found")

            # Clean up the content using base class method
            content = self._clean_content(
                str(content_div), additional_patterns=self.config.patterns.get("unwanted_text", [])
            )

            return content
