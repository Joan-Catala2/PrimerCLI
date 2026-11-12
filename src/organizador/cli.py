"""Punto de entrada de la CLI `organizador`."""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from . import __version__
from .organizador import deshacer, limpiar_vacias, mover_archivo, organizar
from .reglas import (
    REVISION,
    clasificar,
    reglas_efectivas,
    ruta_reglas_usuario,
)

CARPETA_SUGERIDA = "descargas"
CARPETA_LOGS = "organizador-logs"


def _emitir_json(datos):
    """Escribe `datos` como JSON a stdout (una sola linea legible)."""
    json.dump(datos, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


def _parsear_fecha(texto):
    """Convierte 'YYYY-MM-DD' (hora local, medianoche) a datetime."""
    try:
        return datetime.strptime(texto, "%Y-%m-%d")
    except ValueError:
        raise ValueError("fecha inválida '{}': usa el formato YYYY-MM-DD".format(texto))


def _extensiones_de(valores):
    """Aplana --extension aceptando repeticiones y listas separadas por comas."""
    extensiones: list = []
    for valor in valores or ():
        extensiones.extend(parte for parte in valor.split(",") if parte.strip())
    return extensiones


def _confirmar(total, json_salida=False):
    """Pide confirmacion; en modo JSON el aviso va a stderr."""
    texto = "¿Mover {} archivos? [s/N]: ".format(total)
    try:
        if json_salida:
            print(texto, end="", file=sys.stderr, flush=True)
            respuesta = input()
        else:
            respuesta = input(texto)
    except EOFError:
        if json_salida:
            print(file=sys.stderr)
        return False
    return respuesta.strip().lower() in {"s", "si", "sí", "y", "yes"}


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


def _guardar_historial(origen, salida, resumen, carpeta):
    """Guarda una entrada nueva en el historial de logs y devuelve su ruta."""
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    marca = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    ruta = carpeta / "{}.json".format(marca)
    _guardar_log(origen, salida, resumen, ruta)
    return ruta


def _logs_disponibles(carpeta):
    """Logs del historial, del mas reciente al mas antiguo."""
    carpeta = Path(carpeta)
    if not carpeta.is_dir():
        return []
    return sorted(
        (p for p in carpeta.glob("*.json") if p.is_file()),
        key=lambda p: p.name,
        reverse=True,
    )


def _preguntar(texto, json_salida=False):
    """Pide un dato; en modo JSON el enunciado va a stderr."""
    if json_salida:
        print(texto, end="", file=sys.stderr, flush=True)
        return input()
    return input(texto)


def _respuesta_si(texto, json_salida=False):
    """Pregunta de si/no. Un EOFError se propaga al llamador."""
    respuesta = _preguntar(texto, json_salida)
    return respuesta.strip().lower() in {"s", "si", "sí", "y", "yes"}


def _mapa_temas(reglas):
    """Devuelve {asignatura: [temas]} a partir de las reglas efectivas."""
    temas: dict = {}
    for regla in reglas or ():
        lista = temas.setdefault(regla.asignatura, [])
        for tema, _ in regla.temas:
            if tema not in lista:
                lista.append(tema)
    return temas


def _revisar(salida, interactivo=False, reglas=None, json_salida=False):
    """Lista (y opcionalmente recoloca) los archivos de <salida>/_revision."""
    carpeta = salida / REVISION
    if not carpeta.is_dir():
        if json_salida:
            _emitir_json(
                {
                    "salida": str(salida),
                    "carpeta": str(carpeta),
                    "existe": False,
                    "archivos": [],
                    "total": 0,
                    "movidos": [],
                    "pendientes": 0,
                    "cancelado": False,
                }
            )
            return 0
        print("No existe la carpeta de revisión: {}".format(carpeta))
        return 0

    archivos = sorted(p for p in carpeta.iterdir() if p.is_file())

    if not interactivo:
        if json_salida:
            _emitir_json(
                {
                    "salida": str(salida),
                    "carpeta": str(carpeta),
                    "existe": True,
                    "archivos": [archivo.name for archivo in archivos],
                    "total": len(archivos),
                }
            )
            return 0
        for archivo in archivos:
            print(archivo.name)
        print()
        print("Archivos a revisar: {}".format(len(archivos)))
        return 0

    asignaturas = {regla.asignatura for regla in (reglas or ())}
    temas_por_asignatura = _mapa_temas(reglas)
    if not json_salida:
        print("Asignaturas disponibles: {}".format(", ".join(sorted(asignaturas))))

    movidos = []
    cancelado = False
    salir = False
    for numero, archivo in enumerate(archivos, start=1):
        if not json_salida:
            print()
            print("[{}/{}] {}".format(numero, len(archivos), archivo.name))

        sugerencia = clasificar(archivo.name, reglas)
        sug_asignatura, sug_tema = sugerencia if sugerencia else ("", "")

        try:
            if sug_asignatura:
                pregunta = "Asignatura [{}] (Enter para aceptar, q para salir): "
                pregunta = pregunta.format(sug_asignatura)
            else:
                pregunta = "Asignatura (Enter para saltar, q para salir): "
            respuesta = _preguntar(pregunta, json_salida).strip()
            if respuesta.lower() == "q":
                salir = True
                break

            asignatura = respuesta or sug_asignatura
            if not asignatura:
                continue

            if asignatura not in asignaturas:
                crear = _respuesta_si(
                    '¿Crear asignatura "{}"? [s/N]: '.format(asignatura),
                    json_salida,
                )
                if not crear:
                    if not json_salida:
                        print("Asignatura no válida, se salta.")
                    continue
                asignaturas.add(asignatura)
                temas_por_asignatura.setdefault(asignatura, [])

            temas = temas_por_asignatura.get(asignatura, [])
            if temas and not json_salida:
                print("Temas: {}".format(", ".join(temas)))

            tema_sugerido = sug_tema if asignatura == sug_asignatura else ""
            if tema_sugerido:
                pregunta_tema = "Tema [{}] (Enter para aceptar, '-' para ninguno): "
                pregunta_tema = pregunta_tema.format(tema_sugerido)
            else:
                pregunta_tema = "Tema (opcional, '-' para ninguno): "

            respuesta = _preguntar(pregunta_tema, json_salida).strip()
            if respuesta.lower() == "q":
                salir = True
                break
            if respuesta == "-":
                tema = ""
            else:
                tema = respuesta or tema_sugerido

            if tema and temas and tema not in temas:
                crear = _respuesta_si(
                    '¿Crear tema "{}"? [s/N]: '.format(tema), json_salida
                )
                if crear:
                    temas.append(tema)
                else:
                    if not json_salida:
                        print("Tema no válido, se usa sin tema.")
                    tema = ""
        except EOFError:
            if not json_salida:
                print()
                print("Entrada cancelada; se deja el resto en revisión.")
            cancelado = True
            break

        destino_dir = salida / asignatura
        if tema:
            destino_dir = destino_dir / tema

        destino = mover_archivo(archivo, destino_dir)
        movidos.append(
            {
                "nombre": archivo.name,
                "asignatura": asignatura,
                "tema": tema,
                "destino": str(destino),
            }
        )
        if not json_salida:
            print("Movido a {}".format(destino.relative_to(salida)))

    if movidos:
        limpiar_vacias(salida)

    if json_salida:
        _emitir_json(
            {
                "salida": str(salida),
                "carpeta": str(carpeta),
                "existe": True,
                "archivos": [archivo.name for archivo in archivos],
                "total": len(archivos),
                "movidos": movidos,
                "pendientes": len(archivos) - len(movidos),
                "cancelado": cancelado,
                "salir": salir,
            }
        )
        return 130 if cancelado else 0

    print()
    print("Archivos movidos: {}".format(len(movidos)))
    print("Pendientes:       {}".format(len(archivos) - len(movidos)))
    if salir:
        print("Sesión terminada; se deja el resto en revisión.")
    return 130 if cancelado else 0


def _obtener_reglas(ruta):
    """Carga las reglas efectivas; imprime el error y devuelve None si falla."""
    try:
        return reglas_efectivas(ruta)
    except (OSError, ValueError) as error:
        print("Error: {}".format(error), file=sys.stderr)
        return None


def _listar_reglas(reglas):
    """Muestra las asignaturas y temas disponibles."""
    usuario = ruta_reglas_usuario()
    if usuario.is_file():
        print("Reglas del usuario: {}".format(usuario))
    for regla in reglas:
        print(regla.asignatura)
        for tema, _ in regla.temas:
            print("  - {}".format(tema))
    return 0


def _deshacer_un_log(ruta, simular=False):
    """Carga y revierte un log. Devuelve (estado, resumen).

    estado: "ok", "missing" (no existe) o "error" (log invalido).
    """
    try:
        with open(ruta, encoding="utf-8") as archivo:
            registro = json.load(archivo)
    except FileNotFoundError:
        return "missing", None
    except json.JSONDecodeError as error:
        print("Error: log inválido {}: {}".format(ruta, error), file=sys.stderr)
        return "error", None

    if not isinstance(registro, dict):
        print(
            "Error: el log no tiene el formato esperado: {}".format(ruta),
            file=sys.stderr,
        )
        return "error", None

    return "ok", deshacer(registro, simular=simular)


def _info_log(ruta):
    """Resumen legible de un log del historial, o None si no se puede leer."""
    try:
        with open(ruta, encoding="utf-8") as archivo:
            datos = json.load(archivo)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(datos, dict):
        return None
    movimientos = datos.get("movimientos", [])
    errores = datos.get("errores", [])
    return {
        "ruta": str(ruta),
        "fichero": Path(ruta).name,
        "fecha": datos.get("fecha", ""),
        "origen": datos.get("origen", ""),
        "salida": datos.get("salida", ""),
        "movimientos": len(movimientos) if isinstance(movimientos, list) else 0,
        "errores": len(errores) if isinstance(errores, list) else 0,
    }


def _detalles_deshacer(resumen, json_salida=False):
    if not json_salida:
        for movimiento in resumen["deshechos"]:
            print("[UNDO] {} -> {}".format(movimiento["nombre"], movimiento["destino"]))
    for fallo in resumen["errores"]:
        print("[!] {} -> {}".format(fallo["nombre"], fallo["error"]), file=sys.stderr)


def _deshacer(ruta, simular=False, json_salida=False):
    """Revierte los movimientos guardados en un unico log."""
    estado, resumen = _deshacer_un_log(ruta, simular=simular)
    if estado == "missing":
        if json_salida:
            _emitir_json(
                {
                    "ruta": str(ruta),
                    "existe": False,
                    "simulado": simular,
                    "deshechos": [],
                    "errores": [],
                    "borrado": False,
                }
            )
            return 0
        print("No hay log para deshacer: {}".format(ruta))
        return 0
    if estado == "error":
        if json_salida:
            _emitir_json(
                {
                    "ruta": str(ruta),
                    "existe": True,
                    "simulado": simular,
                    "error": "log inválido",
                    "deshechos": [],
                    "errores": [],
                    "borrado": False,
                }
            )
        return 1

    borrado = False
    if not simular and not resumen["errores"]:
        Path(ruta).unlink(missing_ok=True)
        borrado = True

    if json_salida:
        _emitir_json(
            {
                "ruta": str(ruta),
                "existe": True,
                "simulado": simular,
                "deshechos": resumen["deshechos"],
                "errores": resumen["errores"],
                "borrado": borrado,
            }
        )
        return 1 if resumen["errores"] else 0

    _detalles_deshacer(resumen)

    print()
    print("Resumen")
    print("  Archivos devueltos:  {}".format(len(resumen["deshechos"])))
    print("  Errores:             {}".format(len(resumen["errores"])))
    if simular:
        print("  Modo:                simulación (no se ha movido nada)")
    return 1 if resumen["errores"] else 0


def _deshacer_historial(carpeta, ultimos, simular=False, json_salida=False):
    """Revierte los `ultimos` logs del historial, del mas reciente al mas antiguo."""
    rutas = _logs_disponibles(carpeta)[:ultimos]
    if not rutas:
        if json_salida:
            _emitir_json(
                {
                    "carpeta": str(carpeta),
                    "simulado": simular,
                    "logs": [],
                    "deshechos": 0,
                    "errores": 0,
                }
            )
            return 0
        print("No hay logs para deshacer en {}".format(carpeta))
        return 0

    total = 0
    errores = 0
    registros: list = []
    for numero, ruta in enumerate(rutas, start=1):
        if not json_salida:
            print("[{}/{}] {}".format(numero, len(rutas), ruta.name))
        estado, resumen = _deshacer_un_log(ruta, simular=simular)
        if estado == "error":
            errores += 1
            registros.append({"ruta": str(ruta), "error": "log inválido"})
            continue
        if estado == "missing":
            registros.append({"ruta": str(ruta), "error": "no existe"})
            continue

        _detalles_deshacer(resumen, json_salida)
        total += len(resumen["deshechos"])
        errores += len(resumen["errores"])

        borrado = False
        if not simular and not resumen["errores"]:
            ruta.unlink(missing_ok=True)
            borrado = True
        registros.append(
            {
                "ruta": str(ruta),
                "deshechos": resumen["deshechos"],
                "errores": resumen["errores"],
                "borrado": borrado,
            }
        )

    if json_salida:
        _emitir_json(
            {
                "carpeta": str(carpeta),
                "simulado": simular,
                "logs": registros,
                "deshechos": total,
                "errores": errores,
            }
        )
        return 1 if errores else 0

    print()
    print("Resumen")
    print("  Logs procesados:     {}".format(len(rutas)))
    print("  Archivos devueltos:  {}".format(total))
    print("  Errores:             {}".format(errores))
    if simular:
        print("  Modo:                simulación (no se ha movido nada)")
    return 1 if errores else 0


def _listar_logs(infos, json_salida=False, carpeta=""):
    """Muestra una lista de resumenes de logs (o su version JSON)."""
    if json_salida:
        _emitir_json({"carpeta": str(carpeta), "logs": infos})
        return 0

    if not infos:
        print("No hay logs en {}".format(carpeta))
        return 0

    for info in infos:
        print(
            "{}  {:>3} movimientos  {}".format(
                info["fecha"] or info["fichero"],
                info["movimientos"],
                info["ruta"],
            )
        )
    print()
    print("Logs: {}".format(len(infos)))
    return 0


def _listar_historial(carpeta, ultimos, json_salida=False):
    """Muestra los logs del historial sin revertirlos."""
    rutas = _logs_disponibles(carpeta)[:ultimos]
    infos = [info for info in (_info_log(ruta) for ruta in rutas) if info]
    return _listar_logs(infos, json_salida, carpeta)


def _mostrar_movimientos(resumen, salida, etiqueta="[OK]"):
    """Muestra el detalle de los movimientos de un resumen."""
    for movimiento in resumen["movimientos"]:
        relativo = Path(movimiento["destino"]).relative_to(salida)
        marca = "[?]" if movimiento["asignatura"] == REVISION else etiqueta
        print("{} {} -> {}".format(marca, movimiento["nombre"], relativo))


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

    args = parser.parse_args(argv)

    if args.accion == "reglas":
        reglas = _obtener_reglas(args.reglas)
        if reglas is None:
            return 1
        return _listar_reglas(reglas)

    if args.accion == "revisar":
        reglas = _obtener_reglas(args.reglas)
        if reglas is None:
            return 1
        return _revisar(
            Path(args.salida).resolve(), args.interactivo, reglas, args.json
        )

    if args.accion == "deshacer":
        if args.ultimos < 1:
            print("Error: --ultimos debe ser 1 o mas.", file=sys.stderr)
            return 1

        if args.listar:
            if args.log is not None:
                ruta = Path(args.log)
                info = _info_log(ruta)
                return _listar_logs([info] if info else [], args.json, ruta.parent)
            return _listar_historial(Path(args.logs_dir), args.ultimos, args.json)

        if args.log is not None:
            return _deshacer(
                Path(args.log), simular=args.simular, json_salida=args.json
            )
        return _deshacer_historial(
            Path(args.logs_dir),
            args.ultimos,
            simular=args.simular,
            json_salida=args.json,
        )

    if args.accion != "ejecutar":
        parser.print_help()
        return 1

    reglas = _obtener_reglas(args.reglas)
    if reglas is None:
        return 1

    origen = Path(args.origen).resolve()
    salida = Path(args.salida).resolve()

    desde = None
    if args.desde is not None:
        try:
            desde = _parsear_fecha(args.desde)
        except ValueError as error:
            print("Error: {}".format(error), file=sys.stderr)
            return 1

    opciones = {
        "reglas": reglas,
        "recursivo": args.recursivo,
        "extensiones": _extensiones_de(args.extension),
        "excluir": args.excluir,
        "desde": desde,
        "ignorar": [Path(args.logs_dir).resolve()],
    }

    simulado = args.simular or args.confirmar
    try:
        resumen = organizar(origen, salida, simular=simulado, **opciones)
    except (NotADirectoryError, ValueError, OSError) as error:
        print("Error: {}".format(error), file=sys.stderr)
        return 1

    cancelado = False
    if args.confirmar and not args.simular:
        if resumen["movimientos"]:
            if not args.json and not args.seco:
                _mostrar_movimientos(resumen, salida, "[SIM]")
            if _confirmar(len(resumen["movimientos"]), args.json):
                try:
                    resumen = organizar(origen, salida, simular=False, **opciones)
                except (NotADirectoryError, ValueError, OSError) as error:
                    print("Error: {}".format(error), file=sys.stderr)
                    return 1
                simulado = False
            else:
                cancelado = True
                simulado = True
        else:
            simulado = False

    ruta_log = None
    if not simulado and (resumen["movimientos"] or resumen["errores"]):
        if args.log is not None:
            ruta_log = _resolver_log(args.log, origen, salida)
            _avisar_sobrescritura(ruta_log)
        try:
            if ruta_log is not None:
                _guardar_log(origen, salida, resumen, ruta_log)
            else:
                ruta_log = _guardar_historial(origen, salida, resumen, args.logs_dir)
        except OSError as error:
            print(
                "Aviso: no se pudo escribir el log: {}".format(error),
                file=sys.stderr,
            )

    total = len(resumen["organizados"]) + len(resumen["revision"])

    if args.json:
        _emitir_json(
            {
                "origen": str(origen),
                "salida": str(salida),
                "simulado": simulado,
                "cancelado": cancelado,
                "movimientos": resumen["movimientos"],
                "organizados": [
                    {"nombre": nombre, "asignatura": asignatura, "tema": tema}
                    for nombre, asignatura, tema in resumen["organizados"]
                ],
                "revision": resumen["revision"],
                "errores": resumen["errores"],
                "filtrados": resumen["filtrados"],
                "total": total,
                "log": str(ruta_log) if ruta_log is not None else None,
            }
        )
        if cancelado:
            print("Cancelado; no se ha movido nada.", file=sys.stderr)
        return 0

    if cancelado:
        print("Cancelado; no se ha movido nada.")
        return 0

    etiqueta = "[SIM]" if simulado else "[OK]"

    if not args.seco:
        _mostrar_movimientos(resumen, salida, etiqueta)

    for fallo in resumen["errores"]:
        print("[!] {} -> {}".format(fallo["nombre"], fallo["error"]), file=sys.stderr)

    print()
    print("Resumen")
    print("  Archivos procesados: {}".format(total))
    print("  Organizados:         {}".format(len(resumen["organizados"])))
    print("  A revisar:           {}".format(len(resumen["revision"])))
    print("  Errores:             {}".format(len(resumen["errores"])))
    print("  Filtrados:           {}".format(resumen["filtrados"]))
    print("  Destino:             {}".format(salida))
    if ruta_log is not None:
        print("  Log:                 {}".format(ruta_log))
    if simulado:
        print("  Modo:                simulación (no se ha movido nada)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
