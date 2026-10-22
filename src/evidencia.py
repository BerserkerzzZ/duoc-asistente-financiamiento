"""
Registro automático de evidencia: cada turno de la conversación se agrega a un archivo
Markdown por sesión en tests/evidencia/sesiones/ (pregunta, plan, fragmentos recuperados,
respuesta). Sirve como evidencia de pruebas para el informe, incluidas las respuestas malas.

Los datos personales (RUT, correo, teléfono) se enmascaran antes de escribir.
"""

from datetime import datetime
from pathlib import Path

from src.tools.privacidad import enmascarar_datos_personales

CARPETA_EVIDENCIA = "tests/evidencia/sesiones"


def _como_cita(texto: str) -> str:
    return "\n".join(f"> {linea}" if linea else ">" for linea in texto.splitlines())


def registrar_turno(carpeta, session_id: str, pregunta: str, salida: dict,
                    usuario: str | None = None, ahora: datetime | None = None) -> Path:
    """Agrega el turno al archivo de la sesión y devuelve su ruta."""
    ruta = Path(carpeta) / f"{session_id}.md"
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ahora = ahora or datetime.now()

    if ruta.exists():
        turno = ruta.read_text(encoding="utf-8").count("\n## Turno ") + 1
        encabezado = ""
    else:
        turno = 1
        quien = f" (usuario: {usuario})" if usuario else ""
        encabezado = f"# Sesión {session_id}{quien}\n"

    plan = salida["plan"]
    partes = [
        f"\n## Turno {turno} — {ahora.strftime('%Y-%m-%d %H:%M:%S')}\n",
        f"**Pregunta:** {enmascarar_datos_personales(pregunta)}\n",
        f"**Plan:** {plan.tipo} — {plan.motivo}",
    ]
    for paso in plan.pasos:
        detalle = paso.parametros if paso.fuente == "calculo" else paso.consulta
        partes.append(f"{paso.orden}. [{paso.fuente}] {detalle}")
    if getattr(plan, "crudo", ""):
        partes.append(f"(salida cruda del planificador: {plan.crudo!r})")

    recuperados = salida.get("recuperados") or []
    if recuperados:
        partes.append("\n**Memoria de largo plazo (conversaciones anteriores relacionadas):**")
        partes += [f"- ({r['score']}) {enmascarar_datos_personales(r['pregunta'])}" for r in recuperados]

    if salida.get("resultados"):
        partes.append("\n**Fragmentos recuperados:**")
        for resultado in salida["resultados"]:
            marcas = []
            for f in resultado["fragmentos"]:
                pagina = f", p.{f['pagina']}" if f.get("pagina") not in (None, "") else ""
                marcas.append(f"{f['id']} {f['fuente']}{pagina}")
            partes.append(f"- Paso {resultado['orden']} [{resultado['fuente']}]: " + "; ".join(marcas))

    partes.append("\n**Respuesta del asistente:**\n")
    partes.append(_como_cita(enmascarar_datos_personales(salida["respuesta"])))

    crudo = salida.get("texto_crudo")
    if crudo and "[cita no verificada]" in salida["respuesta"]:
        partes.append(
            "\n**Texto original del modelo (antes de resolver las citas), registrado porque hubo "
            "citas no verificadas:**\n"
        )
        partes.append(_como_cita(enmascarar_datos_personales(crudo)))

    with open(ruta, "a", encoding="utf-8") as archivo:
        archivo.write(encabezado + "\n".join(partes) + "\n")
    return ruta