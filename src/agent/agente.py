"""
Agente con herramientas (EP2): en vez de ejecutar siempre el mismo flujo
"buscar y generar", el LLM decide qué herramienta usar, cuántas veces y
si debe reformular la búsqueda antes de responder.

Uso:
    python -m src.agent.agente "¿qué pasa con mi gratuidad si suspendo un semestre?"
"""

import sys
from dotenv import load_dotenv
from langchain_groq import ChatGroq

from src.agent.prompts import SYSTEM_PROMPT
from src.tools.consulta_duoc import consulta_normativa_duoc
from src.tools.consulta_mineduc import consulta_normativa_mineduc

load_dotenv()

MODELO_LLM = "openai/gpt-oss-120b"
HERRAMIENTAS = [consulta_normativa_duoc, consulta_normativa_mineduc]

INSTRUCCIONES_HERRAMIENTAS = """

USO DE HERRAMIENTAS:
- Para cualquier consulta normativa debes usar herramientas. Nunca respondas de memoria.
- consulta_normativa_duoc: reglamento académico interno (suspensión, renuncia, cambio de carrera, convalidación).
- consulta_normativa_mineduc: normativa estatal (gratuidad, Decreto 333, FUAS, requisitos y plazos).
- Si la pregunta involucra ambas normativas, consulta las dos antes de responder.
- Si la pregunta combina un trámite académico (suspender, renunciar, cambiar de carrera) con un beneficio estatal (gratuidad, CAE), consulta SIEMPRE las dos herramientas: el reglamento de Duoc explica el trámite y la normativa del Mineduc explica el efecto sobre el beneficio.
- Si una búsqueda no trae lo necesario, reformula la consulta con otras palabras y vuelve a buscar (máximo 2 reintentos).
- Si después de buscar la información sigue siendo insuficiente, indícalo según la regla 2.
- Cuando expliques un procedimiento o cálculo, sigue exactamente los pasos que aparecen en los fragmentos: no agregues pasos ni omitas condiciones, mínimos o excepciones indicados como importantes.
- Si un paso o dato no aparece en los fragmentos, no lo completes por tu cuenta; indícalo.
- Saludos y preguntas fuera de tu ámbito no requieren herramientas.
- Antes de citar una disposición, verifica que aplique al caso preguntado. Si pertenece a un régimen especial (por ejemplo, la Ley 21.790), no la apliques a casos generales ni deduzcas consecuencias que el texto no indique.
"""

PROMPT_AGENTE = SYSTEM_PROMPT + INSTRUCCIONES_HERRAMIENTAS


def _crear_agente():
    llm = ChatGroq(model=MODELO_LLM, temperature=0.2, max_tokens=1200)
    try:
        # API actual de LangChain para agentes con tool calling.
        from langchain.agents import create_agent
        return create_agent(model=llm, tools=HERRAMIENTAS, system_prompt=PROMPT_AGENTE)
    except ImportError:
        # Respaldo para versiones anteriores (LangGraph prebuilt).
        from langgraph.prebuilt import create_react_agent
        return create_react_agent(llm, HERRAMIENTAS, prompt=PROMPT_AGENTE)


_agente = _crear_agente()


def responder_con_traza(pregunta: str) -> tuple[str, list[str]]:
    """
    Ejecuta el agente y devuelve (respuesta, herramientas_usadas).
    La lista de herramientas deja evidencia de las decisiones del agente.
    """
    resultado = _agente.invoke({"messages": [{"role": "user", "content": pregunta}]})
    mensajes = resultado["messages"]

    herramientas_usadas = [
        llamada["name"]
        for mensaje in mensajes
        for llamada in (getattr(mensaje, "tool_calls", None) or [])
    ]
    return mensajes[-1].content, herramientas_usadas


def responder(pregunta: str) -> str:
    """Versión simple: solo devuelve el texto de la respuesta."""
    return responder_con_traza(pregunta)[0]


if __name__ == "__main__":
    pregunta_prueba = " ".join(sys.argv[1:]) or "¿qué pasa con mi gratuidad si suspendo un semestre?"
    print(f"Pregunta: {pregunta_prueba}\n")

    respuesta, herramientas = responder_con_traza(pregunta_prueba)
    print(f"Herramientas usadas: {herramientas if herramientas else 'ninguna'}\n")
    print(respuesta)