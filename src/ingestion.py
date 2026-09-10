import os
from dotenv import load_dotenv
from pymongo import MongoClient
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings 
from langchain_mongodb import MongoDBAtlasVectorSearch

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = "duoc_rag"
COLLECTION_NAME = "embeddings_estudiantes"
INDEX_NAME = "vector_index"


def procesar_e_ingestar_pdfs():
    # 1. Configurar conexión a MongoDB
    client = MongoClient(MONGO_URI)
    collection = client[DB_NAME][COLLECTION_NAME]

    # Limpiar datos anteriores
    collection.delete_many({})
    print("🧹 Colección en MongoDB limpiada con éxito.")

    # 2. CALCULAR RUTA ABSOLUTA
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    print(f"Detectando carpeta raíz del proyecto en: {BASE_DIR}")

    pdf_files = {
        "Reglamento Duoc": os.path.join(BASE_DIR, "data", "reglamento_duoc.pdf"),
        "Requisitos Mineduc": os.path.join(BASE_DIR, "data", "requisitos_mineduc.pdf"),
        "Manual FUAS": os.path.join(BASE_DIR, "data", "manual_fuas.pdf")
    }

    all_docs = []

    # 3. Cargar y parsear cada PDF usando su ruta exacta en el disco
    for fuente, ruta in pdf_files.items():
        if os.path.exists(ruta):
            print(f"Cargando {fuente} desde {ruta}...")
            loader = PyPDFLoader(ruta)
            docs = loader.load()

            for doc in docs:
                doc.metadata["fuente_origen"] = fuente

            all_docs.extend(docs)
        else:
            print(f"Archivo no encontrado en la ruta esperada: {ruta}")
            ruta_doble_ext = ruta + ".pdf"
            if os.path.exists(ruta_doble_ext):
                print(f"¡Se encontró el archivo pero tenía doble extensión (.pdf.pdf)! Cargando desde: {ruta_doble_ext}")
                loader = PyPDFLoader(ruta_doble_ext)
                docs = loader.load()
                for doc in docs:
                    doc.metadata["fuente_origen"] = fuente
                all_docs.extend(docs)

    # 4. Dividir el texto en fragmentos
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=100)
    chunks = text_splitter.split_documents(all_docs)
    print(f"Documentos divididos en {len(chunks)} fragmentos.")

    if len(chunks) == 0:
        print("\nERROR CRÍTICO: No se logró cargar ningún fragmento de texto.")
        print(f"Por favor, asegúrate de que exista la carpeta: {os.path.join(BASE_DIR, 'data')}")
        print("Y que tus tres archivos PDF estén guardados dentro de ella.")
        print("La ingesta a MongoDB ha sido cancelada.")
        return

    # 5. Configurar Embeddings LOCALES con sentence-transformers (vía HuggingFaceEmbeddings)
    print("Cargando modelo de embeddings local multilingüe (paraphrase-multilingual-MiniLM-L12-v2)...")
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

    # 6. Crear el almacén vectorial en MongoDB Atlas y subir los vectores
    print("Subiendo vectores y metadatos a MongoDB Atlas...")
    vector_store = MongoDBAtlasVectorSearch.from_documents(
        documents=chunks,
        embedding=embeddings,
        collection=collection,
        index_name=INDEX_NAME
    )
    print("¡Ingesta completada!")


if __name__ == "__main__":
    procesar_e_ingestar_pdfs()