"""
Agente con planificación (EP2, IE5): planificar -> ejecutar -> responder.

1. Planificar: el LLM decide fuentes, orden y consulta de cada paso (planner.py).
2. Ejecutar: el código llama a las herramientas según el plan, siempre igual.
3. Responder: el LLM redacta con todo el contexto reunido.

Citas: cada fragmento recuperado recibe una marca ([F1], [F2]...). El modelo solo
escribe la marca; el código la reemplaza por el documento y la página reales del
fragmento. Así el modelo no puede inventar ni mezclar números de página.

Uso:
    python -m src.agent.agente_planificado "Suspendí un semestre, ¿eso afecta mi gratuidad?"
"""

import re
import sys
import time
from dotenv import load_dotenv
from langchain_groq import ChatGroq

from src.agent.prompts import SYSTEM_PROMPT
from src.agent.planner import crear_plan, Plan
from src.tools.consulta_duoc import buscar_duoc
from src.tools.consulta_mineduc import buscar_mineduc
from src.tools.calculo_cobro import fragmento_de_calculo, nota_lectura_alternativa
from src.tools.redactar_derivacion import generar_borrador, CARPETA_BORRADORES
from src.memory.largo_plazo import formatear_recuperados

load_dotenv()

MODELO_LLM = "openai/gpt-oss-120b"

BUSCADORES = {
    "duoc": buscar_duoc,
    "mineduc": buscar_mineduc,
}

# Presupuesto de fragmentos por pregunta, repartido entre los pasos del plan:
# 20 con un paso, 10 con dos, 6 con tres. Los puestos medidos con probar_consultas.py
# para las frases buscadas fueron 18, 13, 10, 16, 4, 18, 20, 1, 11, 8, 12, 11 y 1;
# con 20 fragmentos quedan dentro 12 de las 13 mediciones. Contrapartida: más
# fragmentos significan más tokens (límite del tier gratuito de Groq) y más ruido.
TOTAL_FRAGMENTOS = 20
MIN_FRAGMENTOS_POR_PASO = 4

# El Decreto 333 tiene muchos artículos parecidos entre sí. Medido con
# probar_consultas.py: una consulta larga que mezcla conceptos dejó el Artículo 40
# y el párrafo del reintegro en los puestos 18 y 13; consultas cortas de un solo
# concepto los dejaron en los puestos 4 y 1. Por eso el planificador genera un paso
# por concepto y cada paso de Mineduc trae al menos 6 fragmentos. Es una medición
# sobre un solo escenario y no garantiza el resultado en otros.
MIN_FRAGMENTOS_MINEDUC = 6

# Reintentos ante el límite de tokens por minuto del tier gratuito de Groq (error 429).
INTENTOS_MAXIMOS = 3
ESPERA_MAXIMA_S = 30
_PATRON_ESPERA = re.compile(r"try again in (?:(\d+)m)?([\d.]+)(ms|s)\b")


def _segundos_de_espera(texto_error: str) -> float:
    """Lee del mensaje de Groq cuánto hay que esperar ("try again in 2.7s") y suma un margen."""
    m = _PATRON_ESPERA.search(texto_error)
    if not m:
        return 5.0
    minutos = int(m.group(1) or 0)
    valor = float(m.group(2))
    segundos = valor / 1000 if m.group(3) == "ms" else valor
    return minutos * 60 + segundos + 0.5


class _ConReintento:
    """Envuelve un LLM y reintenta cuando Groq responde con límite de tasa (429)."""

    def __init__(self, llm, intentos: int = INTENTOS_MAXIMOS):
        self._llm = llm
        self._intentos = intentos

    def invoke(self, mensajes):
        for intento in range(1, self._intentos + 1):
            try:
                return self._llm.invoke(mensajes)
            except Exception as error:
                texto = str(error)
                es_limite = "429" in texto or "rate_limit" in texto
                if not es_limite or intento == self._intentos:
                    raise
                espera = _segundos_de_espera(texto)
                if espera > ESPERA_MAXIMA_S:
                    raise   # esperas largas: mejor avisar que dejar el programa colgado
                print(f"  [Groq alcanzó su límite por minuto; reintentando en {espera:.1f} s]")
                time.sleep(espera)


# Temperatura 0 en el planificador: la misma pregunta debe producir el mismo plan.
_llm_planificador = _ConReintento(ChatGroq(model=MODELO_LLM, temperature=0, max_tokens=2000))
_llm_respuesta = _ConReintento(ChatGroq(model=MODELO_LLM, temperature=0.2, max_tokens=2000))

NOTA_RESPUESTA_CORTADA = (
    "\n\n[La respuesta se cortó por el límite de longitud. "
    "Pídeme que continúe o reformula la pregunta de forma más específica.]"
)

MENSAJE_FUERA_DE_ALCANCE = (
    "Soy el asistente de orientación del Departamento de Admisión y Financiamiento "
    "de Duoc UC. Puedo ayudarte con el reglamento académico y con beneficios estatales "
    "como la gratuidad y el FUAS. ¿Qué te gustaría consultar?"
)

MENSAJE_SIN_CONTEXTO_PARA_BORRADOR = (
    "Todavía no tengo una consulta tuya en esta sesión para armar el borrador. "
    "Hazme primero tu pregunta sobre el reglamento o los beneficios y luego pídeme la solicitud."
)

NORMATIVOS = {"simple", "mixta", "multietapa"}   # tipos de plan que producen una respuesta normativa


class EstadoSesion:
    """Lo que la herramienta de escritura necesita recordar de la sesión en curso."""

    def __init__(self):
        self.preguntas: list[str] = []
        self.citas: list[dict] = []

    def registrar(self, pregunta: str, citas: list[dict]) -> None:
        self.preguntas.append(pregunta)
        vistas = {(c["fuente"], c.get("pagina")) for c in self.citas}
        for cita in citas:
            clave = (cita["fuente"], cita.get("pagina"))
            if clave not in vistas:
                vistas.add(clave)
                self.citas.append({"fuente": cita["fuente"], "pagina": cita.get("pagina")})


def _mensaje_de_borrador(estado) -> str:
    """Genera el borrador con la plantilla fija (sin LLM) y arma el mensaje para el estudiante."""
    if estado is None or not estado.preguntas:
        return MENSAJE_SIN_CONTEXTO_PARA_BORRADOR
    borrador = generar_borrador(estado.preguntas, estado.citas, carpeta=CARPETA_BORRADORES)
    return (
        f"Generé un borrador de solicitud para la oficina de financiamiento y lo guardé en: {borrador['ruta']}\n\n"
        f"{borrador['texto']}"
    )


INSTRUCCIONES_RESPUESTA = """

INSTRUCCIONES PARA ESTA RESPUESTA:
- El contexto viene organizado por pasos de un plan. Intégralo: si hay pasos de distintas fuentes, usa lo que dice cada una.
- Cada afirmación debe estar respaldada por un fragmento. No deduzcas consecuencias que el texto no indique.
- Antes de citar una disposición, verifica que aplique al caso preguntado. Si pertenece a un régimen especial (por ejemplo, la Ley 21.790 de maternidad, paternidad o cuidado de dependientes), no la apliques a casos generales.
- Si hay un procedimiento o cálculo, sigue los pasos tal como aparecen en los fragmentos, sin agregar pasos ni omitir mínimos o excepciones marcados como importantes.
- Si un paso no trajo información que responda la pregunta, dilo claramente en vez de completarlo por tu cuenta.
- Si un fragmento termina cortado a media frase, no completes la frase por tu cuenta: indica que el texto recuperado está incompleto.
- Menciona la restricción sobre datos personales solo si el estudiante entregó datos personales.
- Si hay un HISTORIAL RECIENTE, úsalo solo para entender a qué se refiere el estudiante. Las afirmaciones normativas deben salir del contexto recuperado, nunca de respuestas anteriores del asistente.
- Distingue a quién afecta cada disposición (el estudiante, la institución o la Subsecretaría) y no traslades al estudiante efectos que la norma establece para la institución.
- Cuando no encuentres algo, di que "en los fragmentos recuperados no aparece"; nunca afirmes que el documento "no lo menciona" o "no lo indica".
- CITAS: cada fragmento del contexto tiene una marca como [F3]. Para respaldar una afirmación, escribe esa marca al final de la frase, por ejemplo [F3] o [F3, F5]. No escribas números de página ni nombres de documento como cita: el sistema reemplaza las marcas por la fuente exacta. Esta regla reemplaza el formato de cita indicado antes.
- Si hay un fragmento de cálculo, usa sus cifras tal cual, sin recalcular ni redondear, y conserva sus advertencias: es un tope máximo y no el cobro efectivo, y cuando el fragmento muestra dos lecturas del artículo, preséntalas las dos sin elegir una.
- Regla específica de este caso (ambigüedad del Decreto 333): el Artículo 35 distingue las suspensiones de un semestre (se considera el 50% de los recursos) de las suspensiones anuales (no se consideran en la fórmula), pero el Artículo 34 no define qué es una suspensión anual. No afirmes que dos semestres son una suspensión anual ni les apliques el 50%: di que la norma no lo especifica.
- No agregues calificativos que el texto no tenga, como "definitiva", "automática" o "total".
- No uses "normalmente", "generalmente" ni "suele" para completar lo que el texto no dice. Si una frase es ambigua o no especifica algo, cítala tal cual y señala que es ambigua o que no lo especifica.
- No agregues un resumen ni una conclusión práctica que vaya más allá de lo que dicen los fragmentos. Si los fragmentos no permiten concluir qué le pasa al estudiante, dilo y señala qué información faltó.
- Sé conciso: no repitas la información en una tabla o resumen final, y evita pasarte de unas 250 palabras salvo que haya un procedimiento largo.
"""


def fragmentos_por_paso(n_pasos: int, fuente: str = "duoc") -> int:
    """Reparte el presupuesto de fragmentos entre los pasos; Mineduc tiene un mínimo mayor."""
    k = max(MIN_FRAGMENTOS_POR_PASO, TOTAL_FRAGMENTOS // max(n_pasos, 1))
    if fuente == "mineduc":
        k = max(k, MIN_FRAGMENTOS_MINEDUC)
    return k


def ejecutar_plan(plan: Plan) -> list[dict]:
    """
    Ejecuta los pasos en orden. Cada fragmento (recuperado o calculado) recibe una
    marca única (F1, F2...). El presupuesto de fragmentos se reparte solo entre los
    pasos de consulta.
    """
    consultas = sum(1 for p in plan.pasos if p.fuente != "calculo")
    resultados = []
    contador = 0
    for paso in plan.pasos:
        if paso.fuente == "calculo":
            fragmentos = [fragmento_de_calculo(paso.parametros)]
        else:
            k = fragmentos_por_paso(consultas, paso.fuente)
            fragmentos = BUSCADORES[paso.fuente](paso.consulta, k=k)
        for fragmento in fragmentos:
            contador += 1
            fragmento["id"] = f"F{contador}"
        resultados.append({
            "orden": paso.orden,
            "fuente": paso.fuente,
            "consulta": paso.consulta,
            "fragmentos": fragmentos,
        })
    return resultados


def _etiqueta(fragmento: dict) -> str:
    """'Documento, página N'; sin página (por ejemplo en un cálculo) solo el nombre."""
    pagina = fragmento.get("pagina")
    if pagina in (None, ""):
        return fragmento["fuente"]
    return f"{fragmento['fuente']}, página {pagina}"


def _formatear_paso(resultado: dict) -> str:
    if resultado["fragmentos"]:
        cuerpo = "\n\n".join(
            f"[{f['id']} | {_etiqueta(f)}]\n{f['texto']}"
            for f in resultado["fragmentos"]
        )
    else:
        cuerpo = "No se encontraron fragmentos relevantes en esta fuente."
    return f"### Paso {resultado['orden']} — fuente: {resultado['fuente']} — consulta: {resultado['consulta']}\n{cuerpo}"


# Acepta [F3], (F3), 【F3】, ［F3］, （F3）, listas como [F3, F5] y sufijos como 【F3†L2-L4】.
_ABRE = r"[\[(【（［]"
_CIERRA = r"[\])】）］]"
_PATRON_CITA = re.compile(
    _ABRE + r"\s*(F\d+(?:\s*[,;，、]\s*F\d+)*)(?:\s*†[^\])】）］]*)?\s*" + _CIERRA
)
# Dos citas seguidas se unen en una sola, sin repetir fuentes.
_PAR_DE_CITAS = re.compile(r"\((?:Fuente|Fuentes): ([^)]*)\)[ \t]*\((?:Fuente|Fuentes): ([^)]*)\)")
# El modelo suele pegar la marca al texto ("institucionales【F3】"): se separa con un espacio.
_PEGADA_AL_TEXTO = re.compile(r"(?<=[^\s(])\((Fuentes?:)")


def _rotular(etiquetas: list[str]) -> str:
    unicas: list[str] = []
    for etiqueta in etiquetas:
        if etiqueta not in unicas:
            unicas.append(etiqueta)
    rotulo = "Fuente" if len(unicas) == 1 else "Fuentes"
    return f"({rotulo}: {'; '.join(unicas)})"


def _unir_citas_adyacentes(texto: str) -> str:
    while True:
        nuevo = _PAR_DE_CITAS.sub(
            lambda m: _rotular(m.group(1).split("; ") + m.group(2).split("; ")), texto
        )
        if nuevo == texto:
            return nuevo
        texto = nuevo


def resolver_citas(texto: str, resultados: list[dict]) -> tuple[str, list[dict]]:
    """
    Reemplaza las marcas [F#] por (Fuente: documento, página N) usando los datos
    reales del fragmento. Las marcas que no existen quedan como "[cita no verificada]".
    Devuelve el texto y los fragmentos citados, en orden de aparición.
    """
    por_id = {f["id"]: f for r in resultados for f in r["fragmentos"]}
    citados: dict[str, dict] = {}

    def reemplazar(coincidencia):
        ids = re.findall(r"F\d+", coincidencia.group(1))
        validos = [por_id[i] for i in ids if i in por_id]
        if not validos:
            return "[cita no verificada]"
        etiquetas = []
        for f in validos:
            citados.setdefault(f["id"], f)
            etiqueta = _etiqueta(f)
            if etiqueta not in etiquetas:
                etiquetas.append(etiqueta)
        return _rotular(etiquetas)

    resuelto = _unir_citas_adyacentes(_PATRON_CITA.sub(reemplazar, texto))
    resuelto = _PEGADA_AL_TEXTO.sub(r" (\1", resuelto)
    return resuelto, list(citados.values())


def _menciona_lectura_por_tramos(respuesta: str, datos: dict) -> bool:
    """
    La respuesta ya explica la lectura por tramos si usa esa palabra o si escribe el
    porcentaje que resulta de esa lectura (por ejemplo "75 %" o "66,7%").
    """
    if "tramos" in respuesta.lower():
        return True
    porcentaje = datos["por_tramos"]["porcentaje"]
    for entero in {int(porcentaje), round(porcentaje)}:
        if re.search(rf"(?<!\d){entero}(?:[.,]\d+)?\s*%", respuesta):
            return True
    return False


def notas_de_lecturas(resultados: list[dict], respuesta: str) -> tuple[list[str], list[dict]]:
    """
    Si un cálculo tiene dos lecturas y la respuesta no menciona la de tramos, devuelve la
    nota fija correspondiente y el fragmento de cálculo que la respalda. Evita que el
    modelo elija una lectura en silencio.
    """
    notas, usados = [], []
    for resultado in resultados:
        for fragmento in resultado["fragmentos"]:
            datos = fragmento.get("datos")
            if datos and datos.get("por_tramos") and not _menciona_lectura_por_tramos(respuesta, datos):
                notas.append(nota_lectura_alternativa(datos))
                usados.append(fragmento)
    return notas, usados


def pie_de_fuentes(citados: list[dict]) -> str:
    """Lista final de documentos y páginas efectivamente citados (vacía si no hubo citas)."""
    if not citados:
        return ""
    paginas: dict[str, list] = {}
    for f in citados:
        lista = paginas.setdefault(f["fuente"], [])
        pagina = f.get("pagina")
        if pagina not in (None, "") and pagina not in lista:
            lista.append(pagina)
    partes = []
    for documento, lista in paginas.items():
        numeros = sorted(p for p in lista if isinstance(p, int))
        otras = [str(p) for p in lista if not isinstance(p, int)]
        todas = [str(n) for n in numeros] + otras
        if not todas:
            partes.append(documento)
        else:
            palabra = "página" if len(todas) == 1 else "páginas"
            partes.append(f"{documento}, {palabra} {', '.join(todas)}")
    return "\n\nFuentes citadas: " + "; ".join(partes)


def redactar_respuesta(pregunta: str, resultados: list[dict], historial: str = "") -> tuple[str, bool]:
    bloques = "\n\n".join(_formatear_paso(r) for r in resultados)
    mensaje = f"PREGUNTA DEL ESTUDIANTE:\n{pregunta}\n\n"
    if historial:
        mensaje += f"HISTORIAL RECIENTE (solo para entender referencias, no es fuente de normas):\n{historial}\n\n"
    mensaje += f"CONTEXTO RECUPERADO (por paso del plan):\n{bloques}"
    respuesta = _llm_respuesta.invoke([
        {"role": "system", "content": SYSTEM_PROMPT + INSTRUCCIONES_RESPUESTA},
        {"role": "user", "content": mensaje},
    ])
    metadatos = getattr(respuesta, "response_metadata", None) or {}
    return respuesta.content, metadatos.get("finish_reason") == "length"


def responder_con_traza(pregunta: str, memoria=None, estado=None, largo_plazo=None) -> dict:
    """
    Devuelve la respuesta junto con el plan y los pasos ejecutados (evidencia).

    - memoria: MemoriaCortoPlazo; historial de la sesión actual.
    - estado: EstadoSesion; lo que necesita la herramienta de escritura.
    - largo_plazo: MemoriaLargoPlazo; conversaciones anteriores del usuario, recuperadas
      por similitud semántica.
    """
    historial = memoria.texto() if memoria is not None else ""
    recuperados: list[dict] = []
    if largo_plazo is not None:
        recuperados = largo_plazo.recuperar(pregunta, excluir_sesion=getattr(memoria, "session_id", None))
    bloque_previo = formatear_recuperados(recuperados)
    contexto = f"{historial}\n\n{bloque_previo}" if historial and bloque_previo else (historial or bloque_previo)

    plan = crear_plan(pregunta, _llm_planificador, contexto)

    citados: list[dict] = []
    cortada = False
    texto_crudo = None   # lo que escribió el modelo, antes de resolver las citas
    if plan.tipo == "fuera_de_alcance":
        resultados = []
        respuesta = MENSAJE_FUERA_DE_ALCANCE
    elif plan.tipo == "redactar":
        resultados = []
        respuesta = _mensaje_de_borrador(estado)
    else:
        resultados = ejecutar_plan(plan)
        texto, cortada = redactar_respuesta(pregunta, resultados, contexto)
        texto_crudo = texto
        respuesta, citados = resolver_citas(texto, resultados)
        if cortada:
            respuesta += NOTA_RESPUESTA_CORTADA
        notas, usados = notas_de_lecturas(resultados, respuesta)
        for nota in notas:
            respuesta += "\n\n" + nota
        ya_citados = {f["id"] for f in citados}
        citados += [f for f in usados if f["id"] not in ya_citados]
        respuesta += pie_de_fuentes(citados)

    if plan.tipo in NORMATIVOS:
        if estado is not None:
            estado.registrar(pregunta, citados)
        if largo_plazo is not None:
            largo_plazo.guardar_turno(getattr(memoria, "session_id", None), pregunta, respuesta)

    if memoria is not None:
        memoria.guardar("user", pregunta)
        memoria.guardar("assistant", respuesta)

    citas = [{"id": f["id"], "fuente": f["fuente"], "pagina": f["pagina"]} for f in citados]
    return {
        "respuesta": respuesta, "plan": plan, "resultados": resultados, "citas": citas,
        "cortada": cortada, "recuperados": recuperados, "texto_crudo": texto_crudo,
    }


def responder(pregunta: str, memoria=None) -> str:
    return responder_con_traza(pregunta, memoria)["respuesta"]


if __name__ == "__main__":
    pregunta_prueba = " ".join(sys.argv[1:]) or "Suspendí un semestre, ¿eso afecta mi gratuidad?"
    print(f"Pregunta: {pregunta_prueba}\n")

    salida = responder_con_traza(pregunta_prueba)
    plan = salida["plan"]
    print(f"Plan: {plan.tipo} — {plan.motivo}")
    for paso in plan.pasos:
        print(f"  {paso.orden}. [{paso.fuente}] {paso.consulta}")
    print()
    print(salida["respuesta"])