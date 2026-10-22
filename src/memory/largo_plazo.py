"""
Memoria de largo plazo y recuperación semántica de contexto (IE3 e IE4).

Guarda cada consulta normativa del usuario (pregunta y un resumen de la respuesta, con los
datos personales enmascarados) junto con el embedding de la pregunta. En una sesión
posterior, recupera las conversaciones anteriores más parecidas a la pregunta actual por
similitud semántica, y el agente las usa para entender referencias ("lo del semestre
que consulté antes").

Decisión de diseño: la similitud se calcula en Python sobre los últimos documentos del
usuario, no con un índice vectorial de Atlas. Es suficiente para decenas o cientos de
turnos por usuario y evita configurar otro índice; con muchos más habría que usar
Atlas Vector Search.

El usuario se identifica con un apodo, nunca con el RUT. Lo recuperado es contexto, no
fuente de normas: las respuestas anteriores pueden contener errores.
"""

import math
import os
from datetime import datetime, timezone

from src.tools.privacidad import enmascarar_datos_personales

DB_NAME = "duoc_rag"
COLECCION_LARGO_PLAZO = "memoria_largo_plazo"
UMBRAL_SIMILITUD = 0.5       # valor inicial sin calibrar: ajustar mirando los puntajes de --traza
MAX_CHARS_RESPUESTA = 400
MAX_RECUPERADOS = 2
MAX_DOCUMENTOS = 200


def _coleccion_por_defecto():
    from pymongo import MongoClient   # importación diferida: el módulo se puede usar sin conexión
    return MongoClient(os.getenv("MONGO_URI"))[DB_NAME][COLECCION_LARGO_PLAZO]


def similitud_coseno(a: list[float], b: list[float]) -> float:
    producto = sum(x * y for x, y in zip(a, b))
    norma_a = math.sqrt(sum(x * x for x in a))
    norma_b = math.sqrt(sum(y * y for y in b))
    if norma_a == 0 or norma_b == 0:
        return 0.0
    return producto / (norma_a * norma_b)


class MemoriaLargoPlazo:
    def __init__(self, usuario: str, embedder, coleccion=None, max_recuperados: int = MAX_RECUPERADOS,
                 umbral: float = UMBRAL_SIMILITUD, max_documentos: int = MAX_DOCUMENTOS):
        """`embedder` es una función texto -> lista de números (el mismo modelo del retriever)."""
        self.usuario = usuario
        self._embedder = embedder
        self._coleccion = coleccion if coleccion is not None else _coleccion_por_defecto()
        self._max_recuperados = max_recuperados
        self.umbral = umbral
        self._max_documentos = max_documentos
        self.mejor_puntaje = 0.0   # mayor similitud de la última búsqueda, aunque no llegara al umbral

    def guardar_turno(self, session_id: str | None, pregunta: str, respuesta: str) -> None:
        pregunta_limpia = enmascarar_datos_personales(pregunta)
        resumen = enmascarar_datos_personales(respuesta)[:MAX_CHARS_RESPUESTA]
        self._coleccion.insert_one({
            "usuario": self.usuario,
            "session_id": session_id,
            "pregunta": pregunta_limpia,
            "resumen": resumen,
            "embedding": self._embedder(pregunta_limpia),
            "ts": datetime.now(timezone.utc),
        })

    def recuperar(self, pregunta: str, excluir_sesion: str | None = None) -> list[dict]:
        """Conversaciones anteriores del usuario (de otras sesiones) parecidas a la pregunta."""
        consulta = self._embedder(enmascarar_datos_personales(pregunta))
        documentos = list(
            self._coleccion.find({"usuario": self.usuario}).sort("_id", -1).limit(self._max_documentos)
        )
        candidatos = []
        self.mejor_puntaje = 0.0
        for doc in documentos:
            if excluir_sesion is not None and doc.get("session_id") == excluir_sesion:
                continue   # la sesión actual ya está en la memoria de corto plazo
            puntaje = similitud_coseno(consulta, doc["embedding"])
            self.mejor_puntaje = max(self.mejor_puntaje, round(puntaje, 3))
            if puntaje >= self.umbral:
                candidatos.append({"pregunta": doc["pregunta"], "resumen": doc["resumen"], "score": round(puntaje, 3)})
        candidatos.sort(key=lambda c: c["score"], reverse=True)
        return candidatos[: self._max_recuperados]


def formatear_recuperados(recuperados: list[dict]) -> str:
    """Bloque de texto para el prompt; vacío si no hay nada que recuperar."""
    if not recuperados:
        return ""
    lineas = [
        "CONVERSACIONES ANTERIORES RELACIONADAS (de otras sesiones; solo para entender "
        "referencias, no son fuente de normas):"
    ]
    for r in recuperados:
        lineas.append(f"- Pregunta anterior: {r['pregunta']} | Respuesta resumida: {r['resumen']}")
    return "\n".join(lineas)