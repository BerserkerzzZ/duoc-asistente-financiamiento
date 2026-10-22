"""
Interfaz de consola del asistente: agente con planificación y memoria de corto plazo.

Uso:
    python -m src.main                  # sesión nueva
    python -m src.main --sesion ID      # retoma una sesión anterior
    python -m src.main --usuario ana    # activa la memoria de largo plazo para "ana" (un apodo)
    python -m src.main --usuario ana --umbral 0.35   # recupera conversaciones menos parecidas
    python -m src.main --traza          # muestra el plan de cada pregunta
    python -m src.main --fragmentos --marcar "descuentos legales"
                                        # lista los fragmentos que recibió el modelo y marca
                                        # los que contienen la frase
"""

import argparse
import uuid

from src.agent.agente_planificado import responder_con_traza, EstadoSesion
from src.memory.corto_plazo import MemoriaCortoPlazo
from src.memory.largo_plazo import MemoriaLargoPlazo
from src.evidencia import registrar_turno, CARPETA_EVIDENCIA
from src.tools.privacidad import enmascarar_datos_personales


def _normalizar(texto: str) -> str:
    return " ".join(texto.lower().split())


def mostrar_fragmentos(resultados: list[dict], marcas: list[str] | None = None) -> None:
    """Imprime los fragmentos recuperados por paso; marca los que contienen alguna frase."""
    marcas = [_normalizar(m) for m in (marcas or [])]
    for r in resultados:
        print(f"  Paso {r['orden']} [{r['fuente']}] — {len(r['fragmentos'])} fragmentos:")
        for f in r["fragmentos"]:
            texto = _normalizar(f["texto"])
            contiene = [m for m in marcas if m in texto]
            aviso = f"   <-- contiene: {', '.join(contiene)}" if contiene else ""
            pagina = f", p.{f['pagina']}" if f.get("pagina") not in (None, "") else ""
            print(f"    {f['id']:>4} | {f['fuente']}{pagina} | {texto[:70]}{aviso}")


def usuario_valido(usuario: str) -> bool:
    """El usuario debe ser un apodo: no se aceptan RUT, correos ni teléfonos."""
    return bool(usuario.strip()) and enmascarar_datos_personales(usuario) == usuario


def lineas_de_memoria(largo_plazo, recuperados: list[dict]) -> list[str]:
    """Líneas de la traza sobre la memoria de largo plazo (vacías si no está activa)."""
    if largo_plazo is None:
        return []
    lineas = [
        f"  [Memoria de largo plazo: mejor similitud {largo_plazo.mejor_puntaje:.2f}, "
        f"umbral {largo_plazo.umbral:.2f}, {len(recuperados)} recuperada(s)]"
    ]
    lineas += [f"    ({r['score']}) {r['pregunta'][:70]}" for r in recuperados]
    return lineas


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Asistente de orientación y beneficios - Duoc UC")
    parser.add_argument("--sesion", default=None, help="ID de una sesión anterior para retomarla")
    parser.add_argument("--traza", action="store_true", help="muestra el plan de cada pregunta")
    parser.add_argument("--fragmentos", action="store_true", help="lista los fragmentos que recibió el modelo")
    parser.add_argument("--marcar", action="append", default=[], help="frase a marcar en la lista de fragmentos (se puede repetir)")
    parser.add_argument("--usuario", default=None, help="apodo del usuario; activa la memoria de largo plazo (no uses tu RUT)")
    parser.add_argument("--umbral", type=float, default=None,
                        help="similitud mínima (0 a 1) para recuperar conversaciones anteriores; con --usuario")
    parser.add_argument("--sin-registro", action="store_true", help="no guardar el registro de la sesión en tests/evidencia/sesiones")
    return parser


def main():
    args = construir_parser().parse_args()

    if args.usuario is not None and not usuario_valido(args.usuario):
        print("El usuario debe ser un apodo (por ejemplo 'ana'); no uses RUT, correo ni teléfono.")
        return

    if args.umbral is not None and not 0 <= args.umbral <= 1:
        print("El umbral debe estar entre 0 y 1 (por ejemplo 0.35).")
        return

    session_id = args.sesion or uuid.uuid4().hex[:8]
    memoria = MemoriaCortoPlazo(session_id)
    estado = EstadoSesion()
    largo_plazo = None
    if args.usuario:
        from src.retrieval.retriever import _embeddings   # mismo modelo de embeddings que la búsqueda
        opciones = {} if args.umbral is None else {"umbral": args.umbral}
        largo_plazo = MemoriaLargoPlazo(args.usuario, _embeddings.embed_query, **opciones)

    print("=" * 60)
    print("Asistente de Orientación y Beneficios Estudiantiles")
    print("Departamento de Admisión y Financiamiento - Duoc UC")
    print("=" * 60)
    print(f"Sesión: {session_id}" + (f"   Usuario: {args.usuario} (memoria de largo plazo activa)" if args.usuario else ""))
    print(f"(para retomarla más tarde: python -m src.main --sesion {session_id})")
    print("Escribe 'salir' para terminar.\n")

    while True:
        pregunta = input("Tú: ").strip()

        if not pregunta:
            continue

        if pregunta.lower() in ("salir", "exit", "quit"):
            print("\nGracias por usar el asistente. Que te vaya bien.")
            break

        try:
            salida = responder_con_traza(pregunta, memoria=memoria, estado=estado, largo_plazo=largo_plazo)
        except Exception as e:
            print(f"\nOcurrió un error al generar la respuesta: {e}")
            print("Verifica tu conexión, tu GROQ_API_KEY y tu MONGO_URI en el .env.\n")
            continue

        if args.traza:
            plan = salida["plan"]
            print(f"\n[Plan: {plan.tipo} — {plan.motivo}]")
            for paso in plan.pasos:
                print(f"  {paso.orden}. [{paso.fuente}] {paso.consulta}")
            if plan.crudo:
                print(f"  [salida cruda del planificador: {plan.crudo!r}]")
            for linea in lineas_de_memoria(largo_plazo, salida.get("recuperados") or []):
                print(linea)

        if args.fragmentos:
            print()
            mostrar_fragmentos(salida["resultados"], args.marcar)

        print(f"\nAsistente: {salida['respuesta']}\n")

        if not args.sin_registro:
            try:
                registrar_turno(CARPETA_EVIDENCIA, session_id, pregunta, salida, usuario=args.usuario)
            except Exception as e:   # el registro nunca debe interrumpir la conversación
                print(f"(No se pudo guardar el registro de la sesión: {e})\n")


if __name__ == "__main__":
    main()