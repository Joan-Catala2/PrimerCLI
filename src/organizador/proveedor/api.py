"""Proveedor HTTP compatible con la API de chat de OpenAI.

Usa solo `urllib` (stdlib): no añade dependencias, no cambia la instalación
en una orden y no guarda la clave en ningún fichero. Si la red falla o la
respuesta no es el JSON esperado, lanza `IAIndisponible` y la accion decide
seguir con las reglas locales.
"""

import json
import urllib.error
import urllib.request
from typing import Dict, Sequence

from ..excepciones import IAIndisponible
from .base import Explicacion, ProveedorIA, Sugerencia
from .heuristico import ProveedorHeuristico


class ProveedorApi(ProveedorIA):
    """Cliente minimo de un endpoint de chat completions."""

    nombre = "ia"
    disponible = True
    TIEMPO_ESPERA = 10

    def __init__(self, clave, url, modelo, abrir=None):
        self._clave = clave
        self.url = url
        self.modelo = modelo
        self._abrir = abrir or urllib.request.urlopen

    def __repr__(self):
        return "ProveedorApi(url={!r}, modelo={!r}, clave=<oculta>)".format(
            self.url, self.modelo
        )

    __str__ = __repr__

    def sugerir(self, nombres: Sequence[str], reglas: Sequence) -> Sequence[Sugerencia]:
        nombres = list(nombres)
        if not nombres:
            return []

        catalogo = self._catalogo(reglas)
        locales = ProveedorHeuristico().sugerir(nombres, reglas)
        instruccion = (
            "Eres un ayudante que clasifica archivos de estudio. Responde SOLO "
            "un objeto JSON con una clave 'sugerencias' y una entrada por nombre "
            "con: nombre, asignatura, tema, confianza (0..1) y razon. Elige "
            "asignaturas y temas SOLO de las listas dadas. Si no sabes, deja "
            "asignatura y tema vacíos."
        )
        datos = {
            "nombres": nombres,
            "asignaturas": sorted(catalogo["asignaturas"]),
            "temas": catalogo["temas"],
            "locales": [local.a_dict() for local in locales],
        }
        respuesta = self._pedir(instruccion, json.dumps(datos, ensure_ascii=False))
        crudos = respuesta.get("sugerencias")
        if not isinstance(crudos, list):
            raise IAIndisponible("la IA no devolvió una lista de sugerencias")

        por_nombre = {
            item.get("nombre"): item for item in crudos if isinstance(item, dict)
        }
        resultado = []
        for local in locales:
            crudo = por_nombre.get(local.nombre)
            if not isinstance(crudo, dict):
                resultado.append(local)
                continue

            asignatura = str(crudo.get("asignatura") or "")
            if asignatura not in catalogo["asignaturas"]:
                resultado.append(local)
                continue
            tema = str(crudo.get("tema") or "")
            if tema and tema not in catalogo["temas"].get(asignatura, ()):
                tema = local.tema

            try:
                confianza = float(crudo.get("confianza", local.confianza))
            except (TypeError, ValueError):
                confianza = local.confianza
            if not 0.0 <= confianza <= 1.0:
                confianza = local.confianza

            razon = str(crudo.get("razon") or local.razon)
            resultado.append(
                Sugerencia(
                    nombre=local.nombre,
                    asignatura=asignatura,
                    tema=tema,
                    confianza=confianza,
                    fuente=self.nombre,
                    razon=razon,
                )
            )
        return resultado

    def explicar(self, nombre: str, destino: str, reglas: Sequence) -> Explicacion:
        local = ProveedorHeuristico().explicar(nombre, destino, reglas)
        instruccion = (
            "Explica en una frase breve por qué ese nombre de archivo acaba en "
            "ese destino. Usa la explicación local como punto de partida y no "
            "inventes reglas nuevas. Responde SOLO un JSON con la clave 'texto'."
        )
        datos = {
            "nombre": nombre,
            "destino": destino,
            "explicacion_local": local.texto,
        }
        respuesta = self._pedir(instruccion, json.dumps(datos, ensure_ascii=False))
        texto = respuesta.get("texto")
        if not isinstance(texto, str) or not texto.strip():
            raise IAIndisponible("la IA no devolvió una explicación usable")
        return Explicacion(
            texto=texto.strip(), fuente=self.nombre, razon_local=local.texto
        )

    # --- protocolo --------------------------------------------------------

    @staticmethod
    def _catalogo(reglas):
        asignaturas = set()
        temas: Dict[str, tuple] = {}
        for regla in reglas or ():
            asignaturas.add(regla.asignatura)
            temas[regla.asignatura] = tuple(nombre for nombre, _ in regla.temas)
        return {"asignaturas": asignaturas, "temas": temas}

    def _pedir(self, instruccion, contenido):
        peticion = {
            "model": self.modelo,
            "messages": [
                {"role": "system", "content": instruccion},
                {"role": "user", "content": contenido},
            ],
            "temperature": 0,
        }
        solicitud = urllib.request.Request(
            self.url,
            data=json.dumps(peticion).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer {}".format(self._clave),
            },
            method="POST",
        )
        try:
            with self._abrir(solicitud, timeout=self.TIEMPO_ESPERA) as respuesta:
                cuerpo = json.loads(respuesta.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as error:
            raise IAIndisponible(
                "no se pudo contactar con el proveedor de IA: {}".format(error)
            ) from error

        try:
            contenido_ia = cuerpo["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise IAIndisponible("la respuesta de la IA no tiene el formato esperado")
        if not isinstance(contenido_ia, str):
            raise IAIndisponible("la respuesta de la IA no es texto")

        texto = contenido_ia.strip()
        if texto.startswith("```"):
            texto = texto.strip("`")
            if texto.startswith("json"):
                texto = texto[4:].strip()
        try:
            objeto = json.loads(texto)
        except json.JSONDecodeError as error:
            raise IAIndisponible("la respuesta de la IA no era JSON válido") from error
        if not isinstance(objeto, dict):
            raise IAIndisponible("la respuesta de la IA no era un objeto JSON")
        return objeto
