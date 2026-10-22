"""
Retriever: busca los fragmentos más relevantes en MongoDB Atlas Vector Search.

Puede buscar en todo el corpus o filtrar por documento (parámetro `fuentes`),
lo que permite que el agente decida a qué normativa consultar.

Requisito en Atlas: el índice vectorial debe declarar `fuente_origen` como
campo de filtro (ver README, sección "Índice de Atlas").

Uso:
    python -m src.retrieval.retriever "¿qué pasa con mi gratuidad si repruebo un ramo?"
"""

import os
from dotenv import load_dotenv
from pymongo import MongoClient
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_mongodb import MongoDBAtlasVectorSearch

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = "duoc_rag"
COLLECTION_NAME = "embeddings_estudiantes"
INDEX_NAME = "vector_index"

# Nombres tal como quedan en el campo `fuente_origen` durante la ingesta.
FUENTES_DUOC = ["Reglamento Duoc"]
FUENTES_MINEDUC = ["Requisitos Mineduc", "Manual FUAS"]

_client = MongoClient(MONGO_URI)
_collection = _client[DB_NAME][COLLECTION_NAME]
_embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

_vector_store = MongoDBAtlasVectorSearch(
    collection=_collection,
    embedding=_embeddings,
    index_name=INDEX_NAME,
)


def retrieve(pregunta: str, k: int = 12, fuentes: list[str] | None = None) -> list[dict]:
    """
    Busca los k fragmentos más relevantes para la pregunta.

    Si `fuentes` es None, busca en todo el corpus. Si se entrega una lista
    de nombres de documento, solo busca dentro de esos documentos.

    Devuelve diccionarios con: texto, fuente, pagina (numeración desde 1) y score.
    """
    filtro = {"fuente_origen": {"$in": fuentes}} if fuentes else None
    resultados = _vector_store.similarity_search_with_score(pregunta, k=k, pre_filter=filtro)

    fragmentos = []
    for doc, score in resultados:
        pagina_pypdf = doc.metadata.get("page", None)
        # PyPDFLoader numera desde 0; se ajusta a la numeración del PDF real.
        pagina = pagina_pypdf + 1 if isinstance(pagina_pypdf, int) else "?"

        fragmentos.append({
            "texto": doc.page_content,
            "fuente": doc.metadata.get("fuente_origen", "Desconocida"),
            "pagina": pagina,
            "score": round(score, 4),
        })
    return fragmentos


def formatear_contexto(fragmentos: list[dict]) -> str:
    """Convierte los fragmentos en texto con su fuente y página, listo para el LLM."""
    if not fragmentos:
        return "No se encontraron fragmentos relevantes en esta fuente."

    return "\n\n".join(
        f"[Fuente: {f['fuente']}, página {f['pagina']}]\n{f['texto']}"
        for f in fragmentos
    )


if __name__ == "__main__":
    import sys

    pregunta_prueba = " ".join(sys.argv[1:]) or "¿qué pasa con mi gratuidad si repruebo un ramo?"
    print(f"Buscando fragmentos relevantes para: {pregunta_prueba}\n")

    for i, frag in enumerate(retrieve(pregunta_prueba), start=1):
        print(f"--- Fragmento {i} (score={frag['score']}) ---")
        print(f"Fuente: {frag['fuente']} (página {frag['pagina']})")
        print(frag["texto"][:300], "...\n")