"""Punto de entrada de la CLI `organizador`."""

import argparse
import sys
from pathlib import Path

from .organizador import organizar
from .reglas import REVISION

CARPETA_SUGERIDA = "descargas"


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="organizador",
        description="Organiza archivos descargados por asignatura y tema "
        "usando solo el nombre del archivo.",
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

    args = parser.parse_args(argv)

    if args.accion != "ejecutar":
        parser.print_help()
        return 1

    origen = Path(args.origen).resolve()
    salida = Path(args.salida).resolve()

    try:
        resumen = organizar(origen, salida, simular=args.simular)
    except (NotADirectoryError, OSError) as error:
        print("Error: {}".format(error), file=sys.stderr)
        return 1

    etiqueta = "[SIM]" if args.simular else "[OK]"

    if not args.seco:
        for nombre, asignatura, tema in resumen["organizados"]:
            if tema:
                print("{} {} -> {}/{}".format(etiqueta, nombre, asignatura, tema))
            else:
                print("{} {} -> {}".format(etiqueta, nombre, asignatura))
        for nombre in resumen["revision"]:
            print("[?] {} -> {}/".format(nombre, REVISION))

    total = len(resumen["organizados"]) + len(resumen["revision"])
    print()
    print("Resumen")
    print("  Archivos procesados: {}".format(total))
    print("  Organizados:         {}".format(len(resumen["organizados"])))
    print("  A revisar:           {}".format(len(resumen["revision"])))
    print("  Destino:             {}".format(salida))
    if args.simular:
        print("  Modo:                simulación (no se ha movido nada)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
