import os
import requests
import json
import time

SHADOW_SLAVE_NOVEL_ID = "67fec087670d5c2ef8ac567e"
LOTM_NOVEL_ID = "68067caaeb5ad8a72588872d"
BASE_URL = f"http://localhost:8001/api/v1/novels/{SHADOW_SLAVE_NOVEL_ID}/chapters/"
START_CHAPTER = 3188
END_CHAPTER = 3197
LANGUAGE = "es"
FORMAT = "raw"
OUTPUT_DIR = "shadow_slave_chapters"
RETRY_DELAY = 1  # segundos entre reintentos
MAX_RETRIES = 5  # evita quedar en bucle infinito si el capitulo no existe en el source
SKIP_EXISTING = True  # no re-descarga (ni re-traduce) capitulos que ya estan en disco

os.makedirs(OUTPUT_DIR, exist_ok=True)


def download_chapter(chapter_num):
    filename = f"chapter_{chapter_num}_raw_es.json"
    filepath = os.path.join(OUTPUT_DIR, filename)
    if SKIP_EXISTING and os.path.exists(filepath):
        print(f"Ya existe, se salta: {filename}")
        return True

    url = f"{BASE_URL}{chapter_num}?language={LANGUAGE}&format={FORMAT}"
    for intento in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"Descargado: {data.get('chapter_title', f'Chapter_{chapter_num}')} -> {filename}")
            return True
        except Exception as e:
            if intento == MAX_RETRIES:
                print(f"FALLO el capítulo {chapter_num} tras {MAX_RETRIES} intentos: {e}")
                return False
            print(f"Error al descargar el capítulo {chapter_num}: {e}. Reintentando en {RETRY_DELAY} segundos...")
            time.sleep(RETRY_DELAY)


for chapter_num in range(START_CHAPTER, END_CHAPTER + 1):
    download_chapter(chapter_num)


# Preparar integración a EPUB después de la descarga
def integrate_to_epub():
    print("\nTodos los capítulos han sido descargados. Aquí puedes integrar la lógica para crear el EPUB.")
    # Ejemplo: leer todos los JSON, extraer contenido y crear el EPUB
    # Puedes usar la librería ebooklib o similar para esto


if __name__ == "__main__":
    integrate_to_epub()
