"""Motor de organizacion: lee una carpeta y mueve los archivos clasificados."""

from pathlib import Path
from shutil import move

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


def _destino_disponible(destino):
    """Evita sobreescribir: añade -1, -2, ... si el nombre ya existe."""
    if not destino.exists():
        return destino
    n = 1
    while True:
        candidato = destino.with_name(
            "{}-{}{}".format(destino.stem, n, destino.suffix)
        )
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


def organizar(origen, salida, simular=False, reglas=None):
    """Mueve cada archivo de `origen` a su carpeta clasificada.

    Si `simular` es True no se mueve nada: solo se calcula el destino.
    `reglas` permite usar una tupla de Regla personalizada; si es None se
    usan las del paquete.

    Devuelve un dict con el resumen:
      {"organizados": [(archivo, asignatura, tema)],
       "revision": [archivo],
       "movimientos": [{nombre, asignatura, tema, destino}],
       "errores": [{nombre, error}]}
    """
    origen = Path(origen).resolve()
    salida = Path(salida).resolve()

    if not origen.is_dir():
        raise NotADirectoryError("No existe la carpeta de origen: {}".format(origen))

    if salida == origen or origen in salida.parents:
        raise ValueError(
            "La carpeta de salida no puede estar dentro del origen: {}".format(salida)
        )

    organizados = []
    revision = []
    movimientos = []
    errores = []

    for archivo in sorted(origen.iterdir()):
        # Solo archivos del primer nivel; se ignoran subcarpetas y temporales.
        if not archivo.is_file() or _debe_ignorar(archivo):
            continue

        try:
            resultado = clasificar(archivo.name, reglas)
            if resultado is None:
                asignatura, tema = REVISION, ""
            else:
                asignatura, tema = resultado

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
                }
            )

            if asignatura == REVISION or tema == REVISION:
                revision.append(archivo.name)
            else:
                organizados.append((archivo.name, asignatura, tema))
        except OSError as error:
            # Un archivo problematico no debe detener el resto.
            errores.append({"nombre": archivo.name, "error": str(error)})

    return {
        "organizados": organizados,
        "revision": revision,
        "movimientos": movimientos,
        "errores": errores,
    }


def deshacer(registro):
    """Devuelve al origen los archivos indicados en el ultimo log.

    Devuelve {"deshechos": [{nombre, destino}], "errores": [{nombre, error}]}.
    """
    deshechos = []
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
            move(str(actual), str(destino))
            deshechos.append({"nombre": nombre, "destino": str(destino)})
        except OSError as error:
            errores.append({"nombre": nombre, "error": str(error)})

    if salida_dato:
        limpiar_vacias(Path(salida_dato))

    return {"deshechos": deshechos, "errores": errores}
