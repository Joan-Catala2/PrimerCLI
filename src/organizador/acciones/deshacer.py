"""Accion `deshacer`: revierte los movimientos guardados en el registro.

Dos modos: un log concreto (`--log`) o el historial (`--ultimos N`). La
diferencia de tratamiento ante un log corrupto es deliberada: una ruta
pedida a mano aborta (el usuario esperaba deshacer ESE log), mientras que
en el historial un log malo solo cuenta como error y el bucle continua.

Los logs escritos por `verificar --podar` llevan `restaurar: true`: sus
movimientos estan en la papelera del historial y se devuelven carpeta a
carpeta (la ruta original), no al origen del log. El motor `deshacer` no
conoce la papelera; la traduccion vive aqui, en la accion.
"""

from pathlib import Path

from ..excepciones import ConfigError
from ..organizador import _destino_disponible, deshacer
from .base import Accion
from .util import ruta_no_vacia


def _restaurar_papelera(datos, registro, simular=False):
    """Invierte un log de `verificar --podar` desde la papelera del historial.

    Cada movimiento tiene `destino` = ruta original. La copia vive en
    `<logs>/.papelera/<nombre>` (con sufijo -N si habia colision). Devuelve
    el mismo resumen que `organizador.deshacer`.
    """
    papelera = Path(datos.get("origen", registro.carpeta)) / ".papelera"
    deshechos = []
    errores = []
    for movimiento in datos.get("movimientos", []):
        nombre = movimiento.get("nombre", "")
        original = Path(movimiento.get("destino", ""))
        copia = papelera / original.name
        if not copia.is_file():
            copia = _buscar_por_sufijo(papelera, original.name)
        try:
            if copia is None:
                raise FileNotFoundError(
                    "no esta en la papelera: {}".format(original.name)
                )
            destino = _destino_disponible(original)
            if not simular:
                original.parent.mkdir(parents=True, exist_ok=True)
                from shutil import move

                move(str(copia), str(destino))
            deshechos.append({"nombre": nombre, "destino": str(destino)})
        except OSError as error:
            errores.append({"nombre": nombre, "error": str(error)})
    return {"deshechos": deshechos, "errores": errores}


def _buscar_por_sufijo(papelera, nombre):
    """'doc.pdf' en la papelera pudo guardarse como 'doc-1.pdf', 'doc-2.pdf'..."""
    from ..organizador import NOMBRE_LOG  # noqa: F401 — coherencia de sufijos

    if not papelera.is_dir():
        return None
    base = Path(nombre)
    candidatos = [papelera / nombre]
    n = 1
    while True:
        candidatos.append(papelera / "{}-{}{}".format(base.stem, n, base.suffix))
        n += 1
        if n > 50:
            break
    for candidato in candidatos:
        if candidato.is_file():
            return candidato
    return None


def deshacer_un_log(registro, ruta, simular=False):
    """Carga y revierte un log. Devuelve (estado, resumen).

    estado: "ok", "missing" (no existe) o "error" (log invalido). El log
    invalido se propaga como excepcion y lo resuelve el llamador segun el
    contexto: una ruta concreta aborta con `ConfigError`; dentro del
    historial solo cuenta como fallo de ese log. Los logs de poda
    (`restaurar: true`) se revierten desde la papelera.
    """
    try:
        datos = registro.cargar(ruta)
    except ConfigError as error:
        return "error", str(error)

    if datos is None:
        return "missing", None

    if datos.get("restaurar"):
        return "ok", _restaurar_papelera(datos, registro, simular=simular)

    return "ok", deshacer(datos, simular=simular)


class AccionDeshacer(Accion):
    nombre = "deshacer"

    def __init__(
        self, consola, registro, ultimos=1, simular=False, listar=False, log=None
    ):
        super().__init__(consola)
        self.registro = registro
        self.ultimos = ultimos
        self.simular = simular
        self.listar = listar
        self.log = log

    @classmethod
    def desde_config(cls, args, consola):
        from ..registro import Registro

        cls.validar_ultimos(args.ultimos)
        return cls(
            consola=consola,
            registro=Registro.desde_config(args),
            ultimos=args.ultimos,
            simular=args.simular,
            listar=args.listar,
            log=ruta_no_vacia(args.log, "--log"),
        )

    def ejecutar(self):
        if self.listar:
            return self._listar()
        if self.log is not None:
            return self._deshacer_un_log(Path(self.log))
        return self._deshacer_historial()

    # --- listar ---------------------------------------------------------

    def _listar(self):
        if self.log is not None:
            ruta = Path(self.log)
            info = self.registro.info(ruta)
            return self._mostrar_logs([info] if info else [], ruta.parent)
        rutas = self.registro.disponibles()[: self.ultimos]
        infos = [info for info in (self.registro.info(ruta) for ruta in rutas) if info]
        return self._mostrar_logs(infos, self.registro.carpeta)

    def _mostrar_logs(self, infos, carpeta):
        consola = self.consola
        if consola.json_mode:
            self._emitir(carpeta=str(carpeta), logs=infos)
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

    # --- deshacer un log concreto ----------------------------------------

    def _deshacer_un_log(self, ruta):
        consola = self.consola
        estado, resultado = deshacer_un_log(self.registro, ruta, self.simular)
        if estado == "error":
            raise ConfigError(resultado)
        if estado == "missing":
            if consola.json_mode:
                self._emitir(
                    ruta=str(ruta),
                    existe=False,
                    simulado=self.simular,
                    deshechos=[],
                    errores=[],
                    borrado=False,
                )
                return 0
            consola.linea("No hay log para deshacer: {}".format(ruta))
            return 0
        resumen = resultado

        borrado = self._borrar_si_toca(ruta, resumen)
        if self._es_log_poda(ruta) and not resumen["errores"] and not self.simular:
            self._purga_papelera()

        if consola.json_mode:
            self._emitir(
                ruta=str(ruta),
                existe=True,
                simulado=self.simular,
                deshechos=resumen["deshechos"],
                errores=resumen["errores"],
                borrado=borrado,
            )
            return 1 if resumen["errores"] else 0

        consola.deshechos(resumen)

        lineas: list = [
            ("Archivos devueltos", len(resumen["deshechos"])),
            ("Errores", len(resumen["errores"])),
        ]
        if self.simular:
            lineas.append(("Modo", "simulación (no se ha movido nada)"))
        consola.resumen(lineas)
        return 1 if resumen["errores"] else 0

    # --- deshacer historial ------------------------------------------------

    def _deshacer_historial(self):
        consola = self.consola
        rutas = self.registro.disponibles()[: self.ultimos]
        carpeta = self.registro.carpeta
        if not rutas:
            if consola.json_mode:
                self._emitir(
                    carpeta=str(carpeta),
                    simulado=self.simular,
                    logs=[],
                    deshechos=0,
                    errores=0,
                )
                return 0
            consola.linea("No hay logs para deshacer en {}".format(carpeta))
            return 0

        total = 0
        errores = 0
        registros: list = []
        for numero, ruta in enumerate(rutas, start=1):
            consola.linea("[{}/{}] {}".format(numero, len(rutas), ruta.name))
            estado, resultado = deshacer_un_log(self.registro, ruta, self.simular)
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

            borrado = self._borrar_si_toca(ruta, resumen)
            if (
                borrado
                and self._es_log_poda(ruta)
                and len(resumen["errores"]) == 0
                and not self.simular
            ):
                self._purga_papelera()
            registros.append(
                {
                    "ruta": str(ruta),
                    "deshechos": resumen["deshechos"],
                    "errores": resumen["errores"],
                    "borrado": borrado,
                }
            )

        if consola.json_mode:
            self._emitir(
                carpeta=str(carpeta),
                simulado=self.simular,
                logs=registros,
                deshechos=total,
                errores=errores,
            )
            return 1 if errores else 0

        lineas: list = [
            ("Logs procesados", len(rutas)),
            ("Archivos devueltos", total),
            ("Errores", errores),
        ]
        if self.simular:
            lineas.append(("Modo", "simulación (no se ha movido nada)"))
        consola.resumen(lineas)
        return 1 if errores else 0

    # --- utilidades ---------------------------------------------------------

    def _es_log_poda(self, ruta):
        """True si el log es de `verificar --podar` (se restaura desde papelera)."""
        return bool((self.registro.info(ruta) or {}).get("restaurar"))

    def _purga_papelera(self):
        """Vacía la papelera tras una restauración completa y sin errores."""
        papelera = Path(self.registro.carpeta) / ".papelera"
        if not papelera.is_dir():
            return
        from shutil import rmtree

        rmtree(str(papelera), ignore_errors=True)

    def _borrar_si_toca(self, ruta, resumen):
        """El log se borra solo si se deshizo entero y no se estaba simulando."""
        if self.simular or resumen["errores"]:
            return False
        Path(ruta).unlink(missing_ok=True)
        return True

    def _emitir(self, **datos):
        from ..presentacion import emitir_json

        emitir_json(datos)
