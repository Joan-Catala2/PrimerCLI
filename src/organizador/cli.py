"""cli.py: parser de argumentos y despacho a la accion correspondiente.

Toda la logica vive en acciones/ (una clase por comando), la E/S en
presentacion/, la persistencia en registro.py y el motor en organizador.py.
"""

import argparse
import sys

from . import __version__
from .acciones import Acciones
from .excepciones import OrganizadorError
from .presentacion import error_json
from .presentacion.consola import Consola
from .registro import CARPETA_LOGS

CARPETA_SUGERIDA = "descargas"


def _construir_parser():
    """Parser de argumentos: solo estructura, ninguna decision de negocio."""
    parser = argparse.ArgumentParser(
        prog="organizador",
        description="Organiza archivos descargados por asignatura y tema "
        "usando solo el nombre del archivo.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="organizador {}".format(__version__),
    )
    sub = parser.add_subparsers(dest="accion")

    ejecutar = sub.add_parser("ejecutar", help="organiza una carpeta de origen")
    ejecutar.add_argument(
        "origen",
        nargs="?",
        default=CARPETA_SUGERIDA,
        help="carpeta con los archivos a organizar (por defecto: %(default)s)",
    )
    ejecutar.add_argument(
        "--salida",
        default="Organizado",
        help="carpeta de destino (por defecto: %(default)s)",
    )
    ejecutar.add_argument(
        "--seco",
        action="store_true",
        help="no muestra detalle de cada archivo, solo el resumen",
    )
    ejecutar.add_argument(
        "--simular",
        action="store_true",
        help="muestra qué haría sin mover ningún archivo",
    )
    ejecutar.add_argument(
        "--log",
        default=None,
        help="guarda un unico log en esta ruta (por defecto: historial en {}/)".format(
            CARPETA_LOGS
        ),
    )
    ejecutar.add_argument(
        "--logs-dir",
        default=CARPETA_LOGS,
        help="carpeta del historial de logs (por defecto: %(default)s)",
    )
    ejecutar.add_argument(
        "--reglas",
        default=None,
        help="fichero de reglas a usar (sustituye a las del paquete)",
    )
    ejecutar.add_argument(
        "--recursivo",
        action="store_true",
        help="recorre también las subcarpetas del origen",
    )
    ejecutar.add_argument(
        "--extension",
        action="append",
        default=[],
        metavar="EXT",
        help="solo procesa estas extensiones (repetible o separado por comas)",
    )
    ejecutar.add_argument(
        "--excluir",
        action="append",
        default=[],
        metavar="PATRON",
        help="no procesa archivos que casen con este patrón glob (repetible)",
    )
    ejecutar.add_argument(
        "--desde",
        default=None,
        metavar="YYYY-MM-DD",
        help="solo procesa archivos modificados desde esa fecha",
    )
    ejecutar.add_argument(
        "--confirmar",
        action="store_true",
        help="muestra el plan y pide confirmación antes de mover",
    )
    ejecutar.add_argument(
        "--json",
        action="store_true",
        help="emite el resumen en JSON (sin salida humana)",
    )

    revisar = sub.add_parser("revisar", help="lista los archivos pendientes de revisar")
    revisar.add_argument(
        "--salida",
        default="Organizado",
        help="carpeta de destino (por defecto: %(default)s)",
    )
    revisar.add_argument(
        "--interactivo",
        action="store_true",
        help="pregunta asignatura y tema para recolocar cada archivo",
    )
    revisar.add_argument(
        "--reglas",
        default=None,
        help="fichero de reglas a usar (sustituye a las del paquete)",
    )
    revisar.add_argument(
        "--json",
        action="store_true",
        help="emite la lista en JSON (sin salida humana)",
    )

    deshacer_parser = sub.add_parser(
        "deshacer", help="revierte los movimientos del ultimo log"
    )
    deshacer_parser.add_argument(
        "--log",
        default=None,
        help="revierte un unico log en esta ruta",
    )
    deshacer_parser.add_argument(
        "--logs-dir",
        default=CARPETA_LOGS,
        help="carpeta del historial de logs (por defecto: %(default)s)",
    )
    deshacer_parser.add_argument(
        "--ultimos",
        type=int,
        default=1,
        metavar="N",
        help="revierte los N logs mas recientes (por defecto: %(default)s)",
    )
    deshacer_parser.add_argument(
        "--listar",
        action="store_true",
        help="muestra el historial sin revertir nada",
    )
    deshacer_parser.add_argument(
        "--simular",
        action="store_true",
        help="muestra qué devolvería sin mover nada ni borrar logs",
    )
    deshacer_parser.add_argument(
        "--json",
        action="store_true",
        help="emite el resumen en JSON (sin salida humana)",
    )

    reglas_parser = sub.add_parser(
        "reglas", help="lista asignaturas y temas disponibles"
    )
    reglas_parser.add_argument(
        "--reglas",
        default=None,
        help="fichero de reglas a usar (sustituye a las del paquete)",
    )

    sugerir = sub.add_parser(
        "sugerir",
        help="propone destinos para _revision con IA o con las reglas locales",
    )
    sugerir.add_argument(
        "--salida",
        default="Organizado",
        help="carpeta de destino (por defecto: %(default)s)",
    )
    sugerir.add_argument(
        "--reglas",
        default=None,
        help="fichero de reglas a usar (sustituye a las del paquete)",
    )
    sugerir.add_argument(
        "--logs-dir",
        default=CARPETA_LOGS,
        help="carpeta del historial si se aplican propuestas",
    )
    sugerir.add_argument(
        "--aplicar",
        action="store_true",
        help="mueve las propuestas despues de confirmar (requiere --confirmar)",
    )
    sugerir.add_argument(
        "--confirmar",
        action="store_true",
        help="muestra el plan y pide confirmación antes de mover",
    )
    sugerir.add_argument(
        "--json",
        action="store_true",
        help="emite las propuestas en JSON (sin salida humana)",
    )

    explicar = sub.add_parser(
        "explicar", help="explica por qué un nombre acaba en un destino"
    )
    explicar.add_argument("nombre", help="nombre del archivo (o su ruta)")
    explicar.add_argument(
        "--salida",
        default="Organizado",
        help="carpeta de destino (por defecto: %(default)s)",
    )
    explicar.add_argument(
        "--reglas",
        default=None,
        help="fichero de reglas a usar (sustituye a las del paquete)",
    )
    explicar.add_argument(
        "--json",
        action="store_true",
        help="emite la explicación en JSON (sin salida humana)",
    )

    aplicar = sub.add_parser(
        "aplicar",
        help="aprende alias de los archivos de _revision y, opcionalmente, "
        "reorganiza con ellos",
    )
    aplicar.add_argument(
        "--salida",
        default="Organizado",
        help="carpeta de destino (por defecto: %(default)s)",
    )
    aplicar.add_argument(
        "--reglas",
        default=None,
        help="fichero de reglas a usar (sustituye a las del paquete)",
    )
    aplicar.add_argument(
        "--logs-dir",
        default=CARPETA_LOGS,
        help="carpeta del historial de logs si se reorganiza (por defecto: %(default)s)",
    )
    aplicar.add_argument(
        "--confirmar",
        action="store_true",
        help="pregunta alias a alias y guarda los aceptados en las reglas del usuario",
    )
    aplicar.add_argument(
        "--reorganizar",
        action="store_true",
        help="tras guardar alias, mueve lo clasificable (requiere --confirmar)",
    )
    aplicar.add_argument(
        "--seco",
        action="store_true",
        help="solo muestra el resumen final, sin detalle",
    )
    aplicar.add_argument(
        "--json",
        action="store_true",
        help="emite las propuestas y el resultado en JSON (sin salida humana)",
    )

    verificar = sub.add_parser(
        "verificar",
        help="audita el estado de la salida: duplicados, vacios y catalogo",
    )
    verificar.add_argument(
        "--salida",
        default="Organizado",
        help="carpeta a auditar (por defecto: %(default)s)",
    )
    verificar.add_argument(
        "--reglas",
        default=None,
        help="fichero de reglas a usar (sustituye a las del paquete)",
    )
    verificar.add_argument(
        "--logs-dir",
        default=CARPETA_LOGS,
        help="carpeta del historial de logs (por defecto: %(default)s)",
    )
    verificar.add_argument(
        "--podar",
        action="store_true",
        help="borra los duplicados conservando la primera copia (log deshacible)",
    )
    verificar.add_argument(
        "--confirmar",
        action="store_true",
        help="poda sin preguntar (exige --podar)",
    )
    verificar.add_argument(
        "--seco",
        action="store_true",
        help="solo muestra el resumen final, sin detalle",
    )
    verificar.add_argument(
        "--json",
        action="store_true",
        help="emite la auditoria en JSON (sin salida humana)",
    )

    return parser


