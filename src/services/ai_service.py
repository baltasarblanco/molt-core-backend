import json
import os
import re

from dotenv import load_dotenv
from google import genai

load_dotenv()

# Usamos la versión estable 'v1' y el modelo 2.5
client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"), http_options={"api_version": "v1"})
MODEL_ID = "gemini-2.0-flash"

SYSTEM_PROMPT = """
Eres el cerebro de la cervecería Môlt. Tu tarea es extraer pedidos de texto.
Responde ÚNICAMENTE con un JSON con este formato:
{
    "customer_name": "Nombre o 'Cliente'",
    "phone_number": "Número o null",
    "items": [{"product_keyword": "IPA/Hamburguesa/etc", "qty": int}]
}
"""


def parse_order_with_ai(text: str):
    try:
        response = client.models.generate_content(
            model=MODEL_ID, contents=f"{SYSTEM_PROMPT}\n\nTexto del cliente: {text}"
        )

        # Limpieza de Markdown
        raw_text = response.text.strip().replace("```json", "").replace("```", "")
        return json.loads(raw_text)

    except Exception as e:
        # Si Google falla (429/503), activamos el fallback silencioso
        print(f"⚠️ IA degradada: {str(e)}")
        return _fallback_parser(text)


def _fallback_parser(text: str):
    """Extractor de emergencia mejorado para múltiples productos"""
    text_lp = text.lower()
    items = []

    # 1. Buscar IPAs
    if "ipa" in text_lp:
        qty_ipa = re.search(r"(\d+)\s*ipa", text_lp)
        items.append({"product_keyword": "IPA", "qty": int(qty_ipa.group(1)) if qty_ipa else 1})

    # 2. Buscar Hamburguesas
    if "hambur" in text_lp or "burger" in text_lp:
        qty_burger = re.search(r"(\d+)\s*(hambur|burger)", text_lp)
        items.append(
            {"product_keyword": "Hamburguesa", "qty": int(qty_burger.group(1)) if qty_burger else 1}
        )

    # 3. Extraer nombre
    name_match = re.search(r"soy\s+([a-z]+)", text_lp)

    return {
        "customer_name": name_match.group(1).capitalize() if name_match else "Cliente",
        "phone_number": "2485559999",
        "items": items,  # <--- Ahora es una lista que puede tener varios!
    }
