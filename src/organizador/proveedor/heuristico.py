"""Fallback sin red: usa las reglas de `reglas.json` como "IA" local.

No es un proveedor de verdad, pero tiene el mismo contrato. Por eso
`sugerir` y `explicar` siguen siendo útiles aunque no haya clave, no haya
internet o la API falle a mitad de la demostración.
"""

from typing import Sequence

from ..reglas import explicar_match
from .base import Explicacion, ProveedorIA, Sugerencia


class ProveedorHeuristico(ProveedorIA):
    """Sugerencias deterministas derivadas de los aliases del JSON."""

    nombre = "heuristica"
    disponible = False

    def sugerir(self, nombres: Sequence[str], reglas: Sequence) -> Sequence[Sugerencia]:
        resultado = []
        for nombre in nombres:
            coincidencia = explicar_match(nombre, reglas)
            if coincidencia is None:
                resultado.append(
                    Sugerencia(
                        nombre=nombre,
                        fuente=self.nombre,
                        razon="Ningún alias de las reglas coincide con este nombre.",
                    )
                )
                continue
            confianza = 0.8 if coincidencia["tipo"] == "palabra completa" else 0.6
            resultado.append(
                Sugerencia(
                    nombre=nombre,
                    asignatura=coincidencia["asignatura"],
                    tema=coincidencia["tema"],
                    confianza=confianza,
                    fuente=self.nombre,
                    razon=coincidencia["razon"],
                )
            )
        return resultado

    def explicar(self, nombre: str, destino: str, reglas: Sequence) -> Explicacion:
        coincidencia = explicar_match(nombre, reglas)
        if coincidencia is not None:
            texto = coincidencia["razon"]
        else:
            texto = (
                "Ningún alias de las reglas coincide con '{}'; por eso acabaría "
                "en _revision.".format(nombre)
            )
        return Explicacion(texto=texto, fuente=self.nombre, razon_local=texto)
