"""Clase base de las acciones y utilidades compartidas."""

import abc

from ..excepciones import ErrorDeUso


class Accion(abc.ABC):
    """Contrato comun de los comandos: `desde_config` + `ejecutar`.

    `desde_config` (patron de fabrica): construye la accion con sus
    dependencias ya resueltas (consola, registro, reglas) a partir de los
    argumentos parseados. De ahi que los errores de configuracion imposible
    (`ErrorDeUso`, `ConfigError`) salgan al construir, antes de tocar
    ningun archivo.

    `ejecutar` devuelve el codigo de salida de la CLI (0 = todo bien).
    """

    nombre = ""

    def __init__(self, consola):
        self.consola = consola

    @classmethod
    @abc.abstractmethod
    def desde_config(cls, args, consola) -> "Accion":
        """Construye la accion desde la configuracion parseada."""

    @abc.abstractmethod
    def ejecutar(self):
        """Realiza la accion y devuelve el codigo de salida."""

    @staticmethod
    def validar_ultimos(valor):
        """Rechaza `--ultimos` sin sentido antes de tocar el historial."""
        if valor < 1:
            raise ErrorDeUso("--ultimos debe ser 1 o mas.")
        return valor
