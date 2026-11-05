"""Reglas de clasificacion por nombre de archivo.

Cada asignatura tiene palabras clave y, opcionalmente, temas con sus
propias palabras clave. La coincidencia se hace sobre el nombre del
archivo normalizado (minusculas, sin tildes, separadores convertidos en
espacios).
"""

from dataclasses import dataclass
import re
import unicodedata

REVISION = "_revision"


@dataclass(frozen=True)
class Regla:
    asignatura: str
    aliases: tuple
    temas: tuple  # ((tema, (alias, ...)), ...)


REGLAS = (
    Regla(
        "Matematicas",
        ("matematicas", "mates", "calcul", "algebra", "derivada", "integral", "funcion"),
        (
            ("Derivadas", ("derivada", "diferenciacion")),
            ("Integrales", ("integral",)),
            ("Funciones", ("funcion", "funciones")),
            ("Algebra", ("algebra", "matriz", "matrices")),
        ),
    ),
    Regla(
        "Historia",
        ("historia", "edadmoderna", "edad media", "revolucion"),
        (
            ("EdadMedia", ("edad media", "media")),
            ("EdadModerna", ("edad moderna", "moderna")),
            ("RevolucionIndustrial", ("revolucion industrial", "industrial")),
        ),
    ),
    Regla(
        "Lengua",
        ("lengua", "sintaxis", "morfologia", "literatura", "comentario"),
        (
            ("Sintaxis", ("sintaxis", "oracion", "oraciones")),
            ("Morfologia", ("morfologia", "palabra", "palabras")),
            ("Literatura", ("literatura", "comentario", "poema")),
        ),
    ),
    Regla(
        "Ingles",
        ("ingles", "english", "phrasal"),
        (
            ("PhrasalVerbs", ("phrasal", "verb", "verbs")),
            ("Vocabulario", ("vocabulary", "vocabulario")),
        ),
    ),
    Regla(
        "Fisica",
        ("fisica", "cinematica", "cinematic", "newton", "energia"),
        (
            ("Cinematica", ("cinematica", "cinematic", "movimiento")),
            ("Dinamica", ("dinamica", "newton", "fuerza")),
            ("Energia", ("energia", "energy")),
        ),
    ),
    Regla(
        "Quimica",
        ("quimica", "molecula", "reaccion", "formula"),
        (
            ("Formulacion", ("formulacion", "formula")),
            ("Reacciones", ("reaccion", "reacciones")),
        ),
    ),
    Regla(
        "Biologia",
        ("biologia", "celula", "genetica", "ecosistema"),
        (
            ("Celula", ("celula", "celulas")),
            ("Genetica", ("genetica", "adn", "dna")),
        ),
    ),
)


def normalizar(texto):
    """Pasa a minusculas, quita tildes y uniformiza separadores."""
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = texto.lower()
    texto = re.sub(r"[._\-]+", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def _contiene(nombre, alias):
    alias = normalizar(alias)
    return re.search(r"(?:^|\s|/)" + re.escape(alias), nombre) is not None


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
