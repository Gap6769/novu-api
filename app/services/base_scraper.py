from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, HttpUrl, Field
import httpx
import asyncio
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from ..models.novel import Chapter
from playwright.async_api import async_playwright, Browser, Page
import re
from .storage_service import storage_service

class ScraperConfig(BaseModel):
    """Configuration for a scraper instance."""
    name: str
    base_url: str
    content_type: str  # 'novel', 'manhwa', etc.
    selectors: Dict[str, str]  # CSS selectors for different elements
    patterns: Dict[str, Union[str, List[str]]]  # Regex patterns for content extraction
    headers: Dict[str, str] = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    timeout: float = 10.0
    max_retries: int = 3
    use_playwright: bool = False  # Whether to use Playwright for JavaScript-heavy sites
    special_actions: Dict[str, Dict[str, Any]] = Field(
        default_factory=lambda: {
            "view_all": {
                "enabled": False,
                "selector": None,
                "wait_after_click": 0,
                "scroll_after_click": False
            }
        }
    )  # Special actions like clicking "view all" button

class ScraperError(Exception):
    """Custom exception for scraping errors."""
    pass

class BaseScraper:
    """Base class for all scrapers with common functionality."""
    
    def __init__(self, config: Optional[ScraperConfig] = None):
        if config is None:
            # Default configuration for backward compatibility
            config = ScraperConfig(
                name="base",
                base_url="",
                content_type="novel",
                selectors={},
                patterns={}
            )
        self.config = config
        self._client: Optional[httpx.AsyncClient] = None
        self._browser: Optional[Browser] = None
        self._page: Optional[Page] = None
        self._context = None
    
    async def __aenter__(self):
        """Context manager entry."""
        self._client = httpx.AsyncClient(
            follow_redirects=True,
            timeout=self.config.timeout,
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
        )
        
        if self.config.use_playwright:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch()
            self._context = await self._browser.new_context()
            self._page = await self._context.new_page()
        
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if self._client:
            await self._client.aclose()
            self._client = None
        
        if self._page:
            await self._page.close()
            self._page = None
        
        if self._browser:
            await self._browser.close()
            self._browser = None
        
        if hasattr(self, '_playwright'):
            await self._playwright.stop()
    
    async def fetch_html(self, url: str) -> str:
        """Fetch HTML content from a URL with retries."""
        if self.config.use_playwright and self._page:
            await self._page.goto(url)
            return await self._page.content()
        
        if not self._client:
            raise RuntimeError("Scraper must be used as an async context manager")
        
        for attempt in range(self.config.max_retries):
            try:
                response = await self._client.get(url, headers=self.config.headers)
                response.raise_for_status()
                return response.text
            except (httpx.HTTPError, httpx.TimeoutException) as e:
                if attempt == self.config.max_retries - 1:
                    raise ScraperError(f"Failed to fetch {url} after {self.config.max_retries} attempts: {e}")
                await asyncio.sleep(1 * (attempt + 1))  # Exponential backoff
    
    def resolve_url(self, url: str) -> str:
        """Resolve a relative URL against the base URL."""
        return urljoin(self.config.base_url, url)
    
    async def get_novel_info(self, url: str) -> Dict[str, Any]:
        """Get novel information from the source."""
        raise NotImplementedError("Subclasses must implement get_novel_info")
    
    async def get_chapters(self, url: str, max_chapters: int = 50) -> List[Chapter]:
        """Get novel chapters from the source."""
        raise NotImplementedError("Subclasses must implement get_chapters")
    
    async def get_chapter_content(self, url: str, novel_id: str, chapter_number: int) -> Dict[str, Any]:
        """Get the content of a specific chapter."""
        raise NotImplementedError("Subclasses must implement get_chapter_content")
    
    def _extract_text(self, element: Any, selector: str) -> Optional[str]:
        """Extract text from an element using a selector."""
        if not element:
            return None
        selected = element.select_one(selector)
        return selected.get_text(strip=True) if selected else None
    
    def _extract_attribute(self, element: Any, selector: str, attr: str) -> Optional[str]:
        """Extract an attribute from an element using a selector."""
        if not element:
            return None
        selected = element.select_one(selector)
        return selected.get(attr) if selected else None
    
    def _clean_content(self, content: str, additional_patterns: Optional[List[str]] = None) -> str:
        """Clean and normalize content."""
        # Remove unwanted elements
        soup = BeautifulSoup(content, 'html.parser')
        for element in soup.select('script, style, iframe, noscript'):
            element.decompose()
        
        # Get text content
        text = soup.get_text(separator='\n\n', strip=True)
        
        # Remove unwanted text patterns
        unwanted_patterns = [
            r"Enhance your reading experience by removing ads.*",
            r"This material may be protected by copyright.*",
            r"Excerpt From.*",
            r"Remove Ads From.*"
        ]
        
        if additional_patterns:
            unwanted_patterns.extend(additional_patterns)
        
        for pattern in unwanted_patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE | re.DOTALL)
        
        # Clean up extra whitespace
        text = re.sub(r'\n\s*\n', '\n\n', text)
        text = text.strip()
        
        return text
    
    async def _scroll_page_to_bottom(self, page: Page, timeout: int = 1000) -> None:
        """Scroll a Playwright page to the bottom to load all content."""
        last_height = await page.evaluate('document.body.scrollHeight')
        while True:
            await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            await page.wait_for_timeout(timeout)
            
            new_height = await page.evaluate('document.body.scrollHeight')
            if new_height == last_height:
                break
            last_height = new_height 