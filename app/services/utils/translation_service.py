from typing import Optional
import deepl
from bs4 import BeautifulSoup
from app.core.config import settings
from app.services.glossaries.shadow_slave_glossary import SHADOW_SLAVE_GLOSSARY
from deep_translator import GoogleTranslator


class TranslationService:
    def __init__(self):
        self.source_language = "EN"
        self.target_language = settings.TARGET_LANGUAGE
        self.max_chunk_size = 5000  # Tamaño máximo de chunk para traducción

        # Estado de los motores (se inicializan según corresponda)
        self.translator = None  # DeepL
        self.usage = None
        self.glossary_id = None
        self.gemini_client = None
        self.google_translator = None

        # Glosario en texto plano para inyectar en el prompt de Gemini
        self._glossary_lines = "\n".join(f'- "{en}" → "{es}"' for en, es in SHADOW_SLAVE_GLOSSARY.items())

        if settings.IS_DEBUG:
            # En modo debug, solo Google Translate
            self.engine = "google"
            print("Usando Google Translate (modo debug)")
        else:
            self.engine = settings.TRANSLATION_ENGINE.lower()
            print(f"Motor de traducción principal: {self.engine}")

            # DeepL (solo si es el motor elegido)
            if self.engine == "deepl":
                if not settings.DEEPL_API_KEY:
                    raise ValueError(
                        "DEEPL_API_KEY no configurada. Por favor, añade DEEPL_API_KEY a tus variables de entorno."
                    )
                try:
                    self.translator = deepl.Translator(settings.DEEPL_API_KEY)
                    self.usage = self.translator.get_usage()
                    print(
                        f"DeepL API Status: {self.usage.character.count} caracteres usados de {self.usage.character.limit}"
                    )
                    self.glossary_id = self._setup_shadow_slave_glossary()
                except Exception as e:
                    raise ValueError(f"Error al inicializar DeepL: {str(e)}")

            # Gemini (motor principal o fallback si hay API key)
            if settings.GEMINI_API_KEY:
                try:
                    from google import genai

                    self.gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)
                    print(f"Gemini listo (modelo {settings.GEMINI_MODEL})")
                except Exception as e:
                    print(f"No se pudo inicializar Gemini: {str(e)}")
                    self.gemini_client = None
            elif self.engine == "gemini":
                raise ValueError("TRANSLATION_ENGINE=gemini pero GEMINI_API_KEY no está configurada.")

        # Google Translate: siempre disponible como último fallback gratuito
        try:
            self.google_translator = GoogleTranslator(source="en", target=self.target_language.lower())
        except Exception as e:
            print(f"No se pudo inicializar Google Translate: {str(e)}")
            self.google_translator = None

    def _setup_shadow_slave_glossary(self) -> str:
        """Configurar el glosario de términos específicos de Shadow Slave"""
        if settings.IS_DEBUG:
            return None
        glossary_id = None

        try:
            # Listar glosarios existentes y buscar uno con el nombre correcto
            glossaries = self.translator.list_glossaries()
            for glossary in glossaries:
                if glossary.name == "Shadow Slave Glossary":
                    print("Glosario existente encontrado, reutilizando.")
                    glossary_id = glossary.glossary_id
                    break

            # Si hay demasiados glosarios, borra los que sobren (excepto el que vamos a crear)
            MAX_GLOSSARIES = 10  # Ajusta según el límite de DeepL
            if len(glossaries) >= MAX_GLOSSARIES:
                print(f"Demasiados glosarios ({len(glossaries)}), borrando los más antiguos...")
                for glossary in glossaries:
                    try:
                        self.translator.delete_glossary(glossary.glossary_id)
                        print(f"Glosario {glossary.name} eliminado.")
                    except Exception as e:
                        print(f"Error eliminando glosario {glossary.name}: {str(e)}")

            if glossary_id is None:
                # Crear el glosario si no existe
                glossary = self.translator.create_glossary(
                    "Shadow Slave Glossary",
                    source_lang=self.source_language,
                    target_lang=self.target_language,
                    entries=SHADOW_SLAVE_GLOSSARY,
                )
                glossary_id = glossary.glossary_id
                print("Glosario creado correctamente.")
            return glossary_id

        except Exception as e:
            print(f"Error creando o reutilizando glosario: {str(e)}")
            return None

    def _split_text_into_chunks(self, text: str) -> list[str]:
        """
        Split text into chunks while preserving HTML structure and dialogue.
        Optimized for novel content with dialogue and paragraphs.
        """
        soup = BeautifulSoup(text, "html.parser")
        chunks = []
        current_chunk = []
        current_size = 0

        # Preservar estructura de diálogo y párrafos
        for element in soup.find_all(["p", "div", "span"]):
            element_text = str(element)

            # Si el elemento es muy grande, dividirlo
            if len(element_text) > self.max_chunk_size:
                sub_elements = element.find_all(["p", "div", "span"])
                for sub in sub_elements:
                    sub_text = str(sub)
                    if current_size + len(sub_text) > self.max_chunk_size and current_chunk:
                        chunks.append("".join(current_chunk))
                        current_chunk = [sub_text]
                        current_size = len(sub_text)
                    else:
                        current_chunk.append(sub_text)
                        current_size += len(sub_text)
            else:
                if current_size + len(element_text) > self.max_chunk_size and current_chunk:
                    chunks.append("".join(current_chunk))
                    current_chunk = [element_text]
                    current_size = len(element_text)
                else:
                    current_chunk.append(element_text)
                    current_size += len(element_text)

        if current_chunk:
            chunks.append("".join(current_chunk))

        return chunks

    def _translate_google(self, text: str) -> Optional[str]:
        """
        Traducir con Google Translate (deep_translator) por chunks, preservando HTML.
        Devuelve None si ningún chunk pudo traducirse.
        """
        if not self.google_translator:
            print("Fallback de Google Translate no disponible")
            return None

        chunks = self._split_text_into_chunks(text)
        if not chunks:
            print("Warning: No chunks were generated for translation")
            return None

        translated_chunks = []
        any_success = False
        for chunk in chunks:
            try:
                translated_chunks.append(self.google_translator.translate(chunk))
                any_success = True
            except Exception as e:
                print(f"Error translating chunk with Google Translate: {str(e)}")
                translated_chunks.append(chunk)  # Keep original if this chunk fails

        if not any_success:
            print("Warning: Google Translate no pudo traducir ningún chunk")
            return None

        return "\n".join(translated_chunks)

    def _translate_gemini(self, text: str) -> Optional[str]:
        """
        Traducir con Gemini usando el glosario de Shadow Slave en el prompt.
        Devuelve None si Gemini no está disponible o falla.
        """
        if not self.gemini_client:
            return None

        system_instruction = (
            "Eres un traductor profesional de novelas web (web novels) del inglés al español "
            "neutro, con tono narrativo formal y natural.\n"
            "Reglas ESTRICTAS:\n"
            "1. Traduce el texto COMPLETO. No resumas, no omitas ni añadas nada.\n"
            "2. Conserva EXACTAMENTE la estructura y las etiquetas HTML (por ejemplo <p>...</p>). "
            "Traduce únicamente el texto dentro de las etiquetas.\n"
            "3. Respeta OBLIGATORIAMENTE este glosario de términos propios (usa la traducción indicada "
            "tal cual, adaptando mayúsculas/minúsculas al contexto):\n"
            f"{self._glossary_lines}\n"
            "4. Mantén los nombres de personajes y lugares consistentes en toda la traducción.\n"
            "5. Devuelve ÚNICAMENTE el HTML traducido, sin explicaciones, sin comentarios y sin bloques "
            "de código markdown."
        )

        try:
            from google.genai import types

            response = self.gemini_client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=text,
                config=types.GenerateContentConfig(
                    temperature=0.2,
                    system_instruction=system_instruction,
                ),
            )
            out = (response.text or "").strip()
            if not out:
                print("Gemini devolvió una respuesta vacía")
                return None
            return self._strip_code_fences(out)
        except Exception as e:
            print(f"Error en Gemini: {str(e)}")
            return None

    @staticmethod
    def _strip_code_fences(text: str) -> str:
        """Quitar fences markdown (```html ... ```) que el modelo pueda añadir."""
        stripped = text.strip()
        if stripped.startswith("```"):
            lines = stripped.split("\n")
            lines = lines[1:]  # quitar primera línea (```html o ```)
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            stripped = "\n".join(lines).strip()
        return stripped

    async def translate_text(self, text: str) -> Optional[str]:
        """
        Translate HTML text using the configured translation service.
        Preserves HTML structure while translating content.
        Optimized for novel content with dialogue and paragraphs.

        Devuelve None si la traducción falla por completo (el caller NO debe cachear
        el original en inglés como si fuera español).
        """
        if settings.IS_DEBUG or self.engine == "google":
            return self._translate_google(text)

        if self.engine == "gemini":
            return self._translate_gemini(text) or self._translate_google(text)

        # DeepL (por defecto) con fallback automático: Gemini si está disponible, si no Google
        try:
            if self.usage.character.count >= self.usage.character.limit:
                raise ValueError("Límite de caracteres de DeepL alcanzado")

            result = self.translator.translate_text(
                text,
                target_lang=self.target_language,
                tag_handling="html",
                preserve_formatting=True,  # Preservar formato
                formality="prefer_more",  # Usar lenguaje más formal para novelas
                glossary=self.glossary_id,
                source_lang=self.source_language,
            )
            return result.text
        except Exception as e:
            print(f"DeepL no disponible ({str(e)}). Usando fallback...")
            return self._translate_gemini(text) or self._translate_google(text)

    def get_usage_stats(self) -> dict:
        """Obtener estadísticas de uso de la API"""
        if not settings.IS_DEBUG:
            try:
                usage = self.translator.get_usage()
                return {
                    "character_count": usage.character.count,
                    "character_limit": usage.character.limit,
                    "percentage_used": (usage.character.count / usage.character.limit) * 100,
                }
            except Exception as e:
                return {"error": str(e)}
        else:
            return {"message": "Google Translate does not provide usage statistics", "service": "google"}


translation_service = TranslationService()
