"""Contrato del proveedor de IA y los datos que intercambia con las acciones.

Igual que `Accion`, el proveedor tiene una fabrica (`desde_env`) y dos
metodos pequeños. Las acciones no saben si hay HTTP detras: reciben
`Sugerencia` y `Explicacion`, y pueden cambiar de proveedor sin cambiar de
comando.
"""

import abc
import os
from dataclasses import asdict, dataclass
from typing import Dict, Sequence


@dataclass(frozen=True)
class Sugerencia:
    """Propuesta para un archivo: destino, confianza y origen de la idea."""

    nombre: str
    asignatura: str = ""
    tema: str = ""
    confianza: float = 0.0
    fuente: str = "heuristica"
    razon: str = ""

    def a_dict(self) -> Dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class Explicacion:
    """Texto que justifica una clasificacion y su procedencia."""

    texto: str
    fuente: str = "heuristica"
    razon_local: str = ""

    def a_dict(self) -> Dict[str, object]:
        return asdict(self)


class ProveedorIA(abc.ABC):
    """Interfaz comun: sugerir en lote y explicar un caso concreto."""

    nombre = "base"
    disponible = False

    @staticmethod
    def desde_env() -> "ProveedorIA":
        """Construye el proveedor real solo si esta completamente configurado.

        Se exigen las tres variables (`ORGANIZADOR_API_KEY`,
        `ORGANIZADOR_IA_URL` y `ORGANIZADOR_IA_MODELO`) para que nadie llame
        a un servicio de pago por accidente. Sin ellas se usan las reglas
        locales, que no cuestan nada y funcionan sin red.
        """
        from .api import ProveedorApi
        from .heuristico import ProveedorHeuristico

        clave = os.environ.get("ORGANIZADOR_API_KEY", "").strip()
        url = os.environ.get("ORGANIZADOR_IA_URL", "").strip()
        modelo = os.environ.get("ORGANIZADOR_IA_MODELO", "").strip()
        if not (clave and url and modelo):
            return ProveedorHeuristico()
        return ProveedorApi(clave=clave, url=url, modelo=modelo)

    @abc.abstractmethod
    def sugerir(self, nombres: Sequence[str], reglas: Sequence) -> Sequence[Sugerencia]:
        """Devuelve una sugerencia por nombre, en el mismo orden."""

    @abc.abstractmethod
    def explicar(self, nombre: str, destino: str, reglas: Sequence) -> Explicacion:
        """Explica por qué ese nombre acaba en ese destino."""
