"""
Retriever: dada una pregunta del estudiante, busca los fragmentos más
relevantes en MongoDB Atlas Vector Search, SIN filtrar por fuente
(busca siempre en duoc_interno y mineduc_externo a la vez).

Usa el mismo modelo de embeddings que la ingesta (all-MiniLM-L6-v2) —
esto es obligatorio: si consultas con un modelo distinto al usado para
ingestar, los vectores no son comparables y la búsqueda no funciona bien.
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

# Se cargan una sola vez al importar el módulo, para no recrear la conexión
# ni recargar el modelo en cada llamada a retrieve().
_client = MongoClient(MONGO_URI)
_collection = _client[DB_NAME][COLLECTION_NAME]
_embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

_vector_store = MongoDBAtlasVectorSearch(
    collection=_collection,
    embedding=_embeddings,
    index_name=INDEX_NAME,
)


def retrieve(pregunta: str, k: int = 8) -> list[dict]:
    """
    Busca los k fragmentos más relevantes en toda la colección
    (ambas fuentes combinadas) para una pregunta dada.

    Devuelve una lista de diccionarios con:
        - texto: el contenido del chunk
        - fuente: "Reglamento Duoc" | "Requisitos Mineduc" | "Manual FUAS"
        - pagina: número de página en el PDF original
        - score: qué tan relevante es (mayor = más relevante)
    """
    resultados = _vector_store.similarity_search_with_score(pregunta, k=k)

    fragmentos = []
    for doc, score in resultados:
        pagina_pypdf = doc.metadata.get("page", None)
        # PyPDFLoader numera las páginas desde 0; se ajusta a la numeración
        # humana (desde 1) para que la cita coincida con el PDF real.
        pagina_mostrada = pagina_pypdf + 1 if isinstance(pagina_pypdf, int) else "?"

        fragmentos.append({
            "texto": doc.page_content,
            "fuente": doc.metadata.get("fuente_origen", "Desconocida"),
            "pagina": pagina_mostrada,
            "score": round(score, 4),
        })
    return fragmentos


if __name__ == "__main__":
    # Prueba rápida por consola:
    #   python -m src.retrieval.retriever "¿se corta la gratuidad si repruebo un ramo?"
    import sys

    pregunta_prueba = " ".join(sys.argv[1:]) or "¿qué pasa con mi gratuidad si repruebo un ramo?"
    print(f"Buscando fragmentos relevantes para: {pregunta_prueba}\n")

    for i, frag in enumerate(retrieve(pregunta_prueba), start=1):
        print(f"--- Fragmento {i} (score={frag['score']}) ---")
        print(f"Fuente: {frag['fuente']} (página {frag['pagina']})")
        print(frag["texto"][:300], "...\n")