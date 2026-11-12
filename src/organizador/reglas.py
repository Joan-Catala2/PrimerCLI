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
    texto = re.sub(r"[._\-\s]+", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def _partes(nombre_archivo):
    """Trocea el stem por separadores (_ - . espacios), ya normalizadas."""
    stem = Path(nombre_archivo).stem
    return [normalizar(p) for p in re.split(r"[._\-\s]+", stem) if p]


def _tokens(nombre_archivo):
    """Como `_partes`, pero ademas separa camelCase ('BaseDeDatos')."""
    tokens = []
    for parte in _partes(nombre_archivo):
        tokens.extend(p for p in re.split(r"(?<=[a-z])(?=[A-Z])", parte) if p)
    return tokens


def _coincide(tokens, alias):
    """Coincidencia por palabras: el alias debe aparecer como secuencia de
    tokens consecutivos. Cubre 'BaseDeDatos_sql' y 'BaseDeDatos_sql'."""
    objetivo = normalizar(alias).split(" ")
    n = len(objetivo)
    for i in range(len(tokens) - n + 1):
        if tokens[i : i + n] == objetivo:
            return True
    return False


def _pega(nombre_archivo, alias):
    """Coincidencia compacta: alias pegado al nombre sin separadores.

    Permite 'trabajosql', 'basededatos' o 'sql_apuntes'. Para no generar
    falsos positivos ('fol' dentro de 'folder', 'ipe' dentro de 'recipe')
    se aplican estas reglas:
      - varias palabras: subcadena si tiene 4+ letras;
      - una palabra de 4+ letras: al principio o al final;
      - una palabra de 3 letras: solo al final, tras una vocal y con al
        menos 3 letras delante ('trabajosql' si, 'digit'/'recipe' no);
      - 2 letras o menos: nunca (se exige palabra completa).
    """
    alias_norm = normalizar(alias)
    compacto = alias_norm.replace(" ", "")
    if not compacto:
        return False
    texto = "".join(_partes(nombre_archivo))
    if " " in alias_norm:
        return len(compacto) >= 4 and compacto in texto
    if len(compacto) >= 4:
        return texto.startswith(compacto) or texto.endswith(compacto)
    if len(compacto) == 3:
        if not texto.endswith(compacto):
            return False
        prefijo = texto[:-3]
        return len(prefijo) >= 3 and prefijo[-1] in "aeiouy"
    return False


def clasificar(nombre_archivo):
    """Devuelve (asignatura, tema) o None si no se puede clasificar."""
    tokens = _tokens(nombre_archivo)

    def encaja(alias):
        return _coincide(tokens, alias) or _pega(nombre_archivo, alias)

    for regla in REGLAS:
        if not any(encaja(a) for a in regla.aliases):
            continue
        for tema, temas_aliases in regla.temas:
            if any(encaja(a) for a in temas_aliases):
                return regla.asignatura, tema
        return regla.asignatura, ""

    return None
