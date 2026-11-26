"""Utilidades de config de las acciones: fechas y extensiones.

Se validan aqui, no en el parser de argparse: el parser solo sabe de texto
y banderas; quien conoce el formato de fecha o la semantica de `--extension`
es la capa de acciones, que es la que puede explicar el error en humano.
"""

from pathlib import Path

from ..excepciones import ErrorDeUso
from ..presentacion.consola import fecha_valida


def ruta_no_vacia(texto, bandera):
    """String de ruta del usuario, rechazando el vacio o los espacios sueltos.

    `Path("")` es `.`: una bandera de ruta vacia haria leer o mover en el
    directorio actual sin que nadie lo pidiera. La fabrica valida antes de
    tocar disco, asi que el hueco natural es aqui (misma filosofia que
    `parsear_fecha`).
    """
    if texto is None:
        return texto
    if not str(texto).strip():
        raise ErrorDeUso("{} no puede ser vacio.".format(bandera))
    return texto


def ruta_de(texto, bandera):
    """`Path` absoluto desde el texto del usuario, con el vacio rechazado."""
    return Path(ruta_no_vacia(texto, bandera)).resolve()


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
