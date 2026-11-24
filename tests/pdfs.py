"""Helpers compartidos: fabrica de PDFs reales para `--contenido`.

Los PDFs de prueba se generan con `pypdf` (el mismo lector que usa la
CLI): nada de binarios versionados. Sin el extra, `pytest.importorskip`
saltaria las pruebas que los necesitan; `.[dev]` lo incluye, asi que en
CI nunca se saltan.
"""

from pathlib import Path

from pypdf import PdfWriter
from pypdf.generic import (
    ArrayObject,
    DecodedStreamObject,
    DictionaryObject,
    FloatObject,
    NameObject,
)

_FONT = DictionaryObject(
    {
        NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
    }
)


def _escapar(texto):
    return texto.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def _pagina_con_texto(writer, lineas):
    """Una pagina con cada linea escrita en su propio Tj.

    `extract_text` de pypdf separa operaciones distintas con salto de
    linea: es la forma de simular paginas (lineas = paginas) sin OCR ni
    fuentes reales.
    """
    contenido = b"BT /F1 12 Tf 10 50 Td"
    for linea in lineas:
        contenido += b" (" + _escapar(linea).encode("latin-1", "replace") + b") Tj"
    contenido += b" ET"

    stream = DecodedStreamObject()
    stream.set_data(contenido)
    stream.update(
        {
            NameObject("/Type"): NameObject("/XObject"),
            NameObject("/Subtype"): NameObject("/Form"),
            NameObject("/BBox"): ArrayObject(
                [FloatObject(0), FloatObject(0), FloatObject(300), FloatObject(100)]
            ),
        }
    )
    page = writer.add_blank_page(width=300, height=100)
    fonts = DictionaryObject()
    fonts[NameObject("/F1")] = writer._add_object(_FONT)
    recursos = DictionaryObject()
    recursos[NameObject("/Font")] = writer._add_object(fonts)
    page[NameObject("/Resources")] = writer._add_object(recursos)
    page[NameObject("/Contents")] = writer._add_object(stream)


def escribir_pdf(ruta, lineas):
    """Escribe un PDF real con una pagina por linea de `lineas`."""
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    writer = PdfWriter()
    for linea in lineas:
        _pagina_con_texto(writer, [linea])
    with open(ruta, "wb") as archivo:
        writer.write(archivo)
    return ruta


def leer_pdf_texto(ruta):
    """Lee un PDF de prueba con el propio pypdf (para afirmaciones)."""
    from pypdf import PdfReader

    lector = PdfReader(str(ruta))
    return " ".join(pagina.extract_text() or "" for pagina in lector.pages)
