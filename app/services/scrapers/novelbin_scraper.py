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

            soup = None
            playwright_error = None
            try:
                # Navigate to the page
                await self._page.goto(url + "#tab-chapters-title")
                await self._page.wait_for_selector(self.config.selectors["chapter_list"], timeout=50000)
                try:
                    await self._page.wait_for_selector(self.config.selectors["chapter_list"], timeout=50000)
                except Exception as e:
                    print(f"Error waiting for chapter list: {str(e)}")
                    await self._page.screenshot(path="selector_timeout.png")
                    content = await self._page.content()
                    print(f"Current page content length: {len(content)}")
                    print(f"Current URL: {self._page.url}")
                    elements = await self._page.query_selector_all("li")
                    print(f"Found {len(elements)} li elements on the page")
                    raise

                try:
                    await self._page.wait_for_selector(
                        "#chapter-archive > div:nth-child(2)", state="hidden", timeout=30000
                    )
                except Exception as e:
                    print(f"Loading div not found or timeout: {e}")

                content = await self._page.content()
                soup = BeautifulSoup(content, "html.parser")

            except Exception as e:
                playwright_error = e
                print(f"Error con Playwright: {e}. Intentando con ScraperAPI...")
                try:
                    import httpx
                    from app.core.config import settings

                    payload = {
                        "api_key": settings.SCRAPERAPI_KEY,
                        "url": f"{url}#tab-chapters-title",
                        "render": "true",
                        "wait_for_selector": ".list-chapter",
                        "timeout": "60000",  # 60 segundos de timeout
                    }

                    async with httpx.AsyncClient() as client:
                        response = await client.get("https://api.scraperapi.com/", params=payload, timeout=100000)
                        response.raise_for_status()
                        content = response.text

                        # Debug info
                        if len(content) < 1000:  # Si el contenido es muy pequeño, probablemente hay un error
                            print(f"Warning: Content length is very small ({len(content)} bytes)")
                            print(f"Response status: {response.status_code}")
                            print(f"Response headers: {response.headers}")
                            raise ValueError("Response content too small, might be an error page")

                    soup = BeautifulSoup(content, "html.parser")
                    print("novelbin scrapper (scraperapi)")
                except Exception as e2:
                    print(f"Error también con ScraperAPI: {e2}")
                    if playwright_error:
                        raise playwright_error
                    else:
                        raise e2

            chapters = []
            chapter_items = soup.select(self.config.selectors["chapter_list"]) if soup else []
            print(f"Total chapter items found: {len(chapter_items)}")

            # Validación de capítulos
            if not chapter_items:
                print("Warning: No chapters found in the response")
                print("Available selectors in the page:")
                for selector in soup.select("*[class]"):
                    print(f"- {selector.get('class')}")

            for item in chapter_items:
                link = item.select_one(self.config.selectors["chapter_link"])
                if not link:
                    continue

                chapter_url = link["href"]
                chapter_title = link.text.strip()

                try:
                    chapter_number = int(re.search(self.config.patterns["chapter_number"], chapter_title).group(1))
                except (AttributeError, ValueError):
                    chapter_number = len(chapters) + 1
                    print(f"Warning: Could not extract chapter number from title: {chapter_title}")

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

            chapters.sort(key=lambda x: x.chapter_number)
            print(f"Total chapters found: {len(chapters)}")

            # Validación final
            if len(chapters) < 30:
                print("Warning: Found less than 30 chapters, this might indicate a problem")
                print("First few chapter titles:")
                for chapter in chapters[:5]:
                    print(f"- {chapter.title}")

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
