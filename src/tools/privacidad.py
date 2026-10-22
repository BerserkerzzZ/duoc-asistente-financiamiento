"""
Enmascarado de datos personales (restricción de privacidad del caso).

Se aplica antes de guardar una pregunta en la memoria de largo plazo, antes de escribirla
en un borrador y antes de registrarla como evidencia. No reemplaza una revisión humana,
pero evita que un RUT, un correo o un teléfono escritos por el estudiante queden guardados.
"""

import re

_RUT = re.compile(r"(?<![\w.])\d{1,2}\.?\d{3}\.?\d{3}\s?-\s?[\dkK](?!\w)")
_CORREO = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_TELEFONO = re.compile(r"(?<![\d.])(?:\+?56[\s-]?)?9[\s-]?\d{4}[\s-]?\d{4}(?!\d)")


def enmascarar_datos_personales(texto: str) -> str:
    """Reemplaza RUT, correos y teléfonos chilenos por marcas ([RUT], [CORREO], [TELÉFONO])."""
    texto = _RUT.sub("[RUT]", texto)
    texto = _CORREO.sub("[CORREO]", texto)
    texto = _TELEFONO.sub("[TELÉFONO]", texto)
    return texto