"""
Memoria de corto plazo (IE3): historial de la conversación por sesión, guardado
en MongoDB. Sirve para dos cosas:

1. Entender preguntas de seguimiento ("¿y si fueran dos semestres?").
2. Retomar una sesión después de cerrar el programa (python -m src.main --sesion ID).

El historial solo ayuda a interpretar la pregunta. No es fuente de normas: las
respuestas anteriores del asistente pueden contener errores.
"""

import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

DB_NAME = "duoc_rag"
COLECCION_MEMORIA = "memoria_corto_plazo"
MAX_CHARS_ASISTENTE = 500   # las respuestas largas se recortan al armar el historial


def _coleccion_por_defecto():
    cliente = MongoClient(os.getenv("MONGO_URI"))
    return cliente[DB_NAME][COLECCION_MEMORIA]


def formatear_historial(mensajes: list[dict]) -> str:
    """Convierte los mensajes guardados en texto para el prompt."""
    lineas = []
    for m in mensajes:
        if m["rol"] == "user":
            lineas.append(f"Estudiante: {m['contenido']}")
        else:
            contenido = m["contenido"]
            if len(contenido) > MAX_CHARS_ASISTENTE:
                contenido = contenido[:MAX_CHARS_ASISTENTE].rstrip() + " [...]"
            lineas.append(f"Asistente: {contenido}")
    return "\n".join(lineas)


class MemoriaCortoPlazo:
    def __init__(self, session_id: str, coleccion=None, max_mensajes: int = 6):
        self.session_id = session_id
        self.max_mensajes = max_mensajes
        self._coleccion = coleccion if coleccion is not None else _coleccion_por_defecto()

    def guardar(self, rol: str, contenido: str) -> None:
        self._coleccion.insert_one({
            "session_id": self.session_id,
            "rol": rol,
            "contenido": contenido,
            "ts": datetime.now(timezone.utc),
        })

    def obtener(self) -> list[dict]:
        """Últimos mensajes de la sesión, del más antiguo al más reciente."""
        cursor = (
            self._coleccion.find({"session_id": self.session_id})
            .sort("_id", -1)          # _id crece con el orden de inserción
            .limit(self.max_mensajes)
        )
        return list(reversed(list(cursor)))

    def texto(self) -> str:
        return formatear_historial(self.obtener())