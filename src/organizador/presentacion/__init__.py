"""Capa de presentacion: todo lo que toca stdout/stderr/stdin vive aqui.

Las acciones devuelven resumenes; la presentacion decide como mostrarlos
(humano o JSON) y donde (stdout o stderr). Separarlo permite probar las
acciones sin capturar salida y anadir formatos nuevos sin tocarlas.
"""

from .consola import Consola
from .salida_json import emitir_json, error_json

__all__ = ["Consola", "emitir_json", "error_json"]
