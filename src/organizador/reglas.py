"""Carga y validacion de las reglas de clasificacion (reglas.json).

Las asignaturas, palabras clave y temas viven en `reglas.json`. Este modulo
solo se encarga de leerlas, validarlas y clasificar nombres de archivo.
"""

from dataclasses import dataclass
import json
from pathlib import Path
import re
import unicodedata

REVISION = "_revision"
ARCHIVO_REGLAS = "reglas.json"


@dataclass(frozen=True)
class Regla:
    asignatura: str
    aliases: tuple
    temas: tuple  # ((tema, (alias, ...)), ...)


def _error(ruta, indice, mensaje):
    return ValueError("Regla {} en {}: {}".format(indice + 1, ruta, mensaje))


def _lista_textos(valor, campo, ruta, indice):
    """Valida una lista de textos no vacios y la devuelve como tupla."""
    if not isinstance(valor, list) or not valor:
        raise _error(ruta, indice, "'{}' debe ser una lista no vacia".format(campo))
    textos = []
    for item in valor:
        if not isinstance(item, str) or not item.strip():
            raise _error(
                ruta, indice, "'{}' solo puede contener textos no vacios".format(campo)
            )
        textos.append(item.strip())
    return tuple(textos)


def _cargar_regla(datos, ruta, indice):
    """Valida un objeto de regla y lo convierte en Regla."""
    if not isinstance(datos, dict):
        raise _error(ruta, indice, "debe ser un objeto JSON")

    asignatura = datos.get("asignatura")
    if not isinstance(asignatura, str) or not asignatura.strip():
        raise _error(ruta, indice, "'asignatura' debe ser un texto no vacio")

    aliases = _lista_textos(datos.get("aliases"), "aliases", ruta, indice)

    temas_datos = datos.get("temas", [])
    if not isinstance(temas_datos, list):
        raise _error(ruta, indice, "'temas' debe ser una lista")

    temas = []
    for tema_datos in temas_datos:
        if not isinstance(tema_datos, dict):
            raise _error(ruta, indice, "cada tema debe ser un objeto JSON")
        tema = tema_datos.get("tema")
        if not isinstance(tema, str) or not tema.strip():
            raise _error(ruta, indice, "'tema' debe ser un texto no vacio")
        temas.append(
            (
                tema.strip(),
                _lista_textos(tema_datos.get("aliases"), "aliases", ruta, indice),
            )
        )

    return Regla(asignatura.strip(), aliases, tuple(temas))


def cargar_reglas(ruta=None):
    """Carga y valida `reglas.json`. Devuelve una tupla de Regla."""
    ruta = Path(ruta) if ruta is not None else Path(__file__).with_name(ARCHIVO_REGLAS)

    with open(ruta, encoding="utf-8") as archivo:
        try:
            datos = json.load(archivo)
        except json.JSONDecodeError as error:
            raise ValueError("JSON invalido en {}: {}".format(ruta, error)) from error

    if not isinstance(datos, list) or not datos:
        raise ValueError("{} debe contener una lista no vacia de reglas".format(ruta))

    reglas = tuple(_cargar_regla(item, ruta, i) for i, item in enumerate(datos))

    nombres = [regla.asignatura for regla in reglas]
    duplicadas = sorted({nombre for nombre in nombres if nombres.count(nombre) > 1})
    if duplicadas:
        raise ValueError(
            "Asignaturas duplicadas en {}: {}".format(ruta, ", ".join(duplicadas))
        )

    return reglas


REGLAS = cargar_reglas()


def normalizar(texto):
    """Pasa a minusculas, quita tildes y uniformiza separadores."""
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = texto.lower()
    texto = re.sub(r"[._\-]+", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def _contiene(nombre, alias):
    alias = normalizar(alias)
    patron = r"(?:^|\s|/)" + re.escape(alias) + r"(?=\s|$|/)"
    return re.search(patron, nombre) is not None


def clasificar(nombre_archivo):
    """Devuelve (asignatura, tema) o None si no se puede clasificar."""
    nombre = normalizar(nombre_archivo)

    for regla in REGLAS:
        if not any(_contiene(nombre, a) for a in regla.aliases):
            continue
        for tema, temas_aliases in regla.temas:
            if any(_contiene(nombre, a) for a in temas_aliases):
                return regla.asignatura, tema
        return regla.asignatura, ""

    return None
