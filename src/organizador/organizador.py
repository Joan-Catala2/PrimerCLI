"""Motor de organizacion: lee una carpeta y mueve los archivos clasificados."""

import fnmatch
from pathlib import Path
from shutil import move

from .excepciones import CarpetaNoValidaError, afirmar
from .reglas import REVISION, clasificar

NOMBRE_LOG = "organizador.log.json"

# Archivos temporales que no conviene mover.
SUFIJOS_IGNORADOS = (".part", ".crdownload", ".tmp", ".download")


def _debe_ignorar(archivo):
    """True si el archivo es temporal, oculto o el propio log."""
    nombre = archivo.name
    if nombre == NOMBRE_LOG:
        return True
    if nombre.startswith(".") or nombre.startswith("~$"):
        return True
    return archivo.suffix.lower() in SUFIJOS_IGNORADOS


def _dentro_de(ruta, base):
    """True si `ruta` esta dentro de `base` (compatible con Python 3.8)."""
    ruta = Path(ruta).resolve()
    base = Path(base).resolve()
    return ruta == base or base in ruta.parents


def _en_carpeta_oculta(archivo, origen):
    """True si alguna carpeta intermedia (bajo `origen`) empieza por punto."""
    try:
        relativa = Path(archivo).relative_to(Path(origen))
    except ValueError:
        return False
    return any(parte.startswith(".") for parte in relativa.parts[:-1])


def _normalizar_extensiones(extensiones):
    if not extensiones:
        return set()
    normalizadas = set()
    for extension in extensiones:
        extension = extension.strip().lower()
        if not extension:
            continue
        if not extension.startswith("."):
            extension = "." + extension
        normalizadas.add(extension)
    return normalizadas


def _pasa_filtros(archivo, origen, extensiones, excluir, desde):
    """True si el archivo encaja con los filtros pedidos por el usuario."""
    if extensiones and archivo.suffix.lower() not in extensiones:
        return False

    if excluir:
        relativa = str(Path(archivo).relative_to(Path(origen)))
        patrones = (archivo.name, relativa, relativa.replace("\\", "/"))
        if any(
            fnmatch.fnmatch(candidato, patron)
            for patron in excluir
            for candidato in patrones
        ):
            return False

    if desde is not None:
        try:
            if archivo.stat().st_mtime < desde.timestamp():
                return False
        except OSError:
            return False

    return True


def _listar_archivos(origen, recursivo):
    if recursivo:
        candidatos = origen.rglob("*")
    else:
        candidatos = origen.iterdir()
    return sorted(ruta for ruta in candidatos if ruta.is_file())


def _destino_disponible(destino):
    """Evita sobreescribir: añade -1, -2, ... si el nombre ya existe."""
    if not destino.exists():
        return destino
    n = 1
    while True:
        candidato = destino.with_name("{}-{}{}".format(destino.stem, n, destino.suffix))
        if not candidato.exists():
            return candidato
        n += 1


def mover_archivo(archivo, destino_dir):
    """Mueve `archivo` a `destino_dir` sin sobreescribir. Devuelve el destino."""
    archivo = Path(archivo)
    destino_dir = Path(destino_dir)
    destino_dir.mkdir(parents=True, exist_ok=True)
    destino = _destino_disponible(destino_dir / archivo.name)
    move(str(archivo), str(destino))
    return destino


def limpiar_vacias(base):
    """Elimina las carpetas vacias dentro de `base`, sin borrar `base`."""
    base = Path(base)
    if not base.is_dir():
        return

    carpetas = sorted(
        (ruta for ruta in base.rglob("*") if ruta.is_dir()),
        key=lambda ruta: len(ruta.parts),
        reverse=True,
    )
    for carpeta in carpetas:
        try:
            carpeta.rmdir()
        except OSError:
            pass


def _clasificar_por_contenido(archivo, extractor, reglas, avisos):
    """Segundo intento (ADR-006): leer el PDF y casar su texto.

    El extractor es inyectado: el motor no conoce `pypdf`. Si leer o
    casar falla, se anota un aviso y el archivo sigue a `_revision`:
    un PDF ilegible es un caso previsto, no un error. Devuelve
    `(resultado, aviso)`; el aviso es None cuando el resultado existe.
    """
    from .contenido import ExtraccionFallida, clasificar_por_contenido

    try:
        texto = extractor(archivo)
    except ExtraccionFallida as error:
        aviso = "Aviso: {}: {}".format(archivo.name, error)
        avisos.append(aviso)
        return None, aviso
    except OSError as error:
        aviso = "Aviso: {}: {}".format(archivo.name, error)
        avisos.append(aviso)
        return None, aviso
    resultado, _ = clasificar_por_contenido(texto, reglas)
    return resultado, None


