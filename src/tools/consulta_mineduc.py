"""
Herramienta de consulta: normativa estatal (Mineduc).
Cubre el Decreto 333 (gratuidad) y el Manual FUAS.

`buscar_mineduc` es la búsqueda en sí (con k configurable); `consulta_normativa_mineduc`
la expone como herramienta para el agente con tool calling.
"""

from langchain_core.tools import tool

from src.retrieval.retriever import retrieve, formatear_contexto, FUENTES_MINEDUC


def buscar_mineduc(consulta: str, k: int = 6) -> list[dict]:
    """Busca en Requisitos Mineduc y Manual FUAS y devuelve los fragmentos (texto, fuente, página, score)."""
    return retrieve(consulta, k=k, fuentes=FUENTES_MINEDUC)


@tool
def consulta_normativa_mineduc(consulta: str) -> str:
    """Busca en la normativa estatal de beneficios estudiantiles.

    Úsala para preguntas sobre gratuidad (Decreto 333) y sobre el FUAS: requisitos
    de acceso, mantención y suspensión del beneficio, cobros por exceso de duración
    nominal, cambios de carrera con gratuidad, plazos y cálculo de ingresos del
    grupo familiar. Recibe una consulta en lenguaje natural y devuelve fragmentos
    de los documentos oficiales con su fuente y página.
    """
    return formatear_contexto(buscar_mineduc(consulta))