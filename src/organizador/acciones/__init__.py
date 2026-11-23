"""Acciones de la CLI: una clase por comando, con fabrica desde la config.

Patron: cada accion sabe hacer UNA cosa (organizar, revisar, deshacer,
listar reglas, ...). `Acciones.from_config` monta el mapa {nombre: Accion}
a partir de los argumentos ya parseados: aqui es donde se deciden las
dependencias (reglas efectivas, registro, consola) y se cargan una sola vez
aunque crezcan los comandos.

Anadir una accion nueva (las de IA de la v2.4 son el ejemplo) es: 1 clase
nueva + 1 linea en el registro. Ni el motor, ni la consola se tocan; el
parser solo aprende las banderas nuevas del comando.
"""

from .aplicar import AccionAplicar
from .base import Accion
from .deshacer import AccionDeshacer
from .ejecutar import AccionEjecutar
from .explicar import AccionExplicar
from .reglas import AccionReglas
from .revisar import AccionRevisar
from .sugerir import AccionSugerir

__all__ = ["Accion", "Acciones"]


class Acciones:
    """Registro de acciones disponibles, construido desde la configuracion."""

    _IMPLEMENTACIONES = {
        "ejecutar": AccionEjecutar,
        "revisar": AccionRevisar,
        "deshacer": AccionDeshacer,
        "reglas": AccionReglas,
        "sugerir": AccionSugerir,
        "explicar": AccionExplicar,
        "aplicar": AccionAplicar,
    }

    @staticmethod
    def desde_config(args, consola) -> Accion:
        """Devuelve la accion pedida, construida desde args + consola.

        Solo construye la accion elegida: montar todas obligaria a cargar
        reglas o registros que el comando elegido ni mira. El `type(...)`
        es un truco de tipado: la busqueda devuelve clases (no
        instancias), y `Accion` es la base comun de todas ellas.
        """
        from ..excepciones import AccionNoValida

        implementacion = Acciones._IMPLEMENTACIONES.get(args.accion)
        if implementacion is None:
            raise AccionNoValida(
                "acción no reconocida: '{}'. Ejecuta 'organizador --help' para "
                "ver las disponibles.".format(args.accion)
            )
        return implementacion.desde_config(args, consola)  # type: ignore[attr-defined]
