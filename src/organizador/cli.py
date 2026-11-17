"""Punto de entrada de la CLI `organizador`."""

import argparse
import sys
from datetime import datetime
from pathlib import Path

from . import __version__
from .excepciones import AccionNoValida, ConfigError, ErrorDeUso, OrganizadorError
from .organizador import deshacer, limpiar_vacias, mover_archivo, organizar
from .presentacion import emitir_json, error_json
from .presentacion.consola import Consola
from .registro import CARPETA_LOGS, Registro
from .reglas import (
    REVISION,
    clasificar,
    reglas_efectivas,
    ruta_reglas_usuario,
)

CARPETA_SUGERIDA = "descargas"


def _parsear_fecha(texto):
    """Convierte 'YYYY-MM-DD' (hora local, medianoche) a datetime."""
    try:
        return datetime.strptime(texto, "%Y-%m-%d")
    except ValueError:
        raise ErrorDeUso(
            "fecha inválida '{}': usa el formato YYYY-MM-DD".format(texto)
        ) from None


def _extensiones_de(valores):
    """Aplana --extension aceptando repeticiones y listas separadas por comas."""
    extensiones: list = []
    for valor in valores or ():
        extensiones.extend(parte for parte in valor.split(",") if parte.strip())
    return extensiones


def _confirmar(total, consola):
    return consola.confirmar(total)


def _preguntar(texto, consola):
    return consola.preguntar(texto)


def _respuesta_si(texto, consola):
    return consola.respuesta_si(texto)


def _mapa_temas(reglas):
    """Devuelve {asignatura: [temas]} a partir de las reglas efectivas."""
    temas: dict = {}
    for regla in reglas or ():
        lista = temas.setdefault(regla.asignatura, [])
        for tema, _ in regla.temas:
            if tema not in lista:
                lista.append(tema)
    return temas


