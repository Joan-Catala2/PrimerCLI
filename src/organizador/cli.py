"""Punto de entrada de la CLI `organizador`."""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from .organizador import NOMBRE_LOG, organizar
from .reglas import REVISION

CARPETA_SUGERIDA = "descargas"


def _guardar_log(origen, salida, resumen):
    """Sobrescribe el log con el resumen de la ultima ejecucion."""
    datos = {
        "fecha": datetime.now().isoformat(timespec="seconds"),
        "origen": str(origen),
        "salida": str(salida),
        "movimientos": resumen["movimientos"],
        "errores": resumen["errores"],
    }
    with open(NOMBRE_LOG, "w", encoding="utf-8") as archivo:
        json.dump(datos, archivo, indent=2, ensure_ascii=False)


def _revisar(salida):
    """Lista los archivos pendientes dentro de <salida>/_revision."""
    carpeta = salida / REVISION
    if not carpeta.is_dir():
        print("No existe la carpeta de revisión: {}".format(carpeta))
        return 0

    archivos = sorted(p for p in carpeta.iterdir() if p.is_file())
    for archivo in archivos:
        print(archivo.name)

    print()
    print("Archivos a revisar: {}".format(len(archivos)))
    return 0


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

    revisar = sub.add_parser(
        "revisar", help="lista los archivos pendientes de revisar"
    )
    revisar.add_argument(
        "--salida",
        default="Organizado",
        help="carpeta de destino (por defecto: %(default)s)",
    )

    args = parser.parse_args(argv)

    if args.accion == "revisar":
        return _revisar(Path(args.salida).resolve())

    if args.accion != "ejecutar":
        parser.print_help()
        return 1

    origen = Path(args.origen).resolve()
    salida = Path(args.salida).resolve()

    try:
        resumen = organizar(origen, salida, simular=args.simular)
    except (NotADirectoryError, ValueError, OSError) as error:
        print("Error: {}".format(error), file=sys.stderr)
        return 1

    if not args.simular:
        try:
            _guardar_log(origen, salida, resumen)
        except OSError as error:
            print(
                "Aviso: no se pudo escribir el log: {}".format(error),
                file=sys.stderr,
            )

    etiqueta = "[SIM]" if args.simular else "[OK]"

    if not args.seco:
        for movimiento in resumen["movimientos"]:
            relativo = Path(movimiento["destino"]).relative_to(salida)
            marca = "[?]" if movimiento["asignatura"] == REVISION else etiqueta
            print("{} {} -> {}".format(marca, movimiento["nombre"], relativo))

    for error in resumen["errores"]:
        print("[!] {} -> {}".format(error["nombre"], error["error"]), file=sys.stderr)

    total = len(resumen["organizados"]) + len(resumen["revision"])
    print()
    print("Resumen")
    print("  Archivos procesados: {}".format(total))
    print("  Organizados:         {}".format(len(resumen["organizados"])))
    print("  A revisar:           {}".format(len(resumen["revision"])))
    print("  Errores:             {}".format(len(resumen["errores"])))
    print("  Destino:             {}".format(salida))
    if args.simular:
        print("  Modo:                simulación (no se ha movido nada)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