def organizar(
    origen,
    salida,
    simular=False,
    reglas=None,
    recursivo=False,
    extensiones=None,
    excluir=None,
    desde=None,
    ignorar=None,
    extractor=None,
    max_paginas=3,
):
    """Mueve cada archivo de `origen` a su carpeta clasificada.

    Si `simular` es True no se mueve nada: solo se calcula el destino.
    `reglas` permite usar una tupla de Regla personalizada; si es None se
    usan las del paquete. `recursivo` recorre subcarpetas; `extensiones`,
    `excluir` y `desde` filtran que archivos se procesan. `ignorar` es una
    lista de rutas que nunca se recorren (por ejemplo, la carpeta de logs).
    `extractor` (opcional, ADR-006) es una funcion `ruta -> texto` que lee
    el contenido de un PDF cuyo nombre no clasifico: si el texto casa con
    una regla, el archivo se organiza por contenido en vez de ir a
    `_revision`. `max_paginas` se pasa al extractor para que la capa de
    accion lo valide con `ErrorDeUso` antes de recorrer nada; el motor no
    la usa (no conoce el formato de lectura).

    Devuelve un dict con el resumen:
      {"organizados": [(archivo, asignatura, tema)],
       "revision": [archivo],
       "movimientos": [{nombre, asignatura, tema, destino}],
       "errores": [{nombre, error}],
       "avisos": [str],
       "filtrados": int}
    """
    origen = Path(origen).resolve()
    salida = Path(salida).resolve()

    if not origen.exists():
        raise CarpetaNoValidaError("No existe la carpeta de origen: {}".format(origen))
    if not origen.is_dir():
        raise CarpetaNoValidaError("El origen no es una carpeta: {}".format(origen))

    def _es_pdf(nombre):
        # `Path.suffix` mira el ultimo punto: `apuntes.pdf` es un PDF a todos
        # los efectos, y el lector no puede decir lo contrario.
        return nombre.lower().endswith(".pdf")

    if salida == origen or origen in salida.parents:
        raise CarpetaNoValidaError(
            "La carpeta de salida no puede estar dentro del origen: {}".format(salida)
        )

    extensiones = _normalizar_extensiones(extensiones)
    excluir = list(excluir or ())
    ignorar = [Path(ruta).resolve() for ruta in (ignorar or ())]

    organizados = []
    revision = []
    movimientos = []
    errores = []
    avisos: list = []
    filtrados = 0
    total_vistos = 0

    for archivo in _listar_archivos(origen, recursivo):
        if _debe_ignorar(archivo):
            continue
        if recursivo and _en_carpeta_oculta(archivo, origen):
            continue
        if any(_dentro_de(archivo, base) for base in ignorar):
            continue
        total_vistos += 1
        if not _pasa_filtros(archivo, origen, extensiones, excluir, desde):
            filtrados += 1
            continue

        try:
            resultado = clasificar(archivo.name, reglas)
            origen_clasificacion = "nombre"
            if resultado is None and extractor is not None and _es_pdf(archivo.name):
                resultado, aviso = _clasificar_por_contenido(
                    archivo, extractor, reglas, avisos
                )
                if resultado is not None:
                    origen_clasificacion = "contenido"
            if resultado is None:
                asignatura, tema = REVISION, ""
            else:
                asignatura, tema = resultado[0], resultado[1]

            destino_dir = salida / asignatura
            if tema:
                destino_dir = destino_dir / tema

            destino = _destino_disponible(destino_dir / archivo.name)

            if not simular:
                destino_dir.mkdir(parents=True, exist_ok=True)
                move(str(archivo), str(destino))

            movimientos.append(
                {
                    "nombre": archivo.name,
                    "asignatura": asignatura,
                    "tema": tema,
                    "destino": str(destino),
                    "origen": origen_clasificacion,
                }
            )

            if asignatura == REVISION or tema == REVISION:
                revision.append(archivo.name)
            else:
                organizados.append((archivo.name, asignatura, tema))
        except OSError as error:
            # Un archivo problematico no debe detener el resto: el error se
            # acumula en el resumen y la pasada continua.
            errores.append({"nombre": archivo.name, "error": str(error)})

    afirmar(
        len(organizados) + len(revision) + filtrados + len(errores) <= total_vistos,
        "el resumen no cuadra con los archivos vistos",
    )

    return {
        "organizados": organizados,
        "revision": revision,
        "movimientos": movimientos,
        "errores": errores,
        "avisos": avisos,
        "filtrados": filtrados,
    }


def deshacer(registro, simular=False):
    """Devuelve al origen los archivos indicados en el ultimo log.

    Con `simular=True` calcula los destinos pero no mueve nada ni limpia
    carpetas vacias. Devuelve
    {"deshechos": [{nombre, destino}], "errores": [{nombre, error}]}.
    """
    deshechos: list = []
    errores = []

    origen_dato = registro.get("origen") if isinstance(registro, dict) else None
    salida_dato = registro.get("salida") if isinstance(registro, dict) else None
    if not origen_dato:
        errores.append({"nombre": "", "error": "El log no tiene 'origen'"})
        return {"deshechos": deshechos, "errores": errores}

    origen = Path(origen_dato).resolve()
    if not origen.is_dir():
        errores.append(
            {
                "nombre": "",
                "error": "No existe la carpeta de origen: {}".format(origen),
            }
        )
        return {"deshechos": deshechos, "errores": errores}

    for movimiento in registro.get("movimientos", []):
        nombre = movimiento.get("nombre", "")
        actual = Path(movimiento.get("destino", ""))
        try:
            if not actual.is_file():
                raise FileNotFoundError("No existe el archivo: {}".format(actual))
            destino = _destino_disponible(origen / nombre)
            if not simular:
                move(str(actual), str(destino))
            deshechos.append({"nombre": nombre, "destino": str(destino)})
        except OSError as error:
            errores.append({"nombre": nombre, "error": str(error)})

    if salida_dato and not simular:
        limpiar_vacias(Path(salida_dato))

    return {"deshechos": deshechos, "errores": errores}
