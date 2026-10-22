"""
Herramienta de consulta: normativa interna de Duoc UC.

`buscar_duoc` es la búsqueda en sí (con k configurable); `consulta_normativa_duoc`
la expone como herramienta para el agente con tool calling, que decide cuándo usarla
a partir de su descripción (docstring).
"""

from langchain_core.tools import tool

from src.retrieval.retriever import retrieve, formatear_contexto, FUENTES_DUOC


def buscar_duoc(consulta: str, k: int = 6) -> list[dict]:
    """Busca en Reglamento Duoc y devuelve los fragmentos (texto, fuente, página, score)."""
    return retrieve(consulta, k=k, fuentes=FUENTES_DUOC)


@tool
def consulta_normativa_duoc(consulta: str) -> str:
    """Busca en el Reglamento Académico de Duoc UC.

    Úsala para preguntas sobre normas internas de la institución: suspensión de
    estudios, renuncia a la carrera, cambio de carrera, convalidación, causales
    de eliminación y efectos académicos o de cobro de esos trámites.
    Recibe una consulta en lenguaje natural y devuelve fragmentos del reglamento
    con su fuente y página.
    """
    return formatear_contexto(buscar_duoc(consulta))