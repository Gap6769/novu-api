from typing import List, Optional, Dict, Any
from pydantic import HttpUrl
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin
from ..models.novel import Chapter
from .base_scraper import BaseScraper, ScraperConfig
from .storage_service import storage_service

class WuxiaWorldScraper(BaseScraper):
    """Scraper for wuxiaworld.com website."""
    
    def __init__(self):
        config = ScraperConfig(
            name="wuxiaworld",
            base_url="https://www.wuxiaworld.com",
            content_type="novel",
            selectors={
                "title": "h1.novel-title",
                "chapter_list": "div.chapter-list a",
                "chapter_title": "span.chapter-title",
                "chapter_link": "a",
                "cover_image": "div.novel-cover img",
                "description": "div.novel-summary",
                "tags": "div.novel-tags a",
                "author": "div.novel-author a",
                "status": "div.novel-status"
            },
            patterns={
                "chapter_number": r"Chapter\s+(\d+)",
                "unwanted_text": [
                    r"Please support the translation team.*",
                    r"Join our Discord for updates.*",
                    r"Please read this chapter on our website.*"
                ]
            },
            use_playwright=True
        )
        super().__init__(config)
    
    def _extract_chapter_number(self, title: str) -> Optional[float]:
        """Extract chapter number from title."""
        if not title:
            return None
            
        # Intentar extraer el número del capítulo usando el patrón configurado
        match = re.search(self.config.patterns["chapter_number"], title, re.IGNORECASE)
        if match:
            try:
                return float(match.group(1))
            except (ValueError, IndexError):
                pass
                
        # Patrón alternativo para buscar cualquier número en el título
        match = re.search(r'(\d+)', title)
        if match:
            try:
                return float(match.group(1))
            except (ValueError, IndexError):
                pass
                
        return None
    
    async def get_novel_info(self, url: str) -> Dict[str, Any]:
        """Get novel information from wuxiaworld.com."""
        async with self:
            if not self._page:
                raise RuntimeError("Playwright page not initialized")
            
            await self._page.goto(url)
            await self._page.wait_for_load_state("networkidle")
            
            # Esperar a que el título esté visible
            await self._page.wait_for_selector(self.config.selectors["title"])
            
            html = await self._page.content()
            soup = BeautifulSoup(html, 'html.parser')
            
            # Extraer título
            title_elem = soup.select_one(self.config.selectors["title"])
            title = title_elem.get_text(strip=True) if title_elem else None
            
            # Extraer imagen de portada
            cover_img = soup.select_one(self.config.selectors["cover_image"])
            cover_image_url = cover_img["src"] if cover_img else None
            
            # Extraer descripción
            desc_elem = soup.select_one(self.config.selectors["description"])
            description = desc_elem.get_text(strip=True) if desc_elem else None
            
            # Extraer tags
            tag_elems = soup.select(self.config.selectors["tags"])
            tags = [tag.get_text(strip=True) for tag in tag_elems] if tag_elems else []
            
            # Extraer autor
            author_elem = soup.select_one(self.config.selectors["author"])
            author = author_elem.get_text(strip=True) if author_elem else None
            
            # Extraer estado y mapearlo
            status_elem = soup.select_one(self.config.selectors["status"])
            status_text = status_elem.get_text(strip=True) if status_elem else None
            status = None
            if status_text:
                if status_text == "Ongoing":
                    status = "Ongoing"
                elif status_text == "Completed":
                    status = "Completed"
            
            return {
                'title': title,
                'author': author,
                'description': description,
                'cover_image_url': cover_image_url,
                'status': status,
                'tags': tags,
                'source_url': url,
                'source_name': 'wuxiaworld',
                'type': 'novel'
            }
    
    async def get_chapters(self, url: str, max_chapters: int = 50) -> List[Chapter]:
        """Get novel chapters from wuxiaworld.com."""
        async with self:
            if not self._page:
                raise RuntimeError("Playwright page not initialized")
            
            await self._page.goto(url)
            await self._page.wait_for_load_state("networkidle")
            
            # Esperar a que la lista de capítulos esté visible
            await self._page.wait_for_selector(self.config.selectors["chapter_list"])
            
            # Scroll para cargar todos los capítulos
            await self._scroll_page_to_bottom(self._page)
            
            # Esperar a que se carguen los capítulos después del scroll
            await self._page.wait_for_load_state("networkidle")
            await self._page.wait_for_selector(self.config.selectors["chapter_list"])
            
            html = await self._page.content()
            soup = BeautifulSoup(html, 'html.parser')
            
            chapters = []
            # Buscar todos los elementos de capítulo
            chapter_elements = soup.select(self.config.selectors["chapter_list"])
            
            for element in chapter_elements:
                # Extraer título del capítulo
                title_elem = element.select_one(self.config.selectors["chapter_title"])
                if not title_elem:
                    continue
                    
                chapter_title = title_elem.get_text(strip=True)
                
                # Extraer enlace del capítulo
                link_elem = element.select_one(self.config.selectors["chapter_link"])
                if not link_elem:
                    continue
                    
                chapter_url = self.resolve_url(link_elem["href"])
                
                # Extraer número de capítulo del título
                chapter_number = self._extract_chapter_number(chapter_title)
                if not chapter_number:
                    # Si no podemos extraer el número, usamos el índice
                    chapter_number = len(chapters) + 1
                
                chapters.append(Chapter(
                    title=chapter_title,
                    chapter_number=chapter_number,
                    chapter_title=chapter_title,
                    url=chapter_url,
                    read=False,
                    downloaded=False
                ))
            
            # Ordenar capítulos por número
            chapters.sort(key=lambda x: x.chapter_number)
            
            return chapters
    
    async def get_chapter_content(self, url: str, novel_id: str, chapter_number: int) -> Dict[str, Any]:
        """Get the content of a specific chapter."""
        # Check if we have a cached version
        cached_content = await storage_service.get_chapter(novel_id, chapter_number, "raw")
        if cached_content:
            return {
                "type": "novel",
                "content": cached_content
            }

        async with self:
            if not self._page:
                raise RuntimeError("Playwright page not initialized")
            
            await self._page.goto(url)
            await self._page.wait_for_load_state("networkidle")
            
            # Esperar a que el contenido esté visible
            await self._page.wait_for_selector("div.chapter-content")
            
            # Obtener el contenido del capítulo
            content = await self._page.evaluate("""
                () => {
                    const content = document.querySelector("div.chapter-content");
                    return content ? content.innerText : "";
                }
            """)
            
            # Limpiar el contenido
            content = self._clean_content(content)
            
            # Cache the content
            await storage_service.save_chapter(novel_id, chapter_number, content, "raw")
            
            return {
                "type": "novel",
                "content": content
            }
    
    def _clean_content(self, content: str) -> str:
        """Clean the chapter content."""
        # Eliminar texto no deseado
        for pattern in self.config.patterns["unwanted_text"]:
            content = re.sub(pattern, "", content, flags=re.IGNORECASE)
        
        # Eliminar líneas vacías y espacios extra
        lines = [line.strip() for line in content.split("\n") if line.strip()]
        return "\n".join(lines) 