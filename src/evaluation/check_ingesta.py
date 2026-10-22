"""
Diagnóstico rápido: cuenta cuántos chunks quedaron en MongoDB por cada
fuente (fuente_origen), para verificar que los 3 PDFs se ingestaron
correctamente y ninguno quedó en 0.

"""

import os
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = "duoc_rag"
COLLECTION_NAME = "embeddings_estudiantes"

client = MongoClient(MONGO_URI)
collection = client[DB_NAME][COLLECTION_NAME]

total = collection.count_documents({})
print(f"Total de chunks en la colección: {total}\n")

pipeline = [
    {"$group": {"_id": "$fuente_origen", "cantidad": {"$sum": 1}}},
    {"$sort": {"cantidad": -1}},
]

for grupo in collection.aggregate(pipeline):
    print(f"  {grupo['_id']}: {grupo['cantidad']} chunks")