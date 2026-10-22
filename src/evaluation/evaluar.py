"""
Corre el dataset de evaluación (preguntas de respuesta conocida) contra el
agente, y genera un reporte en Markdown comparando la respuesta esperada
(la correcta, según el reglamento) contra la respuesta real del agente.

La evaluación de "¿coincide o no?" es manual/visual -- se revisa cada caso
y se completa el veredicto a mano, porque comparar texto libre en lenguaje
natural de forma 100% automática no es confiable para este tipo de contenido.

Uso:
    python -m src.evaluar
"""

from datetime import datetime
from pathlib import Path
import time

from src.agent.agent import responder
from src.evaluation.dataset import CASOS_EVALUACION


def ejecutar_evaluacion():
    resultados = []

    for i, caso in enumerate(CASOS_EVALUACION, start=1):
        print(f"[{i}/{len(CASOS_EVALUACION)}] Probando: {caso['pregunta']}")
        try:
            respuesta_real = responder(caso["pregunta"])
        except Exception as e:
            respuesta_real = f"ERROR al generar respuesta: {e}"

        resultados.append({
            **caso,
            "respuesta_real": respuesta_real,
        })
        if i < len(CASOS_EVALUACION):
            time.sleep(8)

    return resultados


def guardar_reporte(resultados: list[dict]):
    carpeta = Path("tests/evidencia")
    carpeta.mkdir(parents=True, exist_ok=True)

    archivo = carpeta / "evaluacion_precision.md"
    fecha = datetime.now().strftime("%Y-%m-%d %H:%M")

    with open(archivo, "w", encoding="utf-8") as f:
        f.write("# Evaluación de precisión — Asistente Duoc UC\n\n")
        f.write(f"**Fecha de ejecución:** {fecha}\n\n")
        f.write(f"**Total de casos evaluados:** {len(resultados)}\n\n")
        f.write(
            "**Metodología:** cada caso tiene una respuesta esperada, extraída "
            "manualmente del documento oficial correspondiente. Se compara "
            "contra la respuesta real generada por el agente. El veredicto "
            "(Correcto / Parcial / Incorrecto) se completa manualmente tras "
            "revisar cada caso.\n\n"
        )
        f.write("---\n\n")

        for i, r in enumerate(resultados, start=1):
            f.write(f"## Caso {i}\n\n")
            f.write(f"**Pregunta:**\n> {r['pregunta']}\n\n")
            f.write(f"**Respuesta esperada (según documento oficial):**\n{r['respuesta_esperada']}\n\n")
            f.write(f"**Fuente esperada:** {r['fuente_esperada']}\n\n")
            f.write(f"**Respuesta real del agente:**\n\n{r['respuesta_real']}\n\n")
            f.write("---\n\n")

        f.write(
            "\n## Resumen\n\n"
            "Completar tras revisar todos los casos:\n\n"
            "- Correctos: __ / " + str(len(resultados)) + "\n"
            "- Parciales: __ / " + str(len(resultados)) + "\n"
            "- Incorrectos: __ / " + str(len(resultados)) + "\n"
            "- % de precisión: __ %\n"
        )

    print(f"\n✅ Reporte guardado en: {archivo.resolve()}")
    print("   Ábrelo, revisa cada caso y marca el veredicto manualmente.")


if __name__ == "__main__":
    resultados = ejecutar_evaluacion()
    guardar_reporte(resultados)