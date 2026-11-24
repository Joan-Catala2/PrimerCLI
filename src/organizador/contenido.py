"""Contenido de los archivos: lectura opcional de PDF para clasificar.

Este modulo existe para que la CLI pueda organizar apuntes cuyo nombre no
dice nada (`Tema4.pdf`) leyendo las primeras paginas del PDF. Tres reglas
de diseno (ADR-006) lo mantienen a raya:

- **Opt-in**: solo se usa con `--contenido`; sin flag nada cambia.
- **El nombre siempre manda**: el contenido es un segundo intento para lo
  que por nombre caeria en `_revision`.
- **Frontera de palabra**: el texto del PDF es continuo; `SQL` no puede
  casar dentro de `mysql`. Los alias de un digito o dos del catalogo
  (temas `1`, `2`, `T1`...) no valen aqui: serian falsos positivos.

La dependencia (`pypdf`) es opcional: se importa dentro de `texto_pdf`.
Sin el extra, la CLI responde un error humano con el comando de
instalacion, nunca un traceback.
"""

import importlib
import re
import unicodedata

from .excepciones import ErrorDeUso

#: Paginas leidas por defecto: portada e indice suelen bastar.
MAX_PAGINAS_POR_DEFECTO = 3

#: Un texto plano no necesita mas: las portadas utiles caben con creces.
LIMITE_CARACTERES = 4000

#: Alias mas cortos aceptados en contenido (ver ADR-006, punto 5).
LARGO_MINIMO_ALIAS = 3

_MENSAJE_SIN_EXTRA = (
    "Leer el contenido de los PDFs necesita la dependencia opcional "
    "`pypdf`: instalala con `pip install organizador[pdf]`."
)


class ExtraccionFallida(Exception):
    """El PDF no se puede leer (cifrado, corrupto o sin paginas).

    Es un caso previsto, no un error de la CLI: el archivo sigue su camino
    (a `_revision` si nada mas lo salva) y el fallo se informa como aviso.
    """


def _normalizar(texto):
    """Parecido a `reglas.normalizar` pero conservando los espacios.

    El texto extraido ya viene con espacios; lo que hace falta es poder
    casar alias con espacios contra el texto tal cual. Minusculas, sin
    tildes, NFKD y espacios colapsados.
    """
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = texto.lower()
    return re.sub(r"\s+", " ", texto).strip()


def _frontera(token):
    """Regex de frontera de palabra para un alias normalizado.

    `\\w` trata los digitos como palabra, asi que `sql` no casa dentro de
    `mysql` ni `tema 4` lo hace dentro de `tema4`, pero si ante `tema 4:`,
    `(tema 4)` o el final del texto.
    """
    return re.compile(r"(?<!\w)" + re.escape(token) + r"(?!\w)")


def _alias_usable(alias):
    """Un alias de 1 o 2 letras (temas `1`, `T1`) es ruido dentro de un
    texto continuo: no se usa para clasificar por contenido."""
    compacto = _normalizar(alias).replace(" ", "")
    return len(compacto) >= LARGO_MINIMO_ALIAS


def _leer_pdf(ruta, max_paginas):
    """Lee el PDF con `pypdf` y devuelve su texto acotado.

    La importacion de `pypdf` vive aqui, en el unico punto del paquete que
    lo conoce: sin el extra `organizador[pdf]` falla y se traduce a
    `ErrorDeUso` con instrucciones (el mensaje NO debe contener "pypdf":
    el scanner anti-claves lo marcaria, y el usuario solo necesita el
    comando de instalacion). Los fallos del lector (cifrado, corrupto) se
    convierten en `ExtraccionFallida`, que los llamadores tratan como
    aviso.
    """
    try:
        importlib.import_module("pypdf")
    except ImportError as error:
        raise ErrorDeUso(_MENSAJE_SIN_EXTRA) from error

    # El import esta arriba; aqui se usa la via canonica para que mypy y
    # cualquier releedor vean de donde sale el modulo.
    pypdf = importlib.import_module("pypdf")
    try:
        lector = pypdf.PdfReader(str(ruta))
        if getattr(lector, "is_encrypted", False):
            raise ExtraccionFallida("el PDF esta cifrado")
        paginas = list(lector.pages)[: int(max_paginas)]
        trozos = []
        for pagina in paginas:
            trozos.append(pagina.extract_text() or "")
            if sum(len(t) for t in trozos) >= LIMITE_CARACTERES:
                break
    except ExtraccionFallida:
        raise
    except Exception as error:  # pypdf lanza de todo: nada debe romper la CLI
        raise ExtraccionFallida("el PDF no se pudo leer ({})".format(error)) from error

    texto = " ".join(trozos)
    return texto[:LIMITE_CARACTERES]


