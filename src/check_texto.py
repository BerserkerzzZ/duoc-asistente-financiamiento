"""
Diagnóstico: busca un texto EXACTO (no semántico) dentro de los chunks
ya ingestados en MongoDB, para confirmar si el contenido llegó bien a
la base de datos, independientemente de si el retriever semántico lo
encuentra o no.

"""

import os
import sys
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = "duoc_rag"
COLLECTION_NAME = "embeddings_estudiantes"

client = MongoClient(MONGO_URI)
collection = client[DB_NAME][COLLECTION_NAME]


def buscar_texto(termino: str):
    resultados = collection.find(
        {"text": {"$regex": termino, "$options": "i"}}
    )

    encontrados = list(resultados)
    print(f"Búsqueda literal de: '{termino}'")
    print(f"Coincidencias encontradas: {len(encontrados)}\n")

    for doc in encontrados[:5]:
        fuente = doc.get("fuente_origen", "?")
        pagina = doc.get("page", "?")
        texto = doc.get("text", "")[:400]
        print(f"--- {fuente} (página {pagina}) ---")
        print(texto, "...\n")


if __name__ == "__main__":
    termino_busqueda = " ".join(sys.argv[1:])
    if not termino_busqueda:
        print("Uso: python -m src.check_texto \"texto a buscar\"")
    else:
        buscar_texto(termino_busqueda)