def _revisar(salida, interactivo=False, reglas=None, consola=None):
    """Lista (y opcionalmente recoloca) los archivos de <salida>/_revision."""
    consola = consola or Consola()
    carpeta = salida / REVISION
    if not carpeta.is_dir():
        if consola.json_mode:
            emitir_json(
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
        consola.linea("No existe la carpeta de revisión: {}".format(carpeta))
        return 0

    archivos = sorted(p for p in carpeta.iterdir() if p.is_file())

    if not interactivo:
        if consola.json_mode:
            emitir_json(
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
            consola.linea(archivo.name)
        consola.linea()
        consola.linea("Archivos a revisar: {}".format(len(archivos)))
        return 0

    asignaturas = {regla.asignatura for regla in (reglas or ())}
    temas_por_asignatura = _mapa_temas(reglas)
    consola.linea("Asignaturas disponibles: {}".format(", ".join(sorted(asignaturas))))

    movidos = []
    cancelado = False
    salir = False
    for numero, archivo in enumerate(archivos, start=1):
        consola.linea()
        consola.linea("[{}/{}] {}".format(numero, len(archivos), archivo.name))

        sugerencia = clasificar(archivo.name, reglas)
        sug_asignatura, sug_tema = sugerencia if sugerencia else ("", "")

        try:
            if sug_asignatura:
                pregunta = "Asignatura [{}] (Enter para aceptar, q para salir): "
                pregunta = pregunta.format(sug_asignatura)
            else:
                pregunta = "Asignatura (Enter para saltar, q para salir): "
            respuesta = _preguntar(pregunta, consola).strip()
            if respuesta.lower() == "q":
                salir = True
                break

            asignatura = respuesta or sug_asignatura
            if not asignatura:
                continue

            if asignatura not in asignaturas:
                crear = _respuesta_si(
                    '¿Crear asignatura "{}"? [s/N]: '.format(asignatura),
                    consola,
                )
                if not crear:
                    consola.linea("Asignatura no válida, se salta.")
                    continue
                asignaturas.add(asignatura)
                temas_por_asignatura.setdefault(asignatura, [])

            temas = temas_por_asignatura.get(asignatura, [])
            if temas:
                consola.linea("Temas: {}".format(", ".join(temas)))

            tema_sugerido = sug_tema if asignatura == sug_asignatura else ""
            if tema_sugerido:
                pregunta_tema = "Tema [{}] (Enter para aceptar, '-' para ninguno): "
                pregunta_tema = pregunta_tema.format(tema_sugerido)
            else:
                pregunta_tema = "Tema (opcional, '-' para ninguno): "

            respuesta = _preguntar(pregunta_tema, consola).strip()
            if respuesta.lower() == "q":
                salir = True
                break
            if respuesta == "-":
                tema = ""
            else:
                tema = respuesta or tema_sugerido

            if tema and temas and tema not in temas:
                crear = _respuesta_si('¿Crear tema "{}"? [s/N]: '.format(tema), consola)
                if crear:
                    temas.append(tema)
                else:
                    consola.linea("Tema no válido, se usa sin tema.")
                    tema = ""
        except EOFError:
            consola.linea()
            consola.linea("Entrada cancelada; se deja el resto en revisión.")
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
        consola.linea("Movido a {}".format(destino.relative_to(salida)))

    if movidos:
        limpiar_vacias(salida)

    if consola.json_mode:
        emitir_json(
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

    consola.linea()
    consola.linea("Archivos movidos: {}".format(len(movidos)))
    consola.linea("Pendientes:       {}".format(len(archivos) - len(movidos)))
    if salir:
        consola.linea("Sesión terminada; se deja el resto en revisión.")
    return 130 if cancelado else 0


def _obtener_reglas(ruta):
    """Carga las reglas efectivas. Los ConfigError se propagan a main()."""
    return reglas_efectivas(ruta)


def _listar_reglas(reglas, consola=None):
    """Muestra las asignaturas y temas disponibles."""
    consola = consola or Consola()
    usuario = ruta_reglas_usuario()
    if usuario.is_file():
        consola.linea("Reglas del usuario: {}".format(usuario))
    for regla in reglas:
        consola.linea(regla.asignatura)
        for tema, _ in regla.temas:
            consola.linea("  - {}".format(tema))
    return 0


def _deshacer_un_log(registro, ruta, simular=False):
    """Carga y revierte un log. Devuelve (estado, resumen).

    estado: "ok", "missing" (no existe) o "error" (log invalido). El error
    invalido se propaga como excepcion y lo resuelve el llamador segun el
    contexto: una ruta concreta aborta con `ConfigError`; dentro del
    historial solo cuenta como fallo de ese log.
    """
    try:
        datos = registro.cargar(ruta)
    except ConfigError as error:
        return "error", str(error)

    if datos is None:
        return "missing", None

    return "ok", deshacer(datos, simular=simular)


def _deshacer(registro, ruta, simular=False, consola=None):
    """Revierte los movimientos guardados en un unico log."""
    consola = consola or Consola()
    estado, resultado = _deshacer_un_log(registro, ruta, simular=simular)
    if estado == "error":
        raise ConfigError(resultado)
    if estado == "missing":
        if consola.json_mode:
            emitir_json(
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
        consola.linea("No hay log para deshacer: {}".format(ruta))
        return 0
    resumen = resultado

    borrado = False
    if not simular and not resumen["errores"]:
        Path(ruta).unlink(missing_ok=True)
        borrado = True

    if consola.json_mode:
        emitir_json(
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

    consola.deshechos(resumen)

    lineas: list = [
        ("Archivos devueltos", len(resumen["deshechos"])),
        ("Errores", len(resumen["errores"])),
    ]
    if simular:
        lineas.append(("Modo", "simulación (no se ha movido nada)"))
    consola.resumen(lineas)
    return 1 if resumen["errores"] else 0


def _deshacer_historial(registro, ultimos, simular=False, consola=None):
    """Revierte los `ultimos` logs del historial, del mas reciente al mas antiguo."""
    consola = consola or Consola()
    rutas = registro.disponibles()[:ultimos]
    carpeta = registro.carpeta
    if not rutas:
        if consola.json_mode:
            emitir_json(
                {
                    "carpeta": str(carpeta),
                    "simulado": simular,
                    "logs": [],
                    "deshechos": 0,
                    "errores": 0,
                }
            )
            return 0
        consola.linea("No hay logs para deshacer en {}".format(carpeta))
        return 0

    total = 0
    errores = 0
    registros: list = []
    for numero, ruta in enumerate(rutas, start=1):
        consola.linea("[{}/{}] {}".format(numero, len(rutas), ruta.name))
        estado, resultado = _deshacer_un_log(registro, ruta, simular=simular)
        if estado == "error":
            errores += 1
            consola.aviso("[!] {}: {}".format(ruta.name, resultado))
            registros.append({"ruta": str(ruta), "error": resultado})
            continue
        if estado == "missing":
            registros.append({"ruta": str(ruta), "error": "no existe"})
            continue
        resumen = resultado

        consola.deshechos(resumen)
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

    if consola.json_mode:
        emitir_json(
            {
                "carpeta": str(carpeta),
                "simulado": simular,
                "logs": registros,
                "deshechos": total,
                "errores": errores,
            }
        )
        return 1 if errores else 0

    lineas: list = [
        ("Logs procesados", len(rutas)),
        ("Archivos devueltos", total),
        ("Errores", errores),
    ]
    if simular:
        lineas.append(("Modo", "simulación (no se ha movido nada)"))
    consola.resumen(lineas)
    return 1 if errores else 0


def _listar_logs(infos, consola=None, carpeta=""):
    """Muestra una lista de resumenes de logs (o su version JSON)."""
    consola = consola or Consola()
    if consola.json_mode:
        emitir_json({"carpeta": str(carpeta), "logs": infos})
        return 0

    if not infos:
        consola.linea("No hay logs en {}".format(carpeta))
        return 0

    for info in infos:
        consola.linea(
            "{}  {:>3} movimientos  {}".format(
                info["fecha"] or info["fichero"],
                info["movimientos"],
                info["ruta"],
            )
        )
    consola.linea()
    consola.linea("Logs: {}".format(len(infos)))
    return 0


def _listar_historial(registro, ultimos, consola=None):
    """Muestra los logs del historial sin revertirlos."""
    rutas = registro.disponibles()[:ultimos]
    infos = [info for info in (Registro.info(ruta) for ruta in rutas) if info]
    return _listar_logs(infos, consola, registro.carpeta)


def _mostrar_movimientos(resumen, salida, consola, etiqueta="[OK]"):
    """Muestra el detalle de los movimientos de un resumen."""
    for movimiento in resumen["movimientos"]:
        relativo = Path(movimiento["destino"]).relative_to(salida)
        marca = "[?]" if movimiento["asignatura"] == REVISION else etiqueta
        consola.detalle("{} {} -> {}".format(marca, movimiento["nombre"], relativo))


def _ejecutar(argv=None):
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
    consola = Consola.desde_config(args)

    if args.accion == "reglas":
        return _listar_reglas(_obtener_reglas(args.reglas), consola)

    if args.accion == "revisar":
        return _revisar(
            Path(args.salida).resolve(),
            args.interactivo,
            _obtener_reglas(args.reglas),
            consola,
        )

    if args.accion == "deshacer":
        if args.ultimos < 1:
            raise ErrorDeUso("--ultimos debe ser 1 o mas.")

        registro = Registro.desde_config(args)
        if args.listar:
            if args.log is not None:
                ruta = Path(args.log)
                info = Registro.info(ruta)
                return _listar_logs([info] if info else [], consola, ruta.parent)
            return _listar_historial(registro, args.ultimos, consola)

        if args.log is not None:
            return _deshacer(
                registro, Path(args.log), simular=args.simular, consola=consola
            )
        return _deshacer_historial(
            registro, args.ultimos, simular=args.simular, consola=consola
        )

    if args.accion != "ejecutar":
        raise AccionNoValida(
            "acción no reconocida: '{}'. Ejecuta 'organizador --help' para "
            "ver las disponibles.".format(args.accion)
        )

    reglas = _obtener_reglas(args.reglas)

    origen = Path(args.origen).resolve()
    salida = Path(args.salida).resolve()
    registro = Registro.desde_config(args)

    desde = _parsear_fecha(args.desde) if args.desde is not None else None

    opciones = {
        "reglas": reglas,
        "recursivo": args.recursivo,
        "extensiones": _extensiones_de(args.extension),
        "excluir": args.excluir,
        "desde": desde,
        "ignorar": [Path(args.logs_dir).resolve()],
    }

    simulado = args.simular or args.confirmar
    resumen = organizar(origen, salida, simular=simulado, **opciones)

    cancelado = False
    if args.confirmar and not args.simular:
        if resumen["movimientos"]:
            if not args.json and not args.seco:
                _mostrar_movimientos(resumen, salida, consola, "[SIM]")
            if _confirmar(len(resumen["movimientos"]), consola):
                resumen = organizar(origen, salida, simular=False, **opciones)
                simulado = False
            else:
                cancelado = True
                simulado = True
        else:
            simulado = False

    ruta_log = None
    if not simulado and (resumen["movimientos"] or resumen["errores"]):
        if args.log is not None:
            ruta_log = registro.ruta_unica(args.log, origen, salida, consola.aviso)
            registro.avisar_sobrescritura(ruta_log, consola.aviso)
        try:
            if ruta_log is not None:
                registro.guardar(origen, salida, resumen, ruta_log)
            else:
                ruta_log = registro.guardar_historial(origen, salida, resumen)
        except OSError as error:
            consola.aviso("Aviso: no se pudo escribir el log: {}".format(error))

    total = len(resumen["organizados"]) + len(resumen["revision"])

    if consola.json_mode:
        emitir_json(
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
            consola.cancelar("Cancelado; no se ha movido nada.")
        return 0

    if cancelado:
        consola.linea("Cancelado; no se ha movido nada.")
        return 0

    etiqueta = "[SIM]" if simulado else "[OK]"

    if not args.seco:
        _mostrar_movimientos(resumen, salida, consola, etiqueta)

    consola.errores(resumen)

    lineas = [
        ("Archivos procesados", total),
        ("Organizados", len(resumen["organizados"])),
        ("A revisar", len(resumen["revision"])),
        ("Errores", len(resumen["errores"])),
        ("Filtrados", resumen["filtrados"]),
        ("Destino", salida),
    ]
    if ruta_log is not None:
        lineas.append(("Log", ruta_log))
    if simulado:
        lineas.append(("Modo", "simulación (no se ha movido nada)"))
    consola.resumen(lineas)
    return 0


def _detectar_json(argv):
    """True si el argv pide `--json`, aunque todavia no este parseado."""
    return argv is not None and "--json" in argv


def main(argv=None):
    """Punto de entrada: despacha la accion y convierte errores en mensajes.

    Los `OrganizadorError` (reglas malas, fechas invalidas, origen
    inexistente...) se imprimen como mensaje humano, sin traceback, y
    devuelven el codigo de salida de cada error. En modo `--json` el error
    se emite como un objeto JSON valido (`ok: false`) para que un script
    nunca reciba texto plano donde espera JSON. El resto de excepciones no
    capturadas se dejan pasar: un traceback ante un bug real es intencionado.
    """
    try:
        return _ejecutar(argv)
    except OrganizadorError as error:
        if _detectar_json(argv):
            error_json(error)
        else:
            print("Error: {}".format(error), file=sys.stderr)
        return error.codigo_salida


if __name__ == "__main__":
    sys.exit(main())
