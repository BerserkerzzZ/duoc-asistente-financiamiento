"""
Planificador (IE5): antes de consultar nada, una primera llamada al LLM decide
QUÉ fuentes consultar, EN QUÉ ORDEN y con QUÉ consulta para cada paso.

El enrutamiento deja de depender de que el modelo "se acuerde" de usar una
herramienta: el plan es un dato estructurado y el código lo ejecuta tal cual.

Tipos de plan:
- simple: basta una fuente.
- mixta: trámite académico + beneficio estatal; exige las dos fuentes.
- multietapa: varios hechos o preguntas en secuencia; un paso por cada uno.
- fuera_de_alcance: saludos o temas ajenos; no se consulta nada.
- redactar: el estudiante pide que se le redacte una solicitud para la oficina; no se consulta nada.

Además de consultar las fuentes ("duoc", "mineduc"), un paso puede ser un cálculo
determinista ("calculo", tope de cobro por exceder la duración nominal). Sus números
solo se aceptan si aparecen en lo que escribió el estudiante.
"""

import json
import re
from pydantic import BaseModel, Field, ValidationError

MAX_PASOS = 5
PALABRAS_BENEFICIO = ("gratuidad", "fuas", "beca", "beneficio")
FUENTES_CONSULTA = {"duoc", "mineduc"}
FUENTES_VALIDAS = FUENTES_CONSULTA | {"calculo"}
TIPOS_VALIDOS = {"simple", "mixta", "multietapa", "fuera_de_alcance", "redactar"}
TIPOS_SIN_PASOS = {"fuera_de_alcance", "redactar"}


class Paso(BaseModel):
    orden: int
    fuente: str
    consulta: str = ""
    parametros: dict = Field(default_factory=dict)   # solo para pasos de "calculo"


class Plan(BaseModel):
    tipo: str
    motivo: str = ""
    pasos: list[Paso] = Field(default_factory=list)
    crudo: str = ""   # salida del planificador cuando no se pudo interpretar (para diagnóstico)


PROMPT_PLANIFICADOR = """Eres el planificador de un asistente de Duoc UC sobre normativa académica y beneficios estudiantiles. Tu tarea es decidir qué fuentes consultar. NO respondes la pregunta.

Fuentes disponibles:
- "duoc": Reglamento Académico de Duoc UC (suspensión de estudios, renuncia, cambio de carrera, convalidación, eliminación, y los efectos académicos y de cobro de esos trámites).
- "mineduc": normativa estatal (Decreto 333 de gratuidad y Manual FUAS: requisitos y mantención de la gratuidad, cobros por exceso de duración, cambios de carrera con gratuidad, postulación, plazos, cálculo de ingresos).
- "calculo": cálculo determinista del tope de cobro por exceder la duración nominal de la carrera (Artículo 29 del Decreto 333). Úsalo SOLO si el estudiante pregunta cuánto le pueden cobrar por pasarse de la duración nominal Y dice cuántos semestres o años se pasó. Este paso no lleva "consulta" sino "parametros": {"semestres_de_exceso": <número entero; 1 año = 2 semestres>, "valor_periodo_adicional": <pesos, la suma del arancel y la matrícula de TODO el período adicional; inclúyelo solo si el estudiante lo dijo en su mensaje actual>}. Nunca inventes estos números. Acompaña siempre el paso "calculo" con un paso "mineduc" sobre la norma (consulta: "cobro máximo por exceder la duración nominal").

Tipos de plan:
- "fuera_de_alcance": saludos o temas ajenos a normativa y beneficios. La lista de pasos va vacía.
- "redactar": el estudiante pide EXPLÍCITAMENTE que le redactes una solicitud, carta o derivación para la oficina de financiamiento (por ejemplo "redáctame una solicitud para la oficina"). La lista de pasos va vacía. No uses este tipo si solo pregunta cómo hacer un trámite.
- "simple": basta una sola fuente. Un paso.
- "mixta": la pregunta combina un trámite académico (suspender, renunciar, cambiar de carrera, reprobar) con un beneficio estatal (gratuidad, CAE, FUAS). Es OBLIGATORIO consultar ambas fuentes: un paso "duoc" para el trámite y un paso "mineduc" para su efecto sobre el beneficio.
- "multietapa": la pregunta describe DOS O MÁS hechos en secuencia (por ejemplo "suspendí un semestre y después me cambié de carrera") o contiene varias preguntas. Tiene prioridad sobre "mixta" cuando hay varios hechos. Un paso por concepto: un paso "duoc" por cada hecho, en orden cronológico, y, si hay un beneficio estatal involucrado, un paso "mineduc" por cada hecho sobre su efecto en el beneficio. Si el estudiante suspendió y después se cambió de carrera, incluye además un paso "mineduc" sobre el reintegro a una carrera diferente tras una suspensión.

Reglas:
- Máximo 5 pasos.
- "consulta": reescribe cada paso como una consulta clara, en términos normativos y específica de ese paso (por ejemplo, "echar un ramo" se reescribe como "reprobación de asignatura y pérdida de la calidad de alumno regular"). No agregues datos que el estudiante no mencionó.
- Si recibes un HISTORIAL RECIENTE y la pregunta actual depende de él (por ejemplo "¿y si fueran dos semestres?"), reescribe cada consulta para que se entienda sin el historial, incorporando solo lo que el estudiante dijo. Si la pregunta no depende del historial, ignóralo. El historial solo sirve para entender referencias, nunca como fuente de normas.
- Cada consulta debe ser corta (unas 12 palabras como máximo) y tratar UN solo concepto. No nombres el documento ("según el Decreto 333", "según el Manual FUAS", "según el Reglamento"): la fuente ya está indicada en "fuente". Una consulta larga que mezcla varios temas recupera peor que varias consultas cortas.
- En los pasos "duoc", conserva la mención al beneficio si el estudiante la hizo (por ejemplo, "suspensión de estudios y su efecto en la gratuidad"), porque el reglamento de Duoc también describe los efectos de esos trámites sobre los beneficios.
- "orden": 1 es el primer paso. Primero lo que define el trámite o el hecho, después su efecto.

Responde SOLO con un JSON, sin texto adicional ni bloques de código, con este formato:
{"tipo": "...", "motivo": "una frase breve", "pasos": [{"orden": 1, "fuente": "duoc", "consulta": "..."}]}
Un paso de cálculo tiene esta forma: {"orden": 2, "fuente": "calculo", "parametros": {"semestres_de_exceso": 3}}"""