def texto_pdf(ruta, max_paginas=MAX_PAGINAS_POR_DEFECTO):
    """Devuelve el texto de las `max_paginas` primeras paginas de un PDF.

    Punto de entrada que usa la CLI (inyectada como extractor en el
    motor). Valida `max_paginas` con `ErrorDeUso` ademas de leer: la
    accion ya lo habra chequeado, pero el coste es una comparacion y la
    garantia de que nadie monta un extractor con 0 paginas por su cuenta.
    """
    if max_paginas < 1:
        raise ErrorDeUso("--contenido-max-paginas debe ser 1 o mas.")
    return _leer_pdf(ruta, max_paginas)


def clasificar_por_contenido(texto, reglas=None):
    """Segundo intento: `(asignatura, tema)` leyendo el texto, o None.

    Comparte la idea de `reglas.clasificar` (la primera regla cuya
    asignatura case, manda) pero empareja con fronteras de palabra sobre
    texto continuo. El tema solo se detecta si su alias es largo y casa;
    si no, la clasificacion es sin tema (la carpeta de la asignatura).

    Devuelve `(pareja, detalle)`: `pareja` al estilo `clasificar` y
    `detalle` como el de `reglas.explicar_match` (con `origen="contenido"`
    y `tipo="texto"`), para que `explicar` y el JSON cuenten de donde salio
    la clasificacion. `(None, None)` si el texto no casa con nada.
    Si la asignatura casa pero ningun alias de tema lo hace, el tema queda
    vacio (la carpeta de la asignatura). Comparte el orden del catalogo:
    la primera regla cuya asignatura aparece, gana.
    """
    texto_norm = _normalizar(texto)
    if not texto_norm:
        return None, None
    if reglas is None:
        from .reglas import REGLAS_DEL_PAQUETE

        reglas = REGLAS_DEL_PAQUETE

    for regla in reglas:
        alias_asignatura = _primer_alias_en_texto(texto_norm, regla.aliases)
        if alias_asignatura is None:
            continue
        tema = ""
        alias_tema = ""
        for tema_posible, aliases_tema in regla.temas:
            alias = _primer_alias_en_texto(texto_norm, aliases_tema)
            if alias is not None:
                tema, alias_tema = tema_posible, alias
                break
        return (
            (regla.asignatura, tema),
            {
                "asignatura": regla.asignatura,
                "tema": tema,
                "alias": alias_tema or alias_asignatura,
                "alias_asignatura": alias_asignatura,
                "alias_tema": alias_tema,
                "tipo": "texto",
                "origen": "contenido",
                "razon": (
                    "El alias '{}' de {} encaja por texto del documento; el "
                    "alias '{}' del tema {} también.".format(
                        alias_asignatura,
                        regla.asignatura,
                        alias_tema,
                        tema,
                    )
                    if tema
                    else "El alias '{}' de {} encaja por texto del documento; "
                    "ningún alias de tema encaja, así que sin tema.".format(
                        alias_asignatura, regla.asignatura
                    )
                ),
            },
        )
    return None, None


def _primer_alias_en_texto(texto_norm, aliases):
    """Alias (normalizado) que casa con el texto, o None.

    Respeta el orden de `aliases` igual que `reglas._primera_coincidencia`:
    el primero del catálogo que aparece, gana.
    """
    for alias in aliases:
        if not _alias_usable(alias):
            continue
        if _coincide_texto(texto_norm, alias):
            return alias
    return None


def _coincide_texto(texto_norm, alias):
    return _frontera(_normalizar(alias)).search(texto_norm) is not None
