"""Fabrica de DOCX reales para `--contenido`.

El import de `python-docx` vive dentro de la funcion para que el modulo
pueda importarse incluso sin el extra: cada prueba decide con
`pytest.importorskip` si lo tiene disponible.
"""

from pathlib import Path


def escribir_docx(ruta, parrafos=(), titulo="", tablas=()):
    """Escribe un DOCX real con titulo, parrafos y tablas."""
    from docx import Document

    documento = Document()
    if titulo:
        documento.core_properties.title = titulo
    for parrafo in parrafos:
        documento.add_paragraph(parrafo)
    for filas in tablas:
        tabla = documento.add_table(rows=len(filas), cols=len(filas[0]))
        for numero_fila, fila in enumerate(filas):
            for numero_celda, valor in enumerate(fila):
                tabla.cell(numero_fila, numero_celda).text = valor

    destino = Path(ruta)
    destino.parent.mkdir(parents=True, exist_ok=True)
    documento.save(str(destino))
    return destino