def plan_de_respaldo(pregunta: str, crudo: str = "", consulta: str | None = None) -> Plan:
    """Plan seguro cuando la salida del planificador no se puede interpretar."""
    texto = consulta or pregunta
    return Plan(
        tipo="mixta",
        motivo="Plan de respaldo: no se pudo interpretar la salida del planificador.",
        pasos=[
            Paso(orden=1, fuente="duoc", consulta=texto),
            Paso(orden=2, fuente="mineduc", consulta=texto),
        ],
        crudo=crudo[:600],
    )


def _normalizar_datos(datos: dict) -> dict:
    """Tolera mayúsculas, espacios y números como texto en la salida del modelo."""
    datos["tipo"] = str(datos.get("tipo", "")).strip().lower()
    datos["motivo"] = str(datos.get("motivo", ""))
    limpios = []
    for i, paso in enumerate(datos.get("pasos") or [], start=1):
        if not isinstance(paso, dict):
            continue
        try:
            orden = int(paso.get("orden", i))
        except (TypeError, ValueError):
            orden = i
        parametros = paso.get("parametros")
        limpios.append({
            "orden": orden,
            "fuente": str(paso.get("fuente", "")).strip().lower(),
            "consulta": str(paso.get("consulta", "")),
            "parametros": parametros if isinstance(parametros, dict) else {},
        })
    datos["pasos"] = limpios
    return datos


_PALABRAS_TIEMPO = re.compile(r"semestre|a[ñn]o")


def _semestres(valor) -> int | None:
    """Entero >= 1, o None si el valor no sirve."""
    if isinstance(valor, bool) or valor is None:
        return None
    try:
        numero = float(valor)
        if numero != int(numero) or numero < 1:
            return None
    except (TypeError, ValueError, OverflowError):
        return None
    return int(numero)


def _a_pesos(valor) -> float | None:
    """Acepta números y textos como '$2.400.000'; devuelve None si no hay número."""
    if isinstance(valor, bool) or valor is None:
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    digitos = re.sub(r"\D", "", str(valor))
    return float(digitos) if digitos else None


def _numeros_en(texto: str) -> set[str]:
    """Números escritos en el texto, sin separadores ('2.400.000' -> '2400000')."""
    return {re.sub(r"\D", "", m) for m in re.findall(r"\d[\d.,]*", texto)}