def _detectar_json(argv):
    """True si el argv pide `--json`, aunque todavia no este parseado.

    La entrada real (`organizador ...` y `python -m organizador ...`) llama a
    `main()` sin argumentos: argparse lee `sys.argv`, asi que aqui hay que
    hacer lo mismo para que un error en modo JSON siga siendo JSON.
    """
    if argv is None:
        argv = sys.argv[1:]
    return "--json" in argv


def main(argv=None):
    """Punto de entrada: parsea, construye la accion y la ejecuta.

    Los `OrganizadorError` (reglas malas, fechas invalidas, origen
    inexistente...) se imprimen como mensaje humano, sin traceback, y
    devuelven el codigo de salida de cada error. En modo `--json` el error
    se emite como un objeto JSON valido (`ok: false`) para que un script
    nunca reciba texto plano donde espera JSON. El resto de excepciones no
    capturadas se dejan pasar: un traceback ante un bug real es intencionado.
    """
    try:
        args = _construir_parser().parse_args(argv)
        consola = Consola.desde_config(args)
        # La fabrica resuelve dependencias (reglas, registro) y rechaza
        # configuraciones imposibles antes de tocar el disco.
        return Acciones.desde_config(args, consola).ejecutar()
    except OrganizadorError as error:
        if _detectar_json(argv):
            error_json(error)
        else:
            Consola().error_humano(error)
        return error.codigo_salida


if __name__ == "__main__":
    sys.exit(main())
