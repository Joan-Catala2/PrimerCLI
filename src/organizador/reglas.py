"""Carga y validacion de las reglas de clasificacion (reglas.json).

Las asignaturas, palabras clave y temas viven en `reglas.json`. Este modulo
solo se encarga de leerlas, validarlas y clasificar nombres de archivo.

Las reglas del paquete se cargan y validan una sola vez al importar
(`REGLAS_DEL_PAQUETE`): el JSON es inmutable durante la vida del proceso y
releerlo en cada clasificacion seria trabajo repetido sin beneficio. Las
reglas del usuario NO se cachean: pueden cambiar entre ejecuciones y se leen
una vez por accion desde `reglas_efectivas`.
"""

import json
import os
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .excepciones import ConfigError

REVISION = "_revision"
ARCHIVO_REGLAS = "reglas.json"


@dataclass(frozen=True)
class Regla:
    asignatura: str
    aliases: tuple
    temas: tuple  # ((tema, (alias, ...)), ...)


def _error(ruta, indice, mensaje):
    return ConfigError("Regla {} en {}: {}".format(indice + 1, ruta, mensaje))


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


@lru_cache(maxsize=None)
def cargar_reglas(ruta=None):
    """Carga y valida `reglas.json`. Devuelve una tupla de Regla.

    Cacheada: el JSON del paquete es inmutable durante la vida del
    proceso, y los ficheros de usuario/tmp no cambian mientras una
    accion los usa. La lectura y validacion ocurre una sola vez por ruta.
    """
    ruta = Path(ruta) if ruta is not None else Path(__file__).with_name(ARCHIVO_REGLAS)

    try:
        with open(ruta, encoding="utf-8") as archivo:
            datos = json.load(archivo)
    except FileNotFoundError as error:
        raise ConfigError("No existe el fichero de reglas: {}".format(ruta)) from error
    except IsADirectoryError as error:
        raise ConfigError(
            "La ruta de reglas es una carpeta, no un fichero: {}".format(ruta)
        ) from error
    except PermissionError as error:
        # Windows no devuelve IsADirectoryError al abrir un directorio:
        # dice PermissionError. La comprobacion es posterior y manda.
        if Path(ruta).is_dir():
            raise ConfigError(
                "La ruta de reglas es una carpeta, no un fichero: {}".format(ruta)
            ) from error
        raise ConfigError(
            "No se puede leer el fichero de reglas: {}".format(ruta)
        ) from error
    except json.JSONDecodeError as error:
        raise ConfigError("JSON invalido en {}: {}".format(ruta, error)) from error

    if not isinstance(datos, list) or not datos:
        raise ConfigError("{} debe contener una lista no vacia de reglas".format(ruta))

    reglas = tuple(_cargar_regla(item, ruta, i) for i, item in enumerate(datos))

    nombres = [regla.asignatura for regla in reglas]
    duplicadas = sorted({nombre for nombre in nombres if nombres.count(nombre) > 1})
    if duplicadas:
        raise ConfigError(
            "Asignaturas duplicadas en {}: {}".format(ruta, ", ".join(duplicadas))
        )

    return reglas


def ruta_reglas_usuario():
    """Ruta de las reglas del usuario (~/.config/organizador/reglas.json)."""
    base = os.environ.get("XDG_CONFIG_HOME")
    config = Path(base) if base else Path.home() / ".config"
    return config / "organizador" / ARCHIVO_REGLAS


def reglas_efectivas(ruta=None):
    """Reglas que se usaran, como tupla de Regla.

    - Con `ruta`: solo se cargan las reglas de ese fichero.
    - Sin `ruta`: se cargan las del usuario (si existen) y despues las del
      paquete (cacheadas). Si una asignatura esta en ambas, gana la del
      usuario.

    Se llama una sola vez por accion (las acciones la reciben inyectada),
    asi que no conviene cachear aqui las reglas del usuario.
    """
    if ruta is not None:
        return cargar_reglas(ruta)

    reglas = []
    vistas = set()

    usuario = ruta_reglas_usuario()
    if usuario.is_file():
        for regla in cargar_reglas(usuario):
            reglas.append(regla)
            vistas.add(regla.asignatura)

    for regla in REGLAS_DEL_PAQUETE:
        if regla.asignatura not in vistas:
            reglas.append(regla)

    return tuple(reglas)


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
    tokens: list = []
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


def _primera_coincidencia(nombre_archivo, aliases, tokens):
    """Devuelve (alias, tipo) del primero que encaja, o None."""
    for alias in aliases:
        if _coincide(tokens, alias):
            return alias, "palabra completa"
        if _pega(nombre_archivo, alias):
            return alias, "texto pegado"
    return None


def explicar_match(nombre_archivo, reglas=None):
    """Detalla por qué un nombre encaja con una regla, o devuelve None.

    Es la misma decision que toma `clasificar`, pero conserva el alias y el
    tipo de coincidencia. Lo usan las acciones `explicar` y `sugerir` cuando
    no hay proveedor de IA: la respuesta sigue siendo útil y auditable.
    """
    tokens = _tokens(nombre_archivo)
    usadas = REGLAS_DEL_PAQUETE if reglas is None else reglas

    for regla in usadas:
        asignatura_match = _primera_coincidencia(nombre_archivo, regla.aliases, tokens)
        if asignatura_match is None:
            continue
        alias_asignatura, tipo_asignatura = asignatura_match

        for tema, aliases_tema in regla.temas:
            tema_match = _primera_coincidencia(nombre_archivo, aliases_tema, tokens)
            if tema_match is not None:
                alias_tema, tipo_tema = tema_match
                razon = (
                    "El alias '{}' de {} encaja por {} en '{}', y el alias '{}' "
                    "del tema {} también encaja por {}.".format(
                        alias_asignatura,
                        regla.asignatura,
                        tipo_asignatura,
                        nombre_archivo,
                        alias_tema,
                        tema,
                        tipo_tema,
                    )
                )
                return {
                    "asignatura": regla.asignatura,
                    "tema": tema,
                    "alias": alias_tema,
                    "alias_asignatura": alias_asignatura,
                    "alias_tema": alias_tema,
                    "tipo": tipo_tema,
                    "razon": razon,
                }

        return {
            "asignatura": regla.asignatura,
            "tema": "",
            "alias": alias_asignatura,
            "alias_asignatura": alias_asignatura,
            "alias_tema": "",
            "tipo": tipo_asignatura,
            "razon": (
                "El alias '{}' de {} encaja por {} en '{}'; ningún alias de "
                "tema encaja, así que se clasifica sin tema.".format(
                    alias_asignatura,
                    regla.asignatura,
                    tipo_asignatura,
                    nombre_archivo,
                )
            ),
        }

    return None


def clasificar(nombre_archivo, reglas=None):
    """Devuelve (asignatura, tema) o None si no se puede clasificar.

    `reglas` permite clasificar con una tupla de Regla distinta a la del
    paquete (por ejemplo, reglas personalizadas del usuario). Comparte el
    emparejamiento con `explicar_match` para que explicar y clasificar nunca
    se contradigan.
    """
    coincidencia = explicar_match(nombre_archivo, reglas)
    if coincidencia is None:
        return None
    return coincidencia["asignatura"], coincidencia["tema"]


# Unico punto donde se leen y validan las reglas del paquete, una sola vez.
REGLAS_DEL_PAQUETE = cargar_reglas()