def _parametros_de_calculo(parametros, texto_base: str, texto_valor: str | None = None) -> dict | None:
    """
    Valida los parámetros de un paso de cálculo. Devuelve None si no sirven.
    Control contra números inventados: debe haber una mención de semestres o años en
    lo que escribió el estudiante (mensaje actual o conversación previa). El valor en
    pesos solo se acepta si aparece en `texto_valor` (el mensaje actual): la suma depende
    de cuántos semestres sean, así que no se reutiliza un monto dicho para otro caso.
    Si el valor no se acepta, se conserva el cálculo en porcentaje.
    """
    if not isinstance(parametros, dict):
        return None
    semestres = _semestres(parametros.get("semestres_de_exceso"))
    if semestres is None:
        return None
    base = texto_base.lower()
    if not _PALABRAS_TIEMPO.search(base):
        return None
    limpio = {"semestres_de_exceso": semestres}
    valor = _a_pesos(parametros.get("valor_periodo_adicional"))
    fuente_del_valor = base if texto_valor is None else texto_valor.lower()
    if valor is not None and valor > 0 and str(int(valor)) in _numeros_en(fuente_del_valor):
        limpio["valor_periodo_adicional"] = valor
    return limpio


def _beneficio_en(textos: list[str]) -> str | None:
    """Primer beneficio estatal mencionado en los textos (o None)."""
    for texto in textos:
        for palabra in PALABRAS_BENEFICIO:
            if re.search(rf"\b{palabra}s?\b", texto.lower()):
                return palabra
    return None


def _conservar_beneficio_en_duoc(plan: Plan, pregunta: str) -> None:
    """
    El reglamento de Duoc también describe el efecto de sus trámites sobre los
    beneficios. Si el estudiante o el plan hablan de un beneficio y la consulta de
    un paso "duoc" no lo menciona, se agrega. Así no depende de que el LLM lo
    recuerde en cada corrida.
    """
    beneficio = _beneficio_en([pregunta] + [p.consulta for p in plan.pasos if p.fuente == "mineduc"])
    if beneficio is None:
        return
    for paso in plan.pasos:
        if paso.fuente == "duoc" and _beneficio_en([paso.consulta]) is None:
            paso.consulta = f"{paso.consulta.rstrip('. ')} — efecto en {beneficio}"


def parsear_plan(texto, pregunta: str, consulta_respaldo: str | None = None, contexto: str = "") -> Plan:
    """
    Convierte la salida del LLM en un Plan validado.
    Si algo no cuadra (JSON roto, tipo o fuente inválidos, sin pasos), devuelve
    el plan de respaldo en vez de fallar.
    """
    texto = str(texto or "")

    def respaldo() -> Plan:
        return plan_de_respaldo(pregunta, crudo=texto, consulta=consulta_respaldo)

    try:
        datos = json.loads(texto[texto.index("{"): texto.rindex("}") + 1])
        plan = Plan(**_normalizar_datos(datos))
    except (ValueError, TypeError, AttributeError, ValidationError):
        return respaldo()

    if plan.tipo not in TIPOS_VALIDOS:
        return respaldo()

    pasos = []
    for p in plan.pasos:
        if p.fuente not in FUENTES_VALIDAS:
            continue
        if p.fuente == "calculo":
            parametros = _parametros_de_calculo(p.parametros, f"{pregunta} {contexto}", texto_valor=pregunta)
            if parametros is None:
                continue
            p.parametros = parametros
            p.consulta = p.consulta.strip() or "cálculo del tope de cobro por exceso de duración"
            pasos.append(p)
        elif p.consulta.strip():
            pasos.append(p)
    pasos.sort(key=lambda p: p.orden)
    plan.pasos = pasos[:MAX_PASOS]

    if plan.tipo in TIPOS_SIN_PASOS:
        plan.pasos = []
        return plan

    if not plan.pasos:
        return respaldo()

    # Un plan "mixta" debe consultar las dos fuentes, aunque el modelo olvide una.
    if plan.tipo == "mixta":
        presentes = {p.fuente for p in plan.pasos}
        for faltante in sorted(FUENTES_CONSULTA - presentes):
            plan.pasos.append(
                Paso(orden=len(plan.pasos) + 1, fuente=faltante, consulta=pregunta)
            )

    _conservar_beneficio_en_duoc(plan, pregunta)
    return plan


def _consulta_de_respaldo(pregunta: str, historial: str) -> str:
    """Si no hay plan, busca con las preguntas previas del estudiante más la actual."""
    previas = [
        linea[len("Estudiante: "):]
        for linea in historial.splitlines()
        if linea.startswith("Estudiante: ")
    ]
    return " ".join(previas + [pregunta]) if previas else pregunta


def crear_plan(pregunta: str, llm, historial: str = "") -> Plan:
    """Pide el plan al LLM y lo valida. Los errores de API no se ocultan."""
    if historial:
        contenido = f"HISTORIAL RECIENTE:\n{historial}\n\nPREGUNTA ACTUAL:\n{pregunta}"
    else:
        contenido = pregunta
    respuesta = llm.invoke([
        {"role": "system", "content": PROMPT_PLANIFICADOR},
        {"role": "user", "content": contenido},
    ])
    return parsear_plan(respuesta.content, pregunta, _consulta_de_respaldo(pregunta, historial), contexto=historial)