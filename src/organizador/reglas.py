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
        "BaseDeDatos",
        ("base de datos", "bases de datos", "base de dades", "bases de dades", "basededatos", "basededades", "bd", "bbdd", "sql"),
        (
            ("SQL", ("sql", "consulta", "consultas")),
            ("ModeloEntidadRelacion", ("entidad relacion", "modelo relacional", "er")),
            ("Normalizacion", ("normalizacion", "normalitzacio")),
        ),
    ),
    Regla(
        "SistemasInformaticos",
        ("sistemas informaticos", "sistema informatico", "sistemes informatics", "sistema informatic", "sistemasinformaticos", "sistemesinformatics", "hardware", "redes"),
        (
            ("Hardware", ("hardware", "ordenador", "equipo")),
            ("Redes", ("redes", "red", "ip", "tcp")),
            ("SistemasOperativos", ("sistema operativo", "sistema operatiu", "linux", "windows")),
        ),
    ),
    Regla(
        "Programacion",
        ("programacion", "programacio", "programming", "java", "python", "codigo", "algoritmo"),
        (
            ("Java", ("java",)),
            ("Python", ("python",)),
            ("Algoritmos", ("algoritmo", "algoritmos", "pseudocodigo")),
            ("EstructurasDeDatos", ("estructura de datos", "arrays", "listas")),
        ),
    ),
    Regla(
        "ProyectoIntermodular",
        ("proyecto intermodular", "projecte intermodular", "proyectointermodular", "projecteintermodular", "intermodular", "proyecto", "projecte"),
        (),
    ),
    Regla(
        "EntornosDeDesarrollo",
        ("entornos de desarrollo", "entorno de desarrollo", "entorns de desenvolupament", "entornosdedesarrollo", "entornsdedesenvolupament", "git", "ide", "depuracion"),
        (
            ("Git", ("git", "github", "versionado")),
            ("Testing", ("test", "testing", "junit", "pruebas")),
            ("Refactorizacion", ("refactor", "refactorizacion")),
        ),
    ),
    Regla(
        "Ingles",
        ("ingles", "angles", "english", "phrasal"),
        (
            ("PhrasalVerbs", ("phrasal", "verb", "verbs")),
            ("Vocabulario", ("vocabulary", "vocabulario")),
            ("Gramatica", ("grammar", "gramatica")),
        ),
    ),
    Regla(
        "IPO",
        ("ipo", "interfaces persona ordenador", "interaccion persona ordenador", "usabilidad"),
        (
            ("Usabilidad", ("usabilidad", "usability")),
            ("Interfaces", ("interfaz", "interfaces", "prototipo", "wireframe")),
        ),
    ),
    Regla(
        "LlenguatgeDeMarques",
        ("llenguatge de marques", "lenguaje de marcas", "llenguatgedemarques", "lenguajedemarcas", "marcas", "html", "css", "xml"),
        (
            ("HTML", ("html",)),
            ("CSS", ("css",)),
            ("XML", ("xml",)),
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
