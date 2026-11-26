"""Historial de ejecuciones (logs) de la CLI `organizador`.

Un registro es un JSON con el origen, la salida y los movimientos de una
pasada. Sirve para dos cosas: avisar de sobrescritura y deshacer.

Esta capa se encarga de leer, escribir y localizar logs; no pinta nada en
pantalla (los avisos van por el parametro `aviso`, que la CLI enlaza con
stderr) y no sabe nada de argparse.
"""

import json
from datetime import datetime
from pathlib import Path

from .escaneo import hijos
from .excepciones import ConfigError, ErrorDeUso, afirmar

CARPETA_LOGS = "organizador-logs"


class Registro:
    """Historial de logs en una carpeta, con opcion de log unico."""

    def __init__(self, carpeta=CARPETA_LOGS):
        self.carpeta = Path(carpeta)
        # ruta relativa => relativa al cwd de CADA invocacion: los comandos
        # trabajan contra el historial actual del usuario
        self._absoluta = None

    @classmethod
    def desde_config(cls, args):
        """Crea el registro a partir de la configuracion parseada.

        Mantiene la ruta tal cual: si es relativa, cada comando la resuelve
        contra su cwd (comportamiento historico de la CLI).
        """
        from .acciones.util import ruta_no_vacia

        return cls(ruta_no_vacia(args.logs_dir, "--logs-dir"))

    def ruta_unica(self, ruta, origen, salida, aviso=None):
        """Devuelve una ruta de log unico que nunca cae dentro de `origen`.

        Si la ruta pedida (relativa al directorio actual) esta dentro del
        origen, se recoloca junto a la carpeta de salida para que una nueva
        pasada no la trate como archivo a organizar. El aviso, si procede,
        va al canal `aviso`.
        """
        if not str(ruta).strip():
            raise ErrorDeUso("--log no puede ser vacio.")
        ruta = Path(ruta)
        if not ruta.is_absolute():
            ruta = Path.cwd() / ruta
        ruta = ruta.resolve()

        origen = Path(origen).resolve()
        if ruta == origen or origen in ruta.parents:
            nueva = (Path(salida).resolve().parent / ruta.name).resolve()
            if aviso is not None:
                aviso("Aviso: el log se guardara fuera del origen en {}".format(nueva))
            return nueva
        return ruta

    def avisar_sobrescritura(self, ruta, aviso):
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
            aviso(
                "Aviso: se sobrescribira el log existente ({} movimientos). "
                "Usa --log para conservarlo.".format(movimientos)
            )

    def guardar(self, origen, salida, resumen, ruta):
        """Sobrescribe el log con el resumen de la ultima ejecucion."""
        afirmar(
            isinstance(resumen["movimientos"], list),
            "el log guardado no es una lista de movimientos",
        )
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
        return ruta

    def guardar_historial(self, origen, salida, resumen):
        """Guarda una entrada nueva en el historial y devuelve su ruta."""
        self.carpeta.mkdir(parents=True, exist_ok=True)
        marca = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        return self.guardar(
            origen, salida, resumen, self.carpeta / "{}.json".format(marca)
        )

    def disponibles(self):
        """Logs del historial, del mas reciente al mas antiguo."""
        if not self.carpeta.is_dir():
            return []
        return sorted(
            (p for p in hijos(self.carpeta) if p.suffix == ".json" and p.is_file()),
            key=lambda p: p.name,
            reverse=True,
        )

    def info(self, ruta):
        """Resumen legible de un log, o None si no se puede leer.

        Metodo de instancia, no static: la accion trabaja con un registro
        concreto y no debe importar la clase para consultar un log.
        """
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
            "restaurar": bool(datos.get("restaurar", False)),
            "movimientos": len(movimientos) if isinstance(movimientos, list) else 0,
            "errores": len(errores) if isinstance(errores, list) else 0,
        }

    @staticmethod
    def cargar(ruta):
        """Devuelve el contenido de un log, o None si no existe.

        Un JSON corrupto propaga ConfigError: quien decide si un log malo
        aborta la accion o solo se cuenta como error es la accion.
        """
        try:
            with open(ruta, encoding="utf-8") as archivo:
                datos = json.load(archivo)
        except FileNotFoundError:
            return None
        except json.JSONDecodeError as error:
            raise ConfigError("log inválido {}: {}".format(ruta, error)) from error

        if not isinstance(datos, dict):
            raise ConfigError("El log no tiene el formato esperado: {}".format(ruta))
        return datos
