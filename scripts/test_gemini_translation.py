"""Prueba rápida de la traducción con Gemini (verifica key + glosario).

Uso:
    /Users/ibrun/Documents/Programming/novu/venv/bin/python scripts/test_gemini_translation.py

Requiere GEMINI_API_KEY en .env. No usa DeepL ni la base de datos.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.utils.translation_service import TranslationService  # noqa: E402

SAMPLE = (
    "<p>Chapter 3043 Living Legends</p>\n"
    "<p>Sunny stepped into the Dream Realm, his Shadow Sense flaring as a "
    "Nightmare Creature emerged from the darkness. The Master of the Sacred "
    "order watched in silence.</p>"
)


async def main():
    svc = TranslationService()
    print(f"\nMotor activo: {svc.engine} | Gemini disponible: {bool(svc.gemini_client)}\n")

    result = svc._translate_gemini(SAMPLE)
    if not result:
        print("❌ Gemini no tradujo (revisa GEMINI_API_KEY o el modelo).")
        return
    print("✅ Traducción Gemini:\n")
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
