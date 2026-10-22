"""
Agente orquestador: recibe la pregunta del estudiante, recupera contexto
relevante de MongoDB (vía retriever.py, buscando en ambas fuentes),
arma el prompt con las reglas de citación/anti-alucinación, y llama a
Groq para generar la respuesta final.

Uso:
    python -m src.agent "¿qué pasa con mi gratuidad si repruebo un ramo?"
"""

import os
from dotenv import load_dotenv
from groq import Groq

from src.retrieval.retriever import retrieve
from src.agent.prompts import SYSTEM_PROMPT, build_user_prompt

load_dotenv()

_groq_client = Groq(api_key=os.environ["GROQ_API_KEY"])

MODELO_LLM = "openai/gpt-oss-120b"


def responder(pregunta: str, k: int = 12) -> str:
    """
    Pipeline completo: retrieval + generación.
    Devuelve el texto de la respuesta final, ya con las citas incluidas
    por el LLM según las instrucciones del prompt de sistema.
    """
    fragmentos = retrieve(pregunta, k=k)

    if not fragmentos:
        return ("No encontré información relevante en los documentos disponibles "
                "para responder tu pregunta. Te recomiendo consultar directamente "
                "con la oficina de financiamiento de tu sede.")

    mensaje_usuario = build_user_prompt(pregunta, fragmentos)

    respuesta = _groq_client.chat.completions.create(
        model=MODELO_LLM,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": mensaje_usuario},
        ],
        temperature=0.2,
        max_tokens=1200,
    )

    return respuesta.choices[0].message.content


if __name__ == "__main__":
    import sys

    pregunta_prueba = " ".join(sys.argv[1:]) or "¿qué pasa con mi gratuidad si repruebo un ramo?"
    print(f"Pregunta: {pregunta_prueba}\n")
    print("Respuesta del agente:\n")
    print(responder(pregunta_prueba))