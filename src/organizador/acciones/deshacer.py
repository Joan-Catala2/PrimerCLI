"""Accion `deshacer`: revierte los movimientos guardados en el registro.

Dos modos: un log concreto (`--log`) o el historial (`--ultimos N`). La
diferencia de tratamiento ante un log corrupto es deliberada: una ruta
pedida a mano aborta (el usuario esperaba deshacer ESE log), mientras que
en el historial un log malo solo cuenta como error y el bucle continua.
"""

from pathlib import Path

from ..excepciones import ConfigError
from ..organizador import deshacer
from .base import Accion


def deshacer_un_log(registro, ruta, simular=False):
    """Carga y revierte un log. Devuelve (estado, resumen).

    estado: "ok", "missing" (no existe) o "error" (log invalido). El log
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
            log=args.log,
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

    def _borrar_si_toca(self, ruta, resumen):
        """El log se borra solo si se deshizo entero y no se estaba simulando."""
        if self.simular or resumen["errores"]:
            return False
        Path(ruta).unlink(missing_ok=True)
        return True

    def _emitir(self, **datos):
        from ..presentacion import emitir_json

        emitir_json(datos)
