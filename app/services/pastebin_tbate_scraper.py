import re
import time
from typing import List, Optional, Tuple, Dict, Any
from pydantic import HttpUrl
from ..models.novel import Chapter
from .base_scraper import BaseScraper, ScraperConfig
from .storage_service import storage_service


class PastebinTBATEScraper(BaseScraper):
    """Scraper for TBATE chapters from Pastebin."""

    def __init__(self):
        config = ScraperConfig(
            name="pastebin_tbate",
            base_url="https://pastebin.com",
            content_type="novel",
            selectors={},  # Pastebin doesn't use HTML selectors
            patterns={
                "chapter_number": r"Capítulo\s+(\d+)",
                "next_chapter": r"Capítulo\s+\d+:\s+(https?://pastebin\.com/\w+)",
                "unwanted_text": [
                    r"Capítulo\s+\d+:\s+\d{2}/\d{2}/\d{4}.*",
                    r"Please support the translation team.*",
                    r"Join our Discord for updates.*",
                ],
            },
            use_playwright=False,
        )
        super().__init__(config)
        self.timeout = 15.0  # 15-second timeout for requests

    def _convert_to_raw_url(self, url: str) -> str:
        """Convert a Pastebin URL to its raw version."""
        if "/raw/" in url:
            return url
        parts = url.split("pastebin.com/")
        if len(parts) == 2 and parts[1]:
            return f"https://pastebin.com/raw/{parts[1]}"
        return url

    async def get_chapters(self, source_url: str, max_chapters: int = 50) -> List[Chapter]:
        """
        Get chapters from a Pastebin TBATE source.

        Args:
            source_url: The URL of the Pastebin page
            max_chapters: Maximum number of chapters to fetch

        Returns:
            List of Chapter objects
        """
        start_time = time.time()
        print(f"Starting scrape operation for TBATE from {source_url}")

        try:
            async with self:
                # Convert to raw URL and get content
                raw_url = self._convert_to_raw_url(source_url)
                print(f"Using raw URL: {raw_url}")
                content = await self.fetch_html(raw_url)
                if not content:
                    raise Exception("Failed to fetch content from Pastebin")

                # Parse the content
                chapters, next_url = self.parse_chapters(content, source_url)
                all_chapters = list(chapters)

                # Follow next URLs if available and within limits
                while next_url and len(all_chapters) < max_chapters:
                    print(f"Following next chapter link: {next_url}")
                    try:
                        raw_url = self._convert_to_raw_url(next_url)
                        print(f"Using raw URL: {raw_url}")
                        content = await self.fetch_html(raw_url)
                        if not content:
                            break

                        chapters, next_url = self.parse_chapters(content, next_url)
                        all_chapters.extend(chapters)

                        if len(all_chapters) >= max_chapters:
                            print(f"Reached maximum chapter limit ({max_chapters}), stopping")
                            all_chapters = all_chapters[:max_chapters]
                            break
                    except Exception as e:
                        print(f"Error following next link {next_url}: {e}")
                        break

                elapsed = time.time() - start_time
                print(f"Scrape operation completed in {elapsed:.2f} seconds, found {len(all_chapters)} chapters")

                return all_chapters
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"Error during scrape operation after {elapsed:.2f} seconds: {e}")
            raise

    def parse_chapters(self, raw_text_content: str, chapter_url: str) -> Tuple[List[Chapter], Optional[str]]:
        """
        Parse chapters from raw Pastebin content.

        Args:
            raw_text_content: The raw text content from Pastebin
            chapter_url: The URL of the current chapter

        Returns:
            Tuple of (list of chapters, URL to next chapter or None)
        """
        start_time = time.time()
        print(f"Starting to parse content from {chapter_url}, content length: {len(raw_text_content)} chars")

        # Set a reasonable limit for content size
        if len(raw_text_content) > 500_000:  # 500KB limit
            print(f"Content too large ({len(raw_text_content)} chars), truncating to first 500K chars")
            raw_text_content = raw_text_content[:500_000]

        chapters = []
        current_chapter_title = None
        current_chapter_number = None
        next_chapter_url = None

        # Split content into lines
        lines = raw_text_content.split("\n")

        # Find chapter number and title
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue

            # Look for chapter number (should be alone on a line)
            if line.isdigit():
                current_chapter_number = int(line)
                # Title is usually on the next line
                if i + 1 < len(lines):
                    current_chapter_title = lines[i + 1].strip()
                break

        if not current_chapter_number:
            # Fallback if we can't find the number
            print("Could not parse chapter number from content start.")
            current_chapter_number = int(re.search(r"\d+", chapter_url.split("/")[-1]).group())
            current_chapter_title = f"Capítulo {current_chapter_number}"

        # Create Chapter object for current page
        try:
            validated_url = HttpUrl(chapter_url)
            chapters.append(
                Chapter(
                    title=f"Capítulo {current_chapter_number}",
                    chapter_number=current_chapter_number,
                    chapter_title=current_chapter_title,
                    url=validated_url,
                )
            )
            print(f"Added chapter: {current_chapter_number} - {current_chapter_title}")
        except ValueError as e:
            print(f"Skipping current chapter due to invalid URL {chapter_url}: {e}")

        # Find next chapter link at the end
        next_link_pattern = r"Capítulo\s+\d+:\s+(https?://pastebin\.com/\w+)\s*$"
        print(f"Searching for next chapter link with pattern: {next_link_pattern}")

        next_link_match = re.search(next_link_pattern, raw_text_content, re.IGNORECASE)
        if next_link_match:
            next_chapter_url = next_link_match.group(1)
            print(f"Found next chapter URL: {next_chapter_url}")
        else:
            # Check for date format (end of chapters)
            date_pattern = r"Capítulo\s+\d+:\s+\d{2}/\d{2}/\d{4}\s*$"
            date_match = re.search(date_pattern, raw_text_content)
            if date_match:
                print("Found date marker, likely end of available chapters.")
            else:
                print("Could not find next chapter URL or date marker at the end.")

        elapsed = time.time() - start_time
        print(f"Parsing completed in {elapsed:.2f} seconds, found {len(chapters)} chapters")

        return chapters, next_chapter_url

    async def get_chapter_content(self, url: str, novel_id: str, chapter_number: int) -> Dict[str, Any]:
        """
        Get the content of a specific chapter.

        Args:
            url: The URL of the chapter
            novel_id: The ID of the novel
            chapter_number: The chapter number

        Returns:
            A dictionary containing the chapter content and metadata
        """
        # Check if we have a cached version
        cached_content = await storage_service.get_chapter(novel_id, chapter_number, "raw")
        if cached_content:
            return {"type": "novel", "content": cached_content}

        async with self:
            raw_url = self._convert_to_raw_url(url)
            print(f"Using raw URL: {raw_url}")
            content = await self.fetch_html(raw_url)
            if not content:
                raise Exception(f"Failed to fetch content from {url}")

            # Clean the content
            content = self._clean_content(content)

            # Cache the content
            await storage_service.save_chapter(novel_id, chapter_number, content, "raw")

            return {"type": "novel", "content": content}

    async def get_novel_info(self, url: str) -> Dict[str, Any]:
        """Get novel information from the source."""
        return {
            "title": "The Beginning After The End",
            "author": "TurtleMe",
            "description": "The Beginning After The End is a fantasy novel series written by TurtleMe.",
            "cover_image_url": None,
            "status": "Ongoing",
            "tags": ["Fantasy", "Action", "Adventure"],
            "source_url": url,
            "source_name": "pastebin_tbate",
            "type": "novel",
        }
