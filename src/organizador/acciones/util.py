"""Utilidades de config de las acciones: fechas y extensiones.

Se validan aqui, no en el parser de argparse: el parser solo sabe de texto
y banderas; quien conoce el formato de fecha o la semantica de `--extension`
es la capa de acciones, que es la que puede explicar el error en humano.
"""

from ..excepciones import ErrorDeUso
from ..presentacion.consola import fecha_valida


def parsear_fecha(texto):
    """datetime desde `--desde`, o None si no se pidio fecha."""
    if texto is None:
        return None
    fecha = fecha_valida(texto)
    if fecha is None:
        raise ErrorDeUso("fecha inválida '{}': usa el formato YYYY-MM-DD".format(texto))
    return fecha


def extensiones_de(valores):
    """Aplana --extension aceptando repeticiones y listas separadas por comas."""
    extensiones: list = []
    for valor in valores or ():
        extensiones.extend(parte for parte in valor.split(",") if parte.strip())
    return extensiones
