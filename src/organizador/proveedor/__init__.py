"""Proveedores de IA: contrato comun, HTTP opcional y fallback local."""

from .api import ProveedorApi
from .base import Explicacion, ProveedorIA, Sugerencia
from .heuristico import ProveedorHeuristico

__all__ = [
    "Explicacion",
    "ProveedorApi",
    "ProveedorHeuristico",
    "ProveedorIA",
    "Sugerencia",
]
