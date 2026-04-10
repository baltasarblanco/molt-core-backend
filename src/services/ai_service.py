import json
import os
import re

from dotenv import load_dotenv
from google import genai

load_dotenv()

# Configuración del cliente Gemini
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
    """Función principal con blindaje ante fallos de IA"""
    try:
        response = client.models.generate_content(
            model=MODEL_ID, contents=f"{SYSTEM_PROMPT}\n\nTexto del cliente: {text}"
        )

        # Limpieza de Markdown y parseo de JSON
        raw_text = response.text.strip().replace("```json", "").replace("```", "")
        return json.loads(raw_text)

    except Exception as e:
        # Si Google falla (429 Quota, 503 Overloaded, etc.), activamos el rescate
        print(f"⚠️ IA degradada (Usando Fallback): {str(e)}")
        return _fallback_parser(text)


def _fallback_parser(text: str):
    """
    Extractor de emergencia de ALTO RENDIMIENTO.
    Busca productos conocidos y detecta cantidades cercanas.
    """
    text_lp = text.lower()
    items = []

    # Definimos mapeos de keywords a nombres que tu DB entienda
    catalog = {
        "ipa": "IPA",
        "birra": "IPA",
        "pinta": "IPA",
        "burger": "Hamburguesa",
        "hambur": "Hamburguesa",
        "fernet": "Fernet",
        "coca": "Gaseosa",
    }

    for key, formal_name in catalog.items():
        if key in text_lp:
            # Buscamos un número que esté ANTES de la keyword (hasta 15 caracteres antes)
            # Ejemplo: "40 deliciosos fernets" -> captura el 40
            match = re.search(r"(\d+)\s*(?:\w+\s*){0,2}" + key, text_lp)
            qty = int(match.group(1)) if match else 1

            items.append({"product_keyword": formal_name, "qty": qty})

    # Extraer nombre (Soy Balti -> Balti)
    name_match = re.search(r"soy\s+([a-zñáéíóú]+)", text_lp)

    return {
        "customer_name": name_match.group(1).capitalize() if name_match else "Cliente",
        "phone_number": "+5400000000",
        "items": items,
    }
