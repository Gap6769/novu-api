from typing import List, Dict, Optional, Any, Union
from bs4 import BeautifulSoup
import re
from app.models.novel import Chapter
from ..core.base_scraper import BaseScraper, ScraperConfig
import asyncio


class GenericScraper(BaseScraper):
    """A generic scraper that can be configured for different sources."""

    def __init__(
        self,
        name: str,
        base_url: str,
        content_type: str = "novel",
        selectors: Optional[Dict[str, str]] = None,
        patterns: Optional[Dict[str, Union[str, List[str]]]] = None,
        use_playwright: bool = False,
        headers: Optional[Dict[str, str]] = None,
        timeout: float = 10.0,
        max_retries: int = 3,
        special_actions: Optional[Dict[str, Dict[str, Any]]] = None,
    ):
        # Default selectors for novels
        default_selectors = {
            "title": "h1",
            "author": ".author",
            "description": ".description",
            "cover_image": ".cover img",
            "status": ".status",
            "tags": ".tags a",
            "chapter_list": ".chapter-list",
            "chapter_link": "a",
            "chapter_content": ".chapter-content",
            "chapter_images": ".chapter-content img",
            "view_all_button": None,  # Selector for "view all" button
            "chapter_container": None,  # Selector for chapter container
            "chapter_item": None,  # Selector for individual chapter items
            "chapter_title": None,  # Selector for chapter title
            "chapter_url": None,  # Selector for chapter URL
        }

        # Default patterns for content cleaning
        default_patterns = {
            "chapter_number": r"Chapter\s+(\d+(?:\.\d+)?)",
            "unwanted_text": [r"Please\s+read\s+at\s+.*", r"Translator:.*", r"Editor:.*", r"Proofreader:.*"],
        }

        # Default special actions
        default_special_actions = {
            "view_all": {
                "enabled": False,
                "selector": None,
                "wait_after_click": 0,  # Seconds to wait after clicking
                "scroll_after_click": False,  # Whether to scroll after clicking
            }
        }

        # Update defaults with custom selectors and patterns
        if selectors:
            default_selectors.update(selectors)
        if patterns:
            default_patterns.update(patterns)
        if special_actions:
            default_special_actions.update(special_actions)

        config = ScraperConfig(
            name=name,
            base_url=base_url,
            content_type=content_type,
            selectors=default_selectors,
            patterns=default_patterns,
            use_playwright=use_playwright,
            headers=headers,
            timeout=timeout,
            max_retries=max_retries,
            special_actions=default_special_actions,
        )

        super().__init__(config)

    async def get_novel_info(self, url: str) -> Dict[str, Any]:
        """Get novel information from the source."""
        html = await self.fetch_html(url)
        soup = BeautifulSoup(html, "html.parser")

        info = {}

        # Extract title
        title_elem = self._find_first_matching(soup, self.config.selectors["title"])
        info["title"] = title_elem.get_text().strip() if title_elem else None

        # Extract author
        author_elem = self._find_first_matching(soup, self.config.selectors["author"])
        info["author"] = author_elem.get_text().strip() if author_elem else None

        # Extract description
        desc_elem = self._find_first_matching(soup, self.config.selectors["description"])
        info["description"] = desc_elem.get_text().strip() if desc_elem else None

        # Extract cover image
        cover_elem = self._find_first_matching(soup, self.config.selectors["cover_image"])
        info["cover_image_url"] = self._get_attribute(cover_elem, "src") if cover_elem else None

        # Extract status
        status_elem = self._find_first_matching(soup, self.config.selectors["status"])
        info["status"] = status_elem.get_text().strip() if status_elem else None

        # Extract tags
        tag_elems = soup.select(self.config.selectors["tags"])
        info["tags"] = [tag.get_text().strip() for tag in tag_elems]

        return info

    async def get_chapters(self, url: str, max_chapters: int = 50) -> List[Chapter]:
        """Get all chapters from the source."""
        async with self:
            if self.config.use_playwright and self._page:
                await self._page.goto(url)

                # Handle special actions like "view all" button
                if self.config.special_actions["view_all"]["enabled"]:
                    view_all_selector = self.config.special_actions["view_all"]["selector"]
                    if view_all_selector:
                        try:
                            await self._page.wait_for_selector(view_all_selector)
                            await self._page.click(view_all_selector)

                            # Wait after clicking if specified
                            wait_time = self.config.special_actions["view_all"]["wait_after_click"]
                            if wait_time > 0:
                                await asyncio.sleep(wait_time)

                            # Scroll after clicking if specified
                            if self.config.special_actions["view_all"]["scroll_after_click"]:
                                await self._scroll_page_to_bottom(self._page)
                        except Exception as e:
                            print(f"Error handling view all button: {e}")

                # Get the page content
                content = await self._page.content()
            else:
                content = await self.fetch_html(url)

            soup = BeautifulSoup(content, "html.parser")
            chapters = []

            # Use custom selectors if provided
            chapter_container = soup.select_one(
                self.config.selectors["chapter_container"] or self.config.selectors["chapter_list"]
            )
            if not chapter_container:
                return chapters

            chapter_items = chapter_container.select(
                self.config.selectors["chapter_item"] or self.config.selectors["chapter_link"]
            )

            for item in chapter_items:
                # Use custom selectors for title and URL if provided
                title_selector = self.config.selectors["chapter_title"] or "a"
                url_selector = self.config.selectors["chapter_url"] or "a"

                title_elem = item.select_one(title_selector)
                url_elem = item.select_one(url_selector)

                if not title_elem or not url_elem:
                    continue

                chapter_url = self.resolve_url(url_elem.get("href"))
                chapter_title = title_elem.get_text().strip()

                # Try to extract chapter number from title
                chapter_number = self._extract_chapter_number(chapter_title)

                chapters.append(
                    Chapter(
                        title=chapter_title,
                        chapter_number=chapter_number or len(chapters) + 1,
                        chapter_title=chapter_title,
                        url=chapter_url,
                        read=False,
                        downloaded=False,
                    )
                )

            # Sort chapters by number and limit to max_chapters
            chapters.sort(key=lambda x: x.chapter_number)
            if max_chapters:
                chapters = chapters[:max_chapters]

            return chapters

    async def get_chapter_content(self, url: str) -> str:
        """Get the content of a specific chapter."""
        html = await self.fetch_html(url)
        soup = BeautifulSoup(html, "html.parser")

        content_elem = soup.select_one(self.config.selectors["chapter_content"])
        if not content_elem:
            return ""

        # Clean the content
        content = self.clean_content(str(content_elem))

        return content

    def _find_first_matching(self, soup: BeautifulSoup, selector: str) -> Optional[Any]:
        """Find the first element matching any of the selectors."""
        if not selector:
            return None

        # Try CSS selector first
        elem = soup.select_one(selector)
        if elem:
            return elem

        # Try XPath if selector starts with //
        if selector.startswith("//"):
            try:
                from lxml import etree

                tree = etree.HTML(str(soup))
                elems = tree.xpath(selector)
                if elems:
                    return elems[0]
            except ImportError:
                pass

        return None

    def _get_attribute(self, elem: Any, attr: str) -> Optional[str]:
        """Get an attribute from an element, handling both BeautifulSoup and lxml elements."""
        if hasattr(elem, "get"):
            return elem.get(attr)
        elif hasattr(elem, "attrib"):
            return elem.attrib.get(attr)
        return None

    def _extract_chapter_number(self, title: str) -> Optional[float]:
        """Extract chapter number from title using configured pattern."""
        if not title or not self.config.patterns.get("chapter_number"):
            return None

        match = re.search(self.config.patterns["chapter_number"], title)
        if match:
            try:
                return float(match.group(1))
            except (ValueError, IndexError):
                pass

        return None
