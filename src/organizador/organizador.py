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


def organizar(origen, salida, simular=False):
    """Mueve cada archivo de `origen` a su carpeta clasificada.

    Si `simular` es True no se mueve nada: solo se calcula el destino.

    Devuelve un dict con el resumen:
      {"organizados": [(archivo, asignatura, tema)], "revision": [archivo]}
    """
    origen = Path(origen)
    salida = Path(salida)

    if not origen.is_dir():
        raise NotADirectoryError("No existe la carpeta de origen: {}".format(origen))

    organizados = []
    revision = []
    movimientos = []

    for archivo in sorted(origen.iterdir()):
        # Solo archivos del primer nivel: las subcarpetas se ignoran.
        if not archivo.is_file():
            continue

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

    return {
        "organizados": organizados,
        "revision": revision,
        "movimientos": movimientos,
    }
