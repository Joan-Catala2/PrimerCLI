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


def organizar(origen, salida, simular=False):
    """Mueve cada archivo de `origen` a su carpeta clasificada.

    Si `simular` es True no se mueve nada: solo se calcula el destino.

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
            resultado = clasificar(archivo.name)
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
