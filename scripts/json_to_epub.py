import os
import json
import re
from ebooklib import epub

# 2563
# CHAPTERS_DIR = "lotm_chapters"
CHAPTERS_DIR = "shadow_slave_chapters"

# Rango de capitulos a incluir. None = sin limite por ese extremo.
START_CHAPTER = 3188
END_CHAPTER = 3197

OUTPUT_EPUB = f"Shadow Slave [{START_CHAPTER}-{END_CHAPTER}].epub"
# OUTPUT_EPUB = "Lord of the Mysteries [1-1432].epub"

NOVEL_TITLE = "Shadow Slave"
# NOVEL_TITLE = "Lord of the Mysteries"

AUTHOR = "G3"
# AUTHOR = "Cuttlefish"


# Anuncios inyectados por la fuente. Se comparan contra el contenido de cada <p>.
#
# Los patrones viejos usaban "\\n" en el regex, o sea barra invertida + "n" literal. El
# contenido viene de json.load(), asi que trae saltos de linea reales y esos patrones nunca
# calzaban. Ademas varios usaban ".*?" con DOTALL entre dos etiquetas, lo que podia borrar
# parrafos reales de la novela si el marcador de cierre quedaba lejos.
AD_EXACT_TEXTS = [
    # Citas
    "\U0001f60d \u00a1Las citas casuales est\u00e1n a un solo clic!",
    "\U0001f60d \u00a1Citas casuales a un solo clic!",
    "\U0001f60d \u00a1Las citas casuales est\u00e1n a un clic de distancia!",
    "Reg\u00edstrese y empiece a conocer mujeres en su zona hoy mismo.",
    "\U0001f60d Casual Date is just a click away!",
    "Sign up & start meeting women in your area today.",
    "Singles Near You",
    # Baile
    "Todo el p\u00fablico se qued\u00f3 helado cuando empez\u00f3 a bailar",
    "\u00a1Este baile es incre\u00edble! Mirad hasta el final",
    "CH dance",
    "CH bailar",
    "CH baile",
    "Baile CH",
    # Varios
    "Turista molest\u00f3 a guardia real sin saber que el responder\u00eda as\u00ed",
    "Mirsegondya",
    "Esta pastilla olvidada limpia las venas a un ritmo impresionante",
    "Cardiox",
    "Juego de monedas",
    "\u00a1Gana hoy al f\u00fatbol con tu bono del 100% de tu primer dep\u00f3sito!",
    # Promos del sitio y de la app
    "Anuncio",
    "Abrir",
    "Aplicaci\u00f3n para Android - Lector m\u00f3vil",
    "Aplicaci\u00f3n para iOS - Lector m\u00f3vil",
    "Contin\u00fae con los cap\u00edtulos en una aplicaci\u00f3n limpia con marcadores, historial, "
    "audio, comentarios y lectura sin conexi\u00f3n.",
]

# Familias cuya redaccion cambia entre capitulos.
AD_TEXT_REGEXES = [
    r"Anuncios? (?:de|by) PubFuture",
    r"Ads by PubFuture",
    r"Le[ae]r? con NB Reader",
    r"Solteros cerca de (?:usted|ti)",
    r"Actualizado (?:por primera vez|primero) en lightnovelworld\.org",
]

# Un <p> completo cuyo contenido sea exactamente un anuncio.
AD_BLOCK_RE = re.compile(
    r"[ \t]*<p>\s*(?:" + "|".join([re.escape(t) for t in AD_EXACT_TEXTS] + AD_TEXT_REGEXES) + r")\s*</p>[ \t]*\n?",
    re.IGNORECASE,
)

_BLANK_RUN_RE = re.compile(r"\n{3,}")


def clean_content(html):
    cleaned = AD_BLOCK_RE.sub("", html)
    return _BLANK_RUN_RE.sub("\n\n", cleaned).strip()


def load_chapters():
    chapters = []
    for filename in sorted(os.listdir(CHAPTERS_DIR)):
        if filename.endswith(".json"):
            with open(os.path.join(CHAPTERS_DIR, filename), encoding="utf-8") as f:
                data = json.load(f)
                chapter_number = data.get("chapter_number")
                if START_CHAPTER is not None and chapter_number < START_CHAPTER:
                    continue
                if END_CHAPTER is not None and chapter_number > END_CHAPTER:
                    continue
                chapter_title = data.get("chapter_title") or data.get("title")
                content = clean_content(data.get("content", ""))
                chapters.append({"number": chapter_number, "title": chapter_title, "content": content})
    # Ordenar por número de capítulo
    chapters.sort(key=lambda c: c["number"])
    return chapters


def create_epub(chapters):
    book = epub.EpubBook()
    book.set_identifier(f"shadow_slave_{START_CHAPTER}_{END_CHAPTER}")
    book.set_title(NOVEL_TITLE)
    book.set_language("es")
    book.add_author(AUTHOR)

    # Portada y metadatos opcionales aquí

    spine = ["nav"]
    toc = []
    for chapter in chapters:
        c = epub.EpubHtml(title=chapter["title"], file_name=f'chapter_{chapter["number"]}.xhtml', lang="es")
        c.content = f'<h2>{chapter["title"]}</h2>{chapter["content"]}'
        book.add_item(c)
        spine.append(c)
        toc.append(epub.Link(c.file_name, chapter["title"], f'chap_{chapter["number"]}'))

    book.toc = tuple(toc)
    book.spine = spine
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    epub.write_epub(OUTPUT_EPUB, book, {})
    print(f"EPUB generado: {OUTPUT_EPUB}")


if __name__ == "__main__":
    chapters = load_chapters()
    if not chapters:
        print("No se encontraron capítulos para procesar.")
    else:
        create_epub(chapters)
