"""
Herramienta de escritura (IE1): borrador de solicitud para la oficina de financiamiento.

Usa una plantilla fija, sin LLM: no agrega llamadas al modelo y no puede inventar normas
dentro del borrador. Incluye las preguntas del estudiante en esta sesión y la normativa que
el asistente citó, para que la oficina pueda verificarla. No incluye las respuestas del
asistente, porque pueden contener errores.

Nombre, RUT, sede, carrera y correo quedan en blanco para que el estudiante los complete
a mano: el sistema no los pide ni los guarda.
"""

from datetime import datetime
from pathlib import Path

from src.tools.privacidad import enmascarar_datos_personales

CARPETA_BORRADORES = "borradores"
MAX_PREGUNTAS = 5
MAX_ASUNTO = 100


def _lineas_de_normativa(citas: list[dict]) -> list[str]:
    """Agrupa las citas por documento: '- Documento, páginas 18, 19'."""
    paginas: dict[str, list] = {}
    for cita in citas:
        lista = paginas.setdefault(cita["fuente"], [])
        pagina = cita.get("pagina")
        if pagina not in (None, "") and pagina not in lista:
            lista.append(pagina)
    lineas = []
    for documento, lista in paginas.items():
        numeros = sorted(p for p in lista if isinstance(p, int))
        otras = [str(p) for p in lista if not isinstance(p, int)]
        todas = [str(n) for n in numeros] + otras
        if not todas:
            lineas.append(f"- {documento}")
        else:
            palabra = "página" if len(todas) == 1 else "páginas"
            lineas.append(f"- {documento}, {palabra} {', '.join(todas)}")
    return lineas


def construir_borrador(preguntas: list[str], citas: list[dict], fecha: str) -> str:
    limpias = [enmascarar_datos_personales(p).strip() for p in preguntas if p.strip()]
    limpias = limpias[-MAX_PREGUNTAS:]
    asunto = limpias[0] if limpias else ""
    if len(asunto) > MAX_ASUNTO:
        asunto = asunto[:MAX_ASUNTO].rstrip() + "..."

    lineas = [
        "SOLICITUD DE ORIENTACIÓN",
        "Departamento de Admisión y Financiamiento, Duoc UC",
        f"Fecha: {fecha}",
        "",
        "Nombre completo: [COMPLETAR]",
        "RUT: [COMPLETAR]",
        "Sede: [COMPLETAR]",
        "Carrera: [COMPLETAR]",
        "Correo de contacto: [COMPLETAR]",
        "",
        f"Asunto: {asunto}",
        "",
        "Estimados/as:",
        "",
        "Junto con saludar, solicito orientación sobre la siguiente situación.",
        "",
        "Consultas que realicé al asistente de orientación:",
    ]
    lineas += [f"{i}. {pregunta}" for i, pregunta in enumerate(limpias, start=1)]

    normativa = _lineas_de_normativa(citas)
    if normativa:
        lineas += ["", "Normativa que el asistente revisó (para su verificación):"] + normativa

    lineas += [
        "",
        "Les pido confirmar cómo se aplica esta normativa a mi caso concreto y cuáles son los "
        "pasos y plazos que debo seguir.",
        "",
        "Quedo atento/a a su respuesta.",
        "Saludos cordiales,",
        "[NOMBRE COMPLETO]",
        "",
        "---",
        "Nota: borrador generado automáticamente por el asistente de orientación. Las respuestas "
        "del asistente no reemplazan la resolución oficial de la institución. Revise y complete "
        "los campos entre corchetes antes de enviarlo.",
    ]
    return "\n".join(lineas)


def generar_borrador(preguntas: list[str], citas: list[dict],
                     carpeta: str = CARPETA_BORRADORES, ahora: datetime | None = None) -> dict | None:
    """
    Escribe el borrador en un archivo de texto. Devuelve {"texto", "ruta"}, o None si
    no hay preguntas con las que armarlo.
    """
    if not any(p.strip() for p in preguntas):
        return None
    ahora = ahora or datetime.now()
    texto = construir_borrador(preguntas, citas, ahora.strftime("%d-%m-%Y"))
    ruta = Path(carpeta) / f"derivacion_{ahora.strftime('%Y%m%d_%H%M%S')}.txt"
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(texto, encoding="utf-8")
    return {"texto": texto, "ruta": str(ruta)}