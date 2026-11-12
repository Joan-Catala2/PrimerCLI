"""Punto de entrada de la CLI `organizador`."""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from . import __version__
from .organizador import NOMBRE_LOG, deshacer, limpiar_vacias, mover_archivo, organizar
from .reglas import REGLAS, REVISION

CARPETA_SUGERIDA = "descargas"


def _resolver_log(ruta, origen, salida):
    """Devuelve una ruta de log que nunca cae dentro de `origen`.

    Si la ruta pedida (relativa al directorio actual) esta dentro del
    origen, se recoloca junto a la carpeta de salida para que una nueva
    pasada no la trate como archivo a organizar.
    """
    ruta = Path(ruta)
    if not ruta.is_absolute():
        ruta = Path.cwd() / ruta
    ruta = ruta.resolve()

    origen = Path(origen).resolve()
    if ruta == origen or origen in ruta.parents:
        nueva = (Path(salida).resolve().parent / ruta.name).resolve()
        print(
            "Aviso: el log se guardara fuera del origen en {}".format(nueva),
            file=sys.stderr,
        )
        return nueva
    return ruta


def _avisar_sobrescritura(ruta):
    """Avisa si ya existe un log con movimientos que se va a sobrescribir."""
    ruta = Path(ruta)
    if not ruta.is_file():
        return
    try:
        with open(ruta, encoding="utf-8") as archivo:
            datos = json.load(archivo)
        movimientos = len(datos.get("movimientos", []))
    except (OSError, json.JSONDecodeError, AttributeError):
        movimientos = 0
    if movimientos:
        print(
            "Aviso: se sobrescribira el log existente ({} movimientos). "
            "Usa --log para conservarlo.".format(movimientos),
            file=sys.stderr,
        )


def _guardar_log(origen, salida, resumen, ruta):
    """Sobrescribe el log con el resumen de la ultima ejecucion."""
    datos = {
        "fecha": datetime.now().isoformat(timespec="seconds"),
        "origen": str(origen),
        "salida": str(salida),
        "movimientos": resumen["movimientos"],
        "errores": resumen["errores"],
    }
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as archivo:
        json.dump(datos, archivo, indent=2, ensure_ascii=False)


def _revisar(salida, interactivo=False):
    """Lista (y opcionalmente recoloca) los archivos de <salida>/_revision."""
    carpeta = salida / REVISION
    if not carpeta.is_dir():
        print("No existe la carpeta de revisión: {}".format(carpeta))
        return 0

    archivos = sorted(p for p in carpeta.iterdir() if p.is_file())

    if not interactivo:
        for archivo in archivos:
            print(archivo.name)
        print()
        print("Archivos a revisar: {}".format(len(archivos)))
        return 0

    asignaturas = {regla.asignatura for regla in REGLAS}
    print("Asignaturas disponibles: {}".format(", ".join(sorted(asignaturas))))

    movidos = 0
    cancelado = False
    for numero, archivo in enumerate(archivos, start=1):
        print()
        print("[{}/{}] {}".format(numero, len(archivos), archivo.name))
        try:
            asignatura = input("Asignatura (Enter para saltar): ").strip()
            if not asignatura:
                continue
            if asignatura not in asignaturas:
                print("Asignatura no válida, se salta.")
                continue

            tema = input("Tema (opcional): ").strip()
        except EOFError:
            print()
            print("Entrada cancelada; se deja el resto en revisión.")
            cancelado = True
            break

        destino_dir = salida / asignatura
        if tema:
            destino_dir = destino_dir / tema

        destino = mover_archivo(archivo, destino_dir)
        movidos += 1
        print("Movido a {}".format(destino.relative_to(salida)))

    if movidos:
        limpiar_vacias(salida)

    print()
    print("Archivos movidos: {}".format(movidos))
    print("Pendientes:       {}".format(len(archivos) - movidos))
    return 130 if cancelado else 0


def _listar_reglas():
    """Muestra las asignaturas y temas disponibles."""
    for regla in REGLAS:
        print(regla.asignatura)
        for tema, _ in regla.temas:
            print("  - {}".format(tema))
    return 0


def _deshacer(ruta):
    """Revierte los movimientos guardados en el ultimo log."""
    try:
        with open(ruta, encoding="utf-8") as archivo:
            registro = json.load(archivo)
    except FileNotFoundError:
        print("No hay log para deshacer: {}".format(ruta))
        return 0
    except json.JSONDecodeError as error:
        print("Error: log inválido: {}".format(error), file=sys.stderr)
        return 1

    if not isinstance(registro, dict):
        print("Error: el log no tiene el formato esperado.", file=sys.stderr)
        return 1

    resumen = deshacer(registro)
    for movimiento in resumen["deshechos"]:
        print("[UNDO] {} -> {}".format(movimiento["nombre"], movimiento["destino"]))
    for error in resumen["errores"]:
        print("[!] {} -> {}".format(error["nombre"], error["error"]), file=sys.stderr)

    print()
    print("Resumen")
    print("  Archivos devueltos:  {}".format(len(resumen["deshechos"])))
    print("  Errores:             {}".format(len(resumen["errores"])))

    if not resumen["errores"]:
        Path(ruta).unlink(missing_ok=True)
    return 1 if resumen["errores"] else 0


def main(argv=None):
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
        default=NOMBRE_LOG,
        help="archivo de log (por defecto: %(default)s)",
    )

    revisar = sub.add_parser(
        "revisar", help="lista los archivos pendientes de revisar"
    )
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

    deshacer_parser = sub.add_parser(
        "deshacer", help="revierte los movimientos del ultimo log"
    )
    deshacer_parser.add_argument(
        "--log",
        default=NOMBRE_LOG,
        help="archivo de log (por defecto: %(default)s)",
    )

    sub.add_parser("reglas", help="lista asignaturas y temas disponibles")

    args = parser.parse_args(argv)

    if args.accion == "reglas":
        return _listar_reglas()

    if args.accion == "revisar":
        return _revisar(Path(args.salida).resolve(), args.interactivo)

    if args.accion == "deshacer":
        return _deshacer(Path(args.log))

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

    if not args.simular and (resumen["movimientos"] or resumen["errores"]):
        ruta_log = _resolver_log(args.log, origen, salida)
        _avisar_sobrescritura(ruta_log)
        try:
            _guardar_log(origen, salida, resumen, ruta_log)
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
