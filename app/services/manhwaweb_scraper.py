from typing import List, Optional, Dict, Any
from pydantic import HttpUrl
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin
from ..models.novel import Chapter
from .base_scraper import BaseScraper, ScraperConfig
from .storage_service import storage_service

class ManhwaWebScraper(BaseScraper):
    """Scraper for manhwaweb.com website."""
    
    def __init__(self):
        config = ScraperConfig(
            name="manhwaweb",
            base_url="https://manhwaweb.com",
            content_type="manhwa",
            selectors={
                # Selector para el título usando la estructura exacta
                "title": "h2.text-left.md\\:text-3xl.xs\\:text-2xl.mb-1.text-xl.font-normal",
                # Selector para la lista de capítulos
                "chapter_list": "div.grid.grid-cols-1.md\\:border.border-y div.flex.p-2.gap-2.border-t",
                # Selector para el título del capítulo dentro de cada elemento
                "chapter_title": "div.sm\\:text-lg.xs\\:text-base.text-sm",
                # Selector para el enlace del capítulo
                "chapter_link": "a.text-gray-500",
                # Selector para la imagen de portada
                "cover_image": "img.h-full.object-cover.aspect-lezhin",
                # Selector para el botón "Ver Todo" para cargar más capítulos
                "view_all_button": "button.ver_todo",
                # Selector para la descripción
                "description": "#root > div > div:nth-child(1) > div > div.container.mx-auto.max-w-6xl.sm\\:mt-5.mt-2 > div > div > div.sm\\:w-3\\/4.max-w-md.sm\\:max-w-none > div > span",
                # Selector para los tags
                "tags": "#root > div > div:nth-child(1) > div > div.container.mx-auto.max-w-6xl.sm\\:mt-5.mt-2 > div > div > div.sm\\:w-3\\/4.max-w-md.sm\\:max-w-none > div > div.grid.grid-cols-1 > div > a",
                # Selector para el autor
                "author": "#root > div > div:nth-child(1) > div > div.container.mx-auto.max-w-6xl.sm\\:mt-5.mt-2 > div > div > div.sm\\:w-3\\/4.max-w-md.sm\\:max-w-none > div > div:nth-child(7) > div.flex.gap-2 > a",
                # Selector para el estado
                "status": "#root > div > div:nth-child(1) > div > div.container.mx-auto.max-w-6xl.sm\\:mt-5.mt-2 > div > div > div.sm\\:w-3\\/4.max-w-md.sm\\:max-w-none > div > div:nth-child(5) > div.flex.items-center.gap-2 > div.text-base"
            },
            patterns={
                "chapter_number": r"Capitulo\s+(\d+)",
                "unwanted_text": [
                    r"Please support the translation team.*",
                    r"Join our Discord for updates.*",
                    r"Please read this chapter on our website.*"
                ]
            },
            use_playwright=True  # Usamos Playwright para manejar contenido dinámico
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
        """Get manhwa information from manhwaweb.com."""
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
                if status_text == "PUBLICANDOSE":
                    status = "Ongoing"
                elif status_text == "FINALIZADO":
                    status = "Completed"
            
            return {
                'title': title,
                'author': author,
                'description': description,
                'cover_image_url': cover_image_url,
                'status': status,
                'tags': tags,
                'source_url': url,
                'source_name': 'manhwaweb',
                'type': 'manhwa'
            }
    
    async def get_chapters(self, url: str, max_chapters: int = 50) -> List[Chapter]:
        """Get manhwa chapters from manhwaweb.com."""
        async with self:
            if not self._page:
                raise RuntimeError("Playwright page not initialized")
            
            await self._page.goto(url)
            await self._page.wait_for_load_state("networkidle")
            
            # Esperar a que la lista de capítulos esté visible
            await self._page.wait_for_selector(self.config.selectors["chapter_list"])
            
            # Intentar hacer clic en el botón "Ver Todo" si existe
            try:
                view_all_button = await self._page.wait_for_selector(self.config.selectors["view_all_button"], timeout=5000)
                if view_all_button:
                    await view_all_button.click()
                    # Esperar a que se carguen los nuevos capítulos
                    await self._page.wait_for_load_state("networkidle")
                    # Esperar a que la lista de capítulos se actualice
                    await self._page.wait_for_selector(self.config.selectors["chapter_list"])
                    # Esperar un poco más para asegurar que se cargan todos los capítulos
                    await self._page.wait_for_timeout(2000)
            except Exception as e:
                print(f"No se pudo hacer clic en el botón 'Ver Todo': {e}")
            
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
        cached_content = await storage_service.get_chapter(novel_id, chapter_number, "manhwa")
        if cached_content:
            return cached_content

        async with self:
            if not self._page:
                raise RuntimeError("Playwright page not initialized")
            
            await self._page.goto(url)
            await self._page.wait_for_load_state("networkidle")
            
            # Esperar a que el contenedor de imágenes esté visible
            await self._page.wait_for_selector("div.flex-col.justify-center.items-center")
            
            # Hacer scroll hasta el final de la página para cargar todas las imágenes
            await self._scroll_page_to_bottom(self._page)
            
            # Esperar un tiempo adicional para asegurar que las imágenes se carguen
            await self._page.wait_for_timeout(2000)
            
            # Obtener todas las imágenes dentro del contenedor
            images = await self._page.query_selector_all("div.flex-col.justify-center.items-center div.flex.flex-col.items-center.w-full.md\\:max-w-3xl.m-auto img")
            
            image_list = []
            
            # Obtener el índice de cada imagen en el DOM
            for index, img in enumerate(images):
                # Obtener el src completo usando evaluate
                src = await self._page.evaluate("(img) => img.src", img)
                alt = await img.get_attribute("alt")
                width = await img.get_attribute("width")
                height = await img.get_attribute("height")
                
                # Filtrar imágenes de carga y anuncios
                if (src and 
                    not any(ad in src for ad in ["pubadx", "ads", "advertisement"]) and
                    not src.endswith("loading.gif")):
                    
                    # Asegurarnos de que la URL es completa
                    if not src.startswith("http"):
                        src = urljoin(self.config.base_url, src)
                    
                    # Verificar que la imagen tenga dimensiones válidas
                    if width and height:
                        try:
                            w = int(width)
                            h = int(height)
                            if w > 1 and h > 1:
                                image_list.append({
                                    "url": src,
                                    "alt": alt or "",
                                    "width": width,
                                    "height": height,
                                    "index": index + 1  # Usamos index + 1 para que empiece en 1
                                })
                        except ValueError:
                            # Si las dimensiones son inválidas, seguimos añadiendo la imagen
                            image_list.append({
                                "url": src,
                                "alt": alt or "",
                                "width": width or "0",
                                "height": height or "0",
                                "index": index + 1
                            })
                    else:
                        # Si no tenemos dimensiones, añadimos la imagen de todos modos
                        image_list.append({
                            "url": src,
                            "alt": alt or "",
                            "width": width or "0",
                            "height": height or "0",
                            "index": index + 1
                        })
            
            # Ordenar las imágenes por su índice
            image_list.sort(key=lambda x: x["index"])
            
            content = {
                "type": "manhwa",
                "images": image_list,
                "total_images": len(image_list)
            }
            
            # Cache the content
            await storage_service.save_chapter(novel_id, chapter_number, content, "manhwa")
            
            return content 