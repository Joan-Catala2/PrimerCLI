"""Rechaza claves reales en los archivos que van a entrar en git.

Lo usa pre-commit con los nombres de archivo y CI con `git ls-files`. Es
deliberadamente simple: busca patrones de tokens conocidos, no intenta ser
un escáner universal. La clave de la IA vive solo en variables de entorno.
"""

import re
import sys
from pathlib import Path

PATRONES = (
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"AIza[0-9A-Za-z_-]{20,}"),
)


def revisar(rutas):
    """Devuelve una lista de problemas (ruta, línea, texto)."""
    problemas = []
    for ruta in rutas:
        archivo = Path(ruta)
        if not archivo.is_file():
            continue
        try:
            contenido = archivo.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for numero, linea in enumerate(contenido.splitlines(), start=1):
            if any(patron.search(linea) for patron in PATRONES):
                problemas.append((str(archivo), numero, linea.strip()))
    return problemas


def main(argv=None):
    rutas = sys.argv[1:] if argv is None else argv
    problemas = revisar(rutas)
    if not problemas:
        return 0
    print("Se detectaron posibles claves; no se permite commitearlas:", file=sys.stderr)
    for ruta, numero, linea in problemas:
        print("  {}:{}: {}".format(ruta, numero, linea), file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
