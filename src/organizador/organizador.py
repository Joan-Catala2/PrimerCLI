"""Motor de organizacion: lee una carpeta y mueve los archivos clasificados."""

from pathlib import Path
from shutil import move

from .reglas import REVISION, clasificar


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


def organizar(origen, destino_base):
    """Mueve cada archivo de `origen` a su carpeta clasificada.

    Devuelve un dict con el resumen:
      {"organizados": [(archivo, asignatura, tema)], "revision": [archivo]}
    """
    origen = Path(origen)
    destino_base = Path(destino_base)

    if not origen.is_dir():
        raise NotADirectoryError("No existe la carpeta de origen: {}".format(origen))

    organizados = []
    revision = []

    for archivo in sorted(origen.iterdir()):
        if not archivo.is_file():
            continue

        resultado = clasificar(archivo.name)
        if resultado is None:
            asignatura, tema = REVISION, ""
        else:
            asignatura, tema = resultado

        destino_dir = destino_base / asignatura
        if tema:
            destino_dir = destino_dir / tema
        destino_dir.mkdir(parents=True, exist_ok=True)

        destino = _destino_disponible(destino_dir / archivo.name)
        move(str(archivo), str(destino))

        if asignatura == REVISION or tema == REVISION:
            revision.append(archivo.name)
        else:
            organizados.append((archivo.name, asignatura, tema))

    return {"organizados": organizados, "revision": revision}
