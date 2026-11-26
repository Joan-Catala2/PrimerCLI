"""Escaneo de carpetas con errores humanos.

`Path.iterdir`/`rglob` lanzan `PermissionError` (un traceback en pantalla)
cuando una carpeta no se puede leer. Este modulo convierte ese fallo en
`ErrorDeSistema` — mensaje humano, codigo 1, sin traceback — y ofrece el
reemplazo no recursivo de `rglob("*")`: recorre con `os.scandir`, no sigue
symlinks a carpetas (igual que `pathlib`) y permite decidir que hacer con
las subcarpetas ilegibles.
"""

import os
from pathlib import Path
from typing import List, Tuple

from .excepciones import ErrorDeSistema


def hijos(carpeta) -> List[Path]:
    """Hijos directos de `carpeta`, ordenados, como `sorted(iterdir())`.

    Un fallo del SO al leer la carpeta (permisos, ELOOP, etc.) es previsible
    y sale como `ErrorDeSistema`; no como traceback.
    """
    try:
        return sorted(Path(entrada.path) for entrada in os.scandir(carpeta))
    except OSError as error:
        raise ErrorDeSistema(
            "No se puede leer {} (permisos): {}".format(carpeta, error)
        ) from error


def arbol(carpeta) -> List[Path]:
    """Todos los descendientes de `carpeta` (el reemplazo humano de rglob).

    Lista symlinks (a archivo o a carpeta) como entradas sueltas — igual que
    `rglob` — pero nunca desciende por ellos: el control de `realpath`
    visitados corta los bucles (`r/espejo -> r` no es infinita).
    """
    rutas: List[Path] = []
    vistos = {os.path.realpath(carpeta)}
    pendientes = [Path(carpeta)]
    while pendientes:
        actual = pendientes.pop()
        for entrada in hijos(actual):
            rutas.append(entrada)
            if _es_carpeta(entrada):
                real = os.path.realpath(entrada)
                if real not in vistos:
                    vistos.add(real)
                    pendientes.append(entrada)
    return sorted(rutas)


def archivos_y_ilegibles(carpeta, recursivo) -> Tuple[List[Path], List[Path]]:
    """Archivos del primer nivel (o del arbol) + subcarpetas ilegibles.

    Ilegible la raiz es `ErrorDeUso`-humano via `ErrorDeSistema` (hijos).
    Con `recursivo`, una subcarpeta ilegible no aborta la pasada: se
    devuelve en el segundo elemento para que el motor la muestre como
    aviso honesto. Los symlinks a archivos cuentan como archivos (igual
    que `Path.is_file`); los symlinks a carpetas no se recorren (igual
    que `rglob`).
    """
    archivos: List[Path] = []
    ilegibles: List[Path] = []
    pendientes = [Path(carpeta)]
    es_raiz = True
    while pendientes:
        actual = pendientes.pop()
        try:
            entradas = os.scandir(actual)
        except OSError as error:
            if es_raiz:
                raise ErrorDeSistema(
                    "No se puede leer {} (permisos): {}".format(actual, error)
                ) from error
            ilegibles.append(actual)
            continue
        for entrada in entradas:
            ruta = Path(entrada.path)
            if entrada.is_dir(follow_symlinks=False):
                if recursivo:
                    pendientes.append(ruta)
            elif entrada.is_file(follow_symlinks=True):
                archivos.append(ruta)
        es_raiz = False
    ilegibles.sort()
    return sorted(archivos), ilegibles


def _es_carpeta(ruta: Path) -> bool:
    # `Path.is_dir` ya traga los OSError (enlaces rotos, ELOOP...): nunca
    # hay que protegerla otra vez.
    return ruta.is_dir()
