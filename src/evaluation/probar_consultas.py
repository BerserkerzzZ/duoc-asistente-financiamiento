"""
Diagnóstico de recuperación: para cada redacción de la consulta, en qué puesto
aparece cada frase objetivo. Sirve para ver cuánto depende el resultado de cómo
se escribe la consulta.

Uso (en una sola línea):
    python -m src.evaluation.probar_consultas --fuente mineduc --k 30 --frase "una sola vez" --frase "reintegre" --consulta "texto 1" --consulta "texto 2"

La comparación ignora mayúsculas y saltos de línea, para no perder frases que el
PDF parte entre dos líneas.
"""

import argparse

from src.retrieval.retriever import retrieve, FUENTES_DUOC, FUENTES_MINEDUC

FUENTES = {
    "duoc": FUENTES_DUOC,
    "mineduc": FUENTES_MINEDUC,            # decreto + manual FUAS juntos (como busca hoy el agente)
    "fuas": ["Manual FUAS"],               # solo el manual
    "decreto": ["Requisitos Mineduc"],     # solo el Decreto 333
    "todas": None,
}


def _normalizar(texto: str) -> str:
    return " ".join(texto.lower().split())


def puesto(fragmentos: list[dict], frase: str) -> int | None:
    """Puesto (desde 1) del primer fragmento que contiene la frase, o None."""
    objetivo = _normalizar(frase)
    for i, fragmento in enumerate(fragmentos, start=1):
        if objetivo in _normalizar(fragmento["texto"]):
            return i
    return None


def main(argv=None):
    parser = argparse.ArgumentParser(description="Puesto de frases objetivo según la redacción de la consulta")
    parser.add_argument("--fuente", choices=list(FUENTES), default="mineduc",
                        help="duoc, mineduc (decreto + manual), fuas (solo manual), decreto (solo decreto) o todas")
    parser.add_argument("--k", type=int, default=30, help="cuántos fragmentos mirar")
    parser.add_argument("--frase", action="append", required=True, help="frase objetivo (se puede repetir)")
    parser.add_argument("--consulta", action="append", required=True, help="redacción a probar (se puede repetir)")
    args = parser.parse_args(argv)

    ancho = 62
    encabezado = f"{'consulta':<{ancho}}" + "".join(f"{f[:18]:>20}" for f in args.frase)
    print(encabezado)
    print("-" * len(encabezado))
    for consulta in args.consulta:
        fragmentos = retrieve(consulta, k=args.k, fuentes=FUENTES[args.fuente])
        corta = consulta if len(consulta) <= ancho - 2 else consulta[: ancho - 3] + "…"
        celdas = []
        for frase in args.frase:
            p = puesto(fragmentos, frase)
            celdas.append(f"{(str(p) if p else f'>{args.k}'):>20}")
        print(f"{corta:<{ancho}}" + "".join(celdas))


if __name__ == "__main__":
    main()