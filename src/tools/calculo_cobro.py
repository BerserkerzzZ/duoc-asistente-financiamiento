"""
Herramienta de razonamiento (IE1): tope de cobro por exceder la duración nominal.

Implementa el Artículo 29 del Decreto 333. Es un cálculo determinista, sin LLM:

  a) Si la permanencia excede en hasta un año el plazo de la obligación de la
     institución, puede cobrar hasta el 50% de la suma del arancel regulado y los
     derechos básicos de matrícula del período adicional.
  b) Si excede de un año, puede cobrar hasta el total (100%) de esa suma.

Lo que devuelve es un TOPE MÁXIMO, no el cobro efectivo: el último inciso del
artículo indica que cada institución determina el porcentaje que aplicará.

Dos puntos que el texto no resuelve y que la herramienta explicita:
- La letra b) puede leerse de forma literal (100% de todo el período adicional) o
  por tramos (50% el primer año y 100% el resto). Se calculan las dos.
- Se supone que 1 año = 2 semestres.

Los datos de entrada son valores institucionales (semestres de exceso y el valor
del arancel más la matrícula del período adicional), no datos socioeconómicos
del estudiante.
"""

SEMESTRES_POR_ANIO = 2
FUENTE_CALCULO = "Cálculo según el Artículo 29 del Decreto 333"


def _como_entero(valor) -> int:
    if isinstance(valor, bool):
        raise ValueError("semestres_de_exceso debe ser un número entero")
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        raise ValueError("semestres_de_exceso debe ser un número entero")
    if numero != int(numero):
        raise ValueError("semestres_de_exceso debe ser un número entero")
    if numero < 0:
        raise ValueError("semestres_de_exceso no puede ser negativo")
    return int(numero)


def _como_valor(valor) -> float:
    if isinstance(valor, bool):
        raise ValueError("valor_periodo_adicional debe ser un número")
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        raise ValueError("valor_periodo_adicional debe ser un número")
    if numero < 0:
        raise ValueError("valor_periodo_adicional no puede ser negativo")
    return numero


def calcular_tope_cobro_exceso(semestres_de_exceso, valor_periodo_adicional=None) -> dict:
    """
    semestres_de_exceso: semestres que el estudiante se pasó de la duración nominal.
    valor_periodo_adicional: suma del arancel regulado y los derechos básicos de
        matrícula del período adicional completo, en pesos (opcional).
    """
    n = _como_entero(semestres_de_exceso)
    valor = None if valor_periodo_adicional is None else _como_valor(valor_periodo_adicional)

    if n < 1:
        return {"aplica": False, "semestres_de_exceso": n}

    tramo = "a" if n <= SEMESTRES_POR_ANIO else "b"
    porcentaje = 50 if tramo == "a" else 100
    resultado = {
        "aplica": True,
        "semestres_de_exceso": n,
        "tramo": tramo,
        "porcentaje_tope": porcentaje,
        "valor_periodo_adicional": valor,
        "tope": None if valor is None else valor * porcentaje / 100,
        "por_tramos": None,
    }
    if tramo == "b":
        # 50% durante el primer año (2 semestres) y 100% durante el resto:
        # equivale a (n - 1) de los n semestres al 100%.
        resultado["por_tramos"] = {
            "porcentaje": (n - 1) / n * 100,
            "tope": None if valor is None else valor * (n - 1) / n,
        }
    return resultado


def _clp(valor: float) -> str:
    return "$" + f"{round(valor):,}".replace(",", ".")


def _pct(valor: float) -> str:
    """75 -> '75%'; 66.666 -> '66,7%'."""
    texto = f"{valor:.1f}"
    if texto.endswith(".0"):
        texto = texto[:-2]
    return texto.replace(".", ",") + "%"


def describir_calculo(r: dict) -> str:
    """Texto del resultado, listo para que el LLM lo cite sin recalcular."""
    if not r["aplica"]:
        return (
            "El Artículo 29 del Decreto 333 solo se aplica cuando se excede la duración "
            "nominal de la carrera. Con 0 semestres de exceso no corresponde este cálculo."
        )

    n = r["semestres_de_exceso"]
    lineas = [
        "Cálculo determinista según el Artículo 29 del Decreto 333. "
        "El resultado es un TOPE MÁXIMO, no el cobro efectivo.",
        f"Semestres de exceso sobre la duración nominal: {n} (se supone 1 año = {SEMESTRES_POR_ANIO} semestres).",
    ]
    valor = r["valor_periodo_adicional"]

    if r["tramo"] == "a":
        lineas.append(
            "El exceso es de hasta un año (letra a): la institución puede cobrar hasta el 50% "
            "de la suma del arancel regulado y los derechos básicos de matrícula del período adicional."
        )
        if valor is not None:
            lineas.append(
                f"Con un valor de {_clp(valor)} para el período adicional completo, el tope es {_clp(r['tope'])}."
            )
    else:
        lineas.append(
            "El exceso supera un año (letra b). Lectura literal del texto: la institución puede cobrar "
            "hasta el 100% de la suma del arancel regulado y los derechos básicos de matrícula "
            "del período adicional completo."
        )
        alternativa = r["por_tramos"]
        lineas.append(
            "Lectura alternativa por tramos (50% el primer año y 100% el resto): "
            f"hasta {_pct(alternativa['porcentaje'])} de esa suma. El texto no indica cuál lectura corresponde."
        )
        if valor is not None:
            lineas.append(
                f"Con un valor de {_clp(valor)} para el período adicional completo: tope con la lectura literal "
                f"{_clp(r['tope'])}; tope con la lectura por tramos {_clp(alternativa['tope'])}."
            )

    if valor is not None:
        lineas.append(
            f"Se supone que {_clp(valor)} corresponde a la suma del arancel regulado y los derechos básicos "
            f"de matrícula de todo el período adicional ({n} semestres), no de un solo semestre ni de un año."
        )
    if valor is None:
        lineas.append("No se indicó el valor del período adicional, por lo que solo se informa el porcentaje.")
    lineas.append(
        "El último inciso del artículo establece que cada institución adscrita determina el porcentaje que "
        "aplicará dentro de estos topes; ese porcentaje no está en los documentos disponibles."
    )
    return "\n".join(lineas)


def nota_lectura_alternativa(r: dict) -> str:
    """
    Frase fija con la lectura por tramos de la letra b). El agente la agrega a la respuesta
    cuando el modelo no mencionó esa lectura, para que no elija una en silencio.
    """
    if not r.get("aplica") or not r.get("por_tramos"):
        return ""
    alternativa = r["por_tramos"]
    texto = (
        "Nota del cálculo: la letra b) admite otra lectura, por tramos "
        f"(50% el primer año y 100% el resto): hasta {_pct(alternativa['porcentaje'])} de esa suma"
    )
    if alternativa["tope"] is not None:
        texto += f" ({_clp(alternativa['tope'])} con el valor indicado, frente a {_clp(r['tope'])} con la lectura literal)"
    return texto + f". (Fuente: {FUENTE_CALCULO})"


def fragmento_de_calculo(parametros: dict) -> dict:
    """Resultado del cálculo con el mismo formato que un fragmento recuperado (citable)."""
    resultado = calcular_tope_cobro_exceso(
        parametros["semestres_de_exceso"], parametros.get("valor_periodo_adicional")
    )
    return {
        "texto": describir_calculo(resultado),
        "fuente": FUENTE_CALCULO,
        "pagina": None,
        "score": 1.0,
        "datos": resultado,   # resultado estructurado, para controles posteriores
    }