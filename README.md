Asistente Inteligente de Orientación y Beneficios Estudiantiles

Prototipo de agente conversacional basado en RAG que responde consultas de estudiantes sobre reglamento académico, becas y beneficios estatales, 
citando siempre la fuente oficial de cada respuesta.

Desarrollado para la Evaluación Parcial N°1 — Ingeniería de Soluciones con IA (ISY0101)

Arquitectura

El sistema sigue el flujo: **Estudiante → Interfaz conversacional → Agente
orquestador → Retriever (MongoDB Atlas Vector Search, ambas fuentes combinadas)
→ LLM generador (Groq) → Respuesta con citas**.

Diagrama completo disponible en `docs/arquitectura.png`.

Estructura del proyecto

```
duoc-asistente-ia/
├── data/raw/
│   ├── duoc_interno/        # PDFs del reglamento y beneficios de Duoc UC
│   └── mineduc_externo/     # PDFs de normativa Mineduc (FUAS, gratuidad)
├── src/
│   ├── ingestion.py         # Carga PDFs, chunking, embeddings, sube a MongoDB
│   ├── retriever.py         # Búsqueda semántica en ambas fuentes
│   ├── prompts.py           # Reglas del sistema (citación, anti-alucinación, privacidad)
│   ├── agent.py             # Orquestador: retriever + prompt + LLM (Groq)
│   ├── main.py               # Interfaz de conversación por consola
│   ├── eval_dataset.py       # Preguntas de evaluación con respuesta conocida
│   ├── evaluar.py            # Corre el dataset de evaluación y genera reporte
│   ├── run_pruebas.py        # Corre preguntas de prueba generales
│   ├── check_ingesta.py      # Diagnóstico: conteo de chunks por fuente
│   └── check_texto.py        # Diagnóstico: búsqueda de texto literal en Mongo
├── tests/evidencia/           # Reportes de pruebas generados automáticamente
├── requirements.txt
└── .env.example
```

Requisitos previos

- Python 3.11 o superior
- Una cuenta de [MongoDB Atlas](https://www.mongodb.com/atlas)
- Una API key de [Groq](https://console.groq.com)

Instalación

1. Clonar el repositorio y entrar a la carpeta del proyecto:
   ```bash
   git clone <url-del-repo>
   cd duoc-asistente-ia
   ```

2. Crear un entorno virtual e instalar dependencias:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate        
   source .venv/bin/activate     

   pip install -r requirements.txt
   ```

3. Copiar el archivo de variables de entorno y completarlo con tus credenciales:
   ```bash
   copy .env.example .env        
   cp .env.example .env          
   ```
   Completa `MONGO_URI` (connection string de tu cluster de Atlas) y
   `GROQ_API_KEY` (desde console.groq.com/api-keys).

4. Colocar los PDFs oficiales en `data/raw/` según corresponda.

---

Configuración del índice de MongoDB Atlas

Antes de la primera ingesta, crea el índice de Vector Search en Atlas
(Atlas → tu cluster → Search → Create Search Index → JSON Editor):

```json
{
  "fields": [
    {
      "type": "vector",
      "path": "embedding",
      "numDimensions": 384,
      "similarity": "cosine"
    }
  ]
}
```

Nómbralo `vector_index` sobre la colección `embeddings_estudiantes` de la
base de datos `duoc_rag`. Espera a que el estado pase a **Active** antes de
consultar.

Ejecución

1. Ingestar los documentos a MongoDB
```bash
python -m src.ingestion
```
Descarga el modelo de embeddings multilingüe (`paraphrase-multilingual-MiniLM-L12-v2`,
~470MB, solo la primera vez), procesa los PDFs y sube los vectores a Atlas.

2. Verificar la ingesta (opcional)
```bash
python -m src.check_ingesta
```
Muestra cuántos fragmentos quedaron por cada fuente documental.

3. Probar el retriever de forma aislada (opcional)
```bash
python -m src.retriever "¿qué pasa con mi gratuidad si repruebo un ramo?"
```

4. Conversar con el asistente
```bash
python -m src.main
```
Abre un chat por consola. Escribe `salir` para terminar.

5. Correr la evaluación de precisión
```bash
python -m src.evaluar
```
Corre el dataset de preguntas con respuesta conocida (`src/eval_dataset.py`)
y genera `tests/evidencia/evaluacion_precision.md` con la comparación entre
la respuesta esperada y la respuesta real del agente.

Importante: siempre ejecutar los scripts con `python -m src.<nombre>`
desde la carpeta raíz del proyecto (no con `python src/<archivo>.py`), ya
que los módulos usan imports relativos al paquete `src`.

---

Resultados de la evaluación

Sobre un dataset de 8 preguntas con respuesta verificada manualmente contra
los documentos oficiales:

- ~62.5% de precisión estricta (5/8 respuestas totalmente correctas)
- 0% de tasa de alucinación: en los casos donde el agente no encontró
  el dato exacto, lo indicó explícitamente en vez de inventar información,
  cumpliendo el requisito de "cero alucinaciones" del caso organizacional.

Detalle completo en `tests/evidencia/evaluacion_precision.md`.

Limitación conocida

En preguntas sobre artículos específicos con datos numéricos puntuales
(porcentajes de cobro, límites de veces permitidas), el retriever no
siempre trae el chunk exacto entre los primeros resultados, a pesar de que
el contenido sí está correctamente ingestado (verificado con
`check_texto.py`). La causa identificada es que el corpus contiene varios
artículos temáticamente similares (duración nominal, cambios de carrera,
límites de cobro), lo que dificulta que la búsqueda semántica priorice el
artículo exacto entre docenas de candidatos parecidos.

Mejora futura propuesta: dividir el corpus por artículo completo (usando el
patrón "Artículo N°" como separador) en vez de chunks de tamaño fijo en
caracteres, para que cada unidad de búsqueda corresponda exactamente a una
unidad de sentido legal.

Nombres

- [Patricio Reinoso]

Ingeniería de Soluciones con IA (ISY0101).