from typing import List, Optional, Dict, Any
from pydantic import HttpUrl
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin
from ..models.novel import Chapter
from .base_scraper import BaseScraper, ScraperConfig
from .storage_service import storage_service
import asyncio

class SkyNovelsScraper(BaseScraper):
    """Scraper for skynovels.net website."""
    
    def __init__(self):
        config = ScraperConfig(
            name="skynovels",
            base_url="https://skynovels.net",
            content_type="novel",
            selectors={
                # Selectores más estables basados en el HTML
                "title": "h1.skn-novel-presentation-info-title",
                "chapter_list": "div.skn-nvl-info mat-expansion-panel, div.accordion-item",
                "chapter_title": "div.skn-nvl-chp-element-title",  # Título dentro del enlace de capítulo
                "chapter_number": "div.skn-nvl-chp-element-chp-number-index",  # Número del capítulo
                "chapter_link": "a.unstyled-a-tag.w-100.skn-link",  # Enlace a capítulos con la clase exacta
                "cover_image": "div.skn-novel-presentation-image img",
                "description": 'meta[name="description"]',
                "tags": "div.skn-nvl-card-genres span.skn-secondary",
                "author": "div.skn-text",  # Filtrar por el que contiene "Autor:"
                "status": "div.skn-secondary h4",
                "total_chapters": "div.skn-novel-presentation-info-stats div",  # Filtrar por el que contiene "Capitulos"
                "chapter_content": "div.skn-chp-chapter-content",  # Contenido del capítulo (contenedor principal)
                "content_button": "a.nav-link:has-text('Contenido')",  # Enlace para ver la pestaña de contenido
                "volume_button": "button:has-text('Volumenes'), a:has-text('Volumenes')",  # Botón para expandir volúmenes
                "volume_panels": "div.skn-nvl-info mat-expansion-panel, div.accordion-item",  # Paneles de volúmenes
                "chapter_links": "a.unstyled-a-tag.w-100.skn-link",  # Enlaces a capítulos con la clase exacta
                "expansion_panels": "mat-expansion-panel-header, div.accordion-header button, h2.accordion-header button"  # Cabeceras de paneles expandibles
            },
            patterns={
                "chapter_number": r"Capitulo\s+(\d+)",
                "unwanted_text": [
                    r"Please support the translation team.*",
                    r"Join our Discord for updates.*",
                    r"Please read this chapter on our website.*",
                    r"Visita skynovels.net para.*",
                    r"Si quieres leer más, visita.*",
                    r"Todos los derechos reservados.*",
                    r"Esta historia es propiedad de.*",
                    r"function\s*\(\s*w\s*,\s*q\s*\)\s*\{\s*w\s*\[\s*q\s*\]\s*=.*",
                    r"\(function\s*\(\s*w\s*,\s*q\s*\)\s*\{\s*w\s*\[\s*q\s*\]\s*=.*",
                    r"_mgwidget",
                    r"_mgq",
                    r"_mgc\.load"
                ]
            },
            use_playwright=True
        )
        super().__init__(config)
    
    def _extract_chapter_number(self, title: str) -> Optional[float]:
        """Extract chapter number from title."""
        if not title:
            return None
            
        # Try to extract chapter number using configured pattern
        match = re.search(self.config.patterns["chapter_number"], title, re.IGNORECASE)
        if match:
            try:
                return float(match.group(1))
            except (ValueError, IndexError):
                pass
                
        # Alternative pattern to find any number in title
        match = re.search(r'(\d+)', title)
        if match:
            try:
                return float(match.group(1))
            except (ValueError, IndexError):
                pass
                
        return None
    
    async def _safe_wait_for_load(self, timeout=30000):
        """Espera de forma segura a que la página cargue."""
        try:
            await self._page.wait_for_load_state("domcontentloaded", timeout=timeout)
            # Esperar un poco más para asegurar que el contenido dinámico se cargue
            await asyncio.sleep(2)
        except Exception as e:
            print(f"Warning: Timeout esperando carga de página: {e}")

    async def get_novel_info(self, url: str) -> Dict[str, Any]:
        """Get novel information from skynovels.net."""
        async with self:
            if not self._page:
                raise RuntimeError("Playwright page not initialized")
            
            await self._page.goto(url, wait_until="domcontentloaded")
            await self._safe_wait_for_load()
            
            # Esperar a que el contenido principal esté visible
            try:
                await self._page.wait_for_selector("div.skn-novel-presentation", timeout=10000)
            except Exception as e:
                print(f"Warning: Timeout esperando contenido principal: {e}")
            
            html = await self._page.content()
            soup = BeautifulSoup(html, 'html.parser')
            
            # Extraer título
            title = None
            title_elem = soup.select_one("h1.skn-novel-presentation-info-title")
            if title_elem:
                title = title_elem.get_text(strip=True).split("LOTM")[0].strip()  # Remover el acrónimo
            
            # Extraer imagen de portada
            cover_img = soup.select_one("div.skn-novel-presentation-image img")
            cover_image_url = cover_img["src"] if cover_img else None
            
            # Extraer descripción
            desc_elem = soup.select_one('meta[name="description"]')
            description = desc_elem["content"] if desc_elem else None
            
            # Extraer tags
            tag_elems = soup.select("div.skn-nvl-card-genres span.skn-secondary")
            tags = [tag.get_text(strip=True) for tag in tag_elems] if tag_elems else []
            
            # Extraer autor
            author = None
            author_elems = soup.select("div.skn-text")
            for elem in author_elems:
                text = elem.get_text(strip=True)
                if "Autor:" in text:
                    author = elem.find("strong").get_text(strip=True) if elem.find("strong") else None
                    break
            
            # Extraer estado
            status_elem = soup.select_one("div.skn-secondary h4")
            status_text = status_elem.get_text(strip=True) if status_elem else None
            status = None
            if status_text:
                status_text = status_text.lower()
                if "finalizada" in status_text:
                    status = "Completed"
                else:
                    status = "Ongoing"
            
            # Extraer total de capítulos
            total_chapters = None
            chapters_elems = soup.select("div.skn-novel-presentation-info-stats div")
            for elem in chapters_elems:
                text = elem.get_text(strip=True)
                if "Capitulos" in text:
                    match = re.search(r'(\d+)', text)
                    if match:
                        total_chapters = int(match.group(1))
                    break
            
            return {
                'title': title,
                'author': author,
                'description': description,
                'cover_image_url': cover_image_url,
                'status': status,
                'tags': tags,
                'source_url': url,
                'source_name': 'skynovels',
                'type': 'novel',
                'total_chapters': total_chapters
            }
    
    async def get_chapters(self, url: str, max_chapters: int = 50) -> List[Chapter]:
        """Get novel chapters from skynovels.net."""
        async with self:
            if not self._page:
                raise RuntimeError("Playwright page not initialized")
            
            print(f"Obteniendo capítulos de: {url}")
            await self._page.goto(url, wait_until="domcontentloaded")
            await self._safe_wait_for_load()
            
            # Esperar a que el contenido principal esté visible
            try:
                await self._page.wait_for_selector("div.skn-nvl-info", timeout=10000)
                
                # Hacer clic en la pestaña "Contenido" si está disponible
                contenido_button = await self._page.query_selector(self.config.selectors["content_button"])
                if contenido_button:
                    print("Haciendo clic en la pestaña 'Contenido'")
                    await contenido_button.click()
                    await asyncio.sleep(2)  # Esperar a que se cargue la pestaña de contenido
                    print("Se hizo clic en la pestaña 'Contenido'")
                else:
                    print("Warning: No se encontró el enlace 'Contenido'")
                
                # Intentar hacer clic en el botón de volúmenes si está disponible
                volume_button = await self._page.query_selector(self.config.selectors["volume_button"])
                if volume_button:
                    print("Haciendo clic en el botón 'Volúmenes'")
                    await volume_button.click()
                    await asyncio.sleep(2)  # Esperar a que se expandan los volúmenes
                    print("Se hizo clic en el botón 'Volúmenes'")
                
                # Intentar expandir todos los paneles de volumen
                panels = await self._page.query_selector_all(self.config.selectors["expansion_panels"])
                print(f"Encontrados {len(panels)} paneles de expansión")
                
                for i, panel in enumerate(panels):
                    try:
                        print(f"Expandiendo panel {i+1}/{len(panels)}")
                        await panel.click()
                        await asyncio.sleep(0.5)  # Pequeña pausa entre clics
                    except Exception as e:
                        print(f"Warning: Error al expandir panel {i+1}: {e}")
                        continue
                
                await asyncio.sleep(2)  # Esperar a que todo se expanda
                
                # Esperar a que la lista de capítulos esté visible
                try:
                    await self._page.wait_for_selector(self.config.selectors["chapter_links"], timeout=10000)
                    print("Selectores de capítulos encontrados")
                except Exception as e:
                    print(f"Error esperando selectores de capítulos: {e}")
                
                # Hacer scroll para cargar todos los capítulos
                await self._scroll_page_to_bottom(self._page)
                await asyncio.sleep(2)  # Esperar un poco después del scroll
                
            except Exception as e:
                print(f"Warning: Error al cargar la lista de capítulos: {e}")
            
            # Tomar una captura de pantalla para depuración
            try:
                await self._page.screenshot(path="debug_chapters.png")
                print("Captura de pantalla guardada como debug_chapters.png")
            except Exception as e:
                print(f"No se pudo guardar la captura de pantalla: {e}")
            
            html = await self._page.content()
            soup = BeautifulSoup(html, 'html.parser')
            
            chapters = []
            # Buscar todos los enlaces de capítulos
            chapter_links = soup.select(self.config.selectors["chapter_links"])
            print(f"Se encontraron {len(chapter_links)} enlaces de capítulos")
            
            for link in chapter_links:
                # Extraer título del capítulo
                title_elem = link.select_one(self.config.selectors["chapter_title"])
                chapter_title = ""
                if title_elem:
                    chapter_title = title_elem.get_text(strip=True)
                else:
                    # Si no encuentra el título con el selector, intentar extraerlo del texto completo
                    chapter_title = link.get_text(strip=True)
                
                # Extraer número de capítulo del elemento específico
                number_elem = link.select_one(self.config.selectors["chapter_number"])
                chapter_number = None
                if number_elem:
                    try:
                        chapter_number = float(number_elem.get_text(strip=True))
                    except (ValueError, TypeError):
                        # Si no se puede convertir, intentamos extraer del título
                        chapter_number = self._extract_chapter_number(chapter_title)
                
                # Si no se pudo extraer el número, intentar con el título o la URL
                if not chapter_number:
                    chapter_number = self._extract_chapter_number(chapter_title)
                    
                    if not chapter_number:
                        # Intentar extraer de la URL
                        chapter_url = link["href"]
                        match = re.search(r'/capitulo[/-](\d+)', chapter_url)
                        if match:
                            chapter_number = float(match.group(1))
                        else:
                            # Último recurso: usar la posición en la lista
                            chapter_number = len(chapters) + 1
                
                chapters.append(Chapter(
                    title=chapter_title,
                    chapter_number=chapter_number,
                    chapter_title=chapter_title,
                    url=self.resolve_url(link["href"]),
                    read=False,
                    downloaded=False
                ))
            
            # Ordenar capítulos por número
            chapters.sort(key=lambda x: x.chapter_number)
            
            # Limitar si es necesario
                
            print(f"Total de capítulos procesados: {len(chapters)}")
            return chapters
    
    def _clean_content(self, content: str, additional_patterns: List[str] = None) -> str:
        """Limpia el contenido del capítulo, eliminando texto no deseado y elementos publicitarios."""
        # Crear una copia del contenido para trabajar
        cleaned_content = content
        
        # Aplicar patrones de limpieza configurados
        patterns = self.config.patterns.get("unwanted_text", [])
        if additional_patterns:
            patterns.extend(additional_patterns)
            
        for pattern in patterns:
            cleaned_content = re.sub(pattern, "", cleaned_content, flags=re.IGNORECASE | re.DOTALL)
        
        # Eliminar scripts y estilos
        soup = BeautifulSoup(cleaned_content, 'html.parser')
        
        # Eliminar todos los scripts
        for script in soup.find_all(["script"]):
            script.extract()
        
        # Eliminar todos los elementos de estilo
        for style in soup.find_all(["style"]):
            style.extract()
            
        # Eliminar elementos publicitarios o no deseados
        for unwanted in soup.find_all(["miad-block1", "miad-block2", "miad-block3", "miad-block4", "miad-block5", 
                                      "div[data-type='_mgwidget']", "div[data-widget-id]"]):
            unwanted.extract()
        
        # Si el contenido está dentro de un tag 'markdown', extraer solo el contenido interno
        for markdown_tag in soup.find_all('markdown'):
            # Extraer el contenido interno del tag markdown
            markdown_content = markdown_tag.decode_contents()
            # Crear un nuevo elemento div para reemplazar el markdown
            new_div = soup.new_tag('div')
            new_div.append(BeautifulSoup(markdown_content, 'html.parser'))
            # Reemplazar el markdown con el nuevo div
            markdown_tag.replace_with(new_div)
        
        # Eliminar atributos no deseados de todos los elementos excepto imágenes y enlaces
        for tag in soup.find_all(True):
            if tag.name not in ["img", "a"]:
                # Conservar solo algunos atributos específicos si son necesarios
                if tag.name == "div" and tag.get("class") and "chapter-content" in tag.get("class"):
                    tag.attrs = {"class": "chapter-content"}
                else:
                    tag.attrs = {}
        
        # Eliminar elementos vacíos que no aportan contenido
        for tag in soup.find_all(True):
            if not tag.get_text(strip=True) and tag.name not in ['img', 'br', 'hr']:
                if not tag.find(['img', 'br', 'hr']):
                    tag.extract()
                
        return str(soup)

    async def get_chapter_content(self, url: str, novel_id: str = None, chapter_number: int = None) -> Dict[str, Any] | str:
        """Get the content of a specific chapter."""
        # Check if we have a cached version
        if novel_id and chapter_number:
            cached_content = await storage_service.get_chapter(novel_id, chapter_number, "novel")
            if cached_content:
                return cached_content

        async with self:
            if not self._page:
                raise RuntimeError("Playwright page not initialized")
            
            print(f"Obteniendo contenido del capítulo en: {url}")
            await self._page.goto(url, wait_until="domcontentloaded")
            await self._safe_wait_for_load()
            
            try:
                # Esperar a que el contenedor principal del capítulo esté visible
                await self._page.wait_for_selector("div.skn-chp-chapter-content", timeout=10000)
                print("Contenedor del capítulo encontrado")
            except Exception as e:
                print(f"Warning: Timeout esperando el contenedor del capítulo: {e}")
                
                # Intentar tomar captura de pantalla para depuración
                try:
                    await self._page.screenshot(path="debug_chapter.png")
                    print("Captura de pantalla guardada como debug_chapter.png")
                except Exception as e3:
                    print(f"No se pudo guardar la captura de pantalla: {e3}")
            
            # Intentar obtener el título directamente de la página con JavaScript
            page_title = await self._page.evaluate('''
                () => {
                    // Primero, intentar obtener el título desde un elemento markdown strong
                    const markdownStrong = document.querySelector('div.skn-chp-chapter-content markdown strong');
                    if (markdownStrong) {
                        return markdownStrong.textContent.trim();
                    }
                    
                    // Si no, intentar con h1, h2 o h3
                    const heading = document.querySelector('h1, h2, h3');
                    if (heading) {
                        return heading.textContent.trim();
                    }
                    
                    // Por último, usar el título de la página
                    return document.title.replace(/\s*\|\s*SkyNovels.*$/, '').trim();
                }
            ''')
            
            print(f"Título obtenido directamente: {page_title}")
            
            # Obtener el contenido actual de la página
            html = await self._page.content()
            soup = BeautifulSoup(html, 'html.parser')
            
            # Buscar el contenedor principal del capítulo
            chapter_container = soup.select_one("div.skn-chp-chapter-content")
            
            if not chapter_container:
                print("No se encontró el contenedor del capítulo")
                return None
            
            # Crear un nuevo contenedor para almacenar solo el contenido de los elementos markdown
            combined_content = BeautifulSoup("<div></div>", "html.parser")
            container_div = combined_content.div
            
            # Buscar todos los elementos markdown dentro del contenedor del capítulo
            all_markdowns = chapter_container.select("markdown")
            print(f"Encontrados {len(all_markdowns)} elementos markdown")
            
            # Extraer el título del capítulo - intentar diferentes métodos
            title = page_title if page_title else ""
            chapter_title = title
            
            # Si no tenemos título aún, intentar extraerlo del HTML
            if not title:
                # 1. Buscar en el primer elemento markdown (generalmente contiene el título)
                if all_markdowns and all_markdowns[0].select_one("strong"):
                    title_elem = all_markdowns[0].select_one("strong")
                    if title_elem:
                        title = title_elem.get_text(strip=True)
                        chapter_title = title  # Guardamos el título completo
                
                # 2. Si no encontramos título, buscar en encabezados de la página
                if not title:
                    title_elem = soup.select_one("h1, h2, h3")
                    if title_elem:
                        title = title_elem.get_text(strip=True)
                        chapter_title = title
                    else:
                        # 3. Si aún no hay título, intentar con el título de la página
                        title_elem = soup.select_one("title")
                        if title_elem:
                            title = title_elem.get_text(strip=True)
                            # Limpiar el título de la página (suele incluir el nombre del sitio)
                            title = re.sub(r'\s*\|\s*SkyNovels.*$', '', title)
                            chapter_title = title
            
            # Limpiar el título
            if title:
                # Eliminar espacios adicionales
                title = re.sub(r'\s+', ' ', title).strip()
                chapter_title = title
            
            # Extraer el número de capítulo del título si está presente y no se proporcionó
            if title and not chapter_number:
                match = re.search(r'Capítulo\s+(\d+)', title, re.IGNORECASE)
                if match:
                    chapter_number = int(match.group(1))
            
            # Agregar el contenido de cada markdown al contenedor combinado
            for markdown_elem in all_markdowns:
                # Obtener el contenido HTML del elemento markdown
                markdown_content = markdown_elem.decode_contents()
                # Parsear el contenido
                markdown_soup = BeautifulSoup(markdown_content, "html.parser")
                # Añadir cada elemento del markdown al contenedor combinado
                for element in markdown_soup:
                    container_div.append(element)
            
            # Si no se encontró ningún elemento markdown, usar el contenido del contenedor completo
            if len(all_markdowns) == 0:
                print("No se encontraron elementos markdown, usando contenedor completo")
                # Eliminar elementos no deseados del contenedor
                for unwanted in chapter_container.select("miad-block1, miad-block4, miad-block5, script"):
                    unwanted.extract()
                # Usar el contenido limpio
                cleaned_content = self._clean_content(str(chapter_container))
            else:
                # Limpiar el contenido combinado
                cleaned_content = self._clean_content(str(container_div))
            
            # Si no se proporciona novel_id o chapter_number, devolver solo el contenido como string
            if not novel_id or not chapter_number:
                return cleaned_content
            
            # Preparar el objeto de respuesta
            content_obj = {
                "type": "novel",
                "content": cleaned_content,
                "title": title,
                "chapter_title": chapter_title  # Incluimos el título completo del capítulo
            }
            
            # Cache the content
            await storage_service.save_chapter(novel_id, chapter_number, content_obj, "novel")
            print(f"Contenido del capítulo {chapter_number} guardado correctamente con título: {chapter_title}")
            
            return content_obj 