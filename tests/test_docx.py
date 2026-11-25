"""Pruebas de `--contenido` para DOCX (ADR-007).

Cubren el lector opcional, el despacho por extension, el motor y los tres
comandos que exponen la bandera. Los DOCX son reales, generados con
`python-docx` (`tests/documentos.py`); sin el extra `organizador[docx]` el
modulo se salta, y `.[dev]` lo incluye para que CI nunca lo salte.
"""

import json

import pytest
from documentos import escribir_docx

from organizador import cli, contenido
from organizador.contenido import (
    ExtraccionFallida,
    es_lexible,
    texto_documento,
    texto_docx,
)
from organizador.excepciones import ErrorDeUso
from organizador.organizador import organizar
from organizador.reglas import Regla

pytest.importorskip("docx", reason="extra organizador[docx] no instalado")

REGLAS = (
    Regla(
        "BaseDeDatos",
        ("basedatos", "base de datos", "sql", "bds"),
        (("Normalizacion", ("normalizacion", "normalizar")), ("SQL", ("sql",))),
    ),
    Regla("Programacion", ("programacion", "java"), (("Java", ("java",)),)),
)


# --- lector ---------------------------------------------------------------


def test_texto_docx_lee_titulo_parrafos_y_tablas(tmp_path):
    ruta = escribir_docx(
        tmp_path / "apunte.docx",
        titulo="Apuntes de Base de Datos",
        parrafos=["Tema 4: Normalizacion"],
        tablas=[("Base de Datos", "Normalizacion")],
    )
    texto = texto_docx(ruta)
    assert "Apuntes de Base de Datos" in texto
    assert "Tema 4: Normalizacion" in texto
    assert "Normalizacion" in texto


def test_texto_docx_trunca_sin_reventar(tmp_path):
    ruta = escribir_docx(tmp_path / "largo.docx", ["xy" * 4000])
    assert len(texto_docx(ruta)) <= contenido.LIMITE_CARACTERES


def test_texto_docx_con_archivo_basura_es_fallo_previsto(tmp_path):
    ruta = tmp_path / "roto.docx"
    ruta.write_bytes(b"esto no es un docx")
    with pytest.raises(ExtraccionFallida):
        texto_docx(ruta)


def test_texto_docx_sin_extra_es_error_humano(tmp_path, monkeypatch):
    ruta = escribir_docx(tmp_path / "ok.docx", ["apuntes"])
    original = contenido.importlib.import_module

    def sin_docx(nombre, *args, **kwargs):
        if nombre == "docx":
            raise ImportError("no module named docx")
        return original(nombre, *args, **kwargs)

    monkeypatch.setattr(contenido.importlib, "import_module", sin_docx)
    with pytest.raises(ErrorDeUso) as error:
        texto_docx(ruta)
    assert "organizador[docx]" in str(error.value)


# --- despacho por extension ------------------------------------------------


@pytest.mark.parametrize(
    "nombre, esperado",
    [
        ("a.pdf", True),
        ("A.DOCX", True),
        ("a.pdf.txt", False),
        ("a.txt", False),
    ],
)
def test_es_lexible_por_extension(nombre, esperado):
    assert es_lexible(nombre) is esperado


def test_texto_documento_elige_el_lector_por_extension(monkeypatch):
    vistos: list = []

    def falso_docx(ruta):
        vistos.append("docx")
        return "texto docx"

    def falso_pdf(ruta, paginas):
        vistos.append(("pdf", paginas))
        return "texto pdf"

    monkeypatch.setattr(contenido, "_leer_docx", falso_docx)
    monkeypatch.setattr(contenido, "_leer_pdf", falso_pdf)

    assert texto_documento("a.docx", 2) == "texto docx"
    assert texto_documento("a.PDF", 2) == "texto pdf"
    assert vistos == ["docx", ("pdf", 2)]


def test_texto_documento_valida_max_paginas():
    with pytest.raises(ErrorDeUso):
        texto_documento("a.docx", 0)


def test_texto_documento_rechaza_formatos_no_lexibles():
    with pytest.raises(ExtraccionFallida):
        texto_documento("apuntes.txt")


# --- motor ----------------------------------------------------------------


def test_motor_clasifica_docx_por_contenido(tmp_path):
    origen = tmp_path / "descargas"
    origen.mkdir()
    escribir_docx(
        origen / "sin_nombre.docx",
        ["Apuntes de Base de Datos", "Tema 4: Normalizacion"],
    )
    resumen = organizar(
        origen,
        tmp_path / "Organizado",
        reglas=REGLAS,
        extractor=texto_documento,
    )
    movimiento = resumen["movimientos"][0]
    assert movimiento["asignatura"] == "BaseDeDatos"
    assert movimiento["tema"] == "Normalizacion"
    assert movimiento["origen"] == "contenido"


def test_motor_no_lee_txt_con_contenido(tmp_path):
    origen = tmp_path / "descargas"
    origen.mkdir()
    (origen / "apuntes.txt").write_text("Apuntes de Base de Datos", encoding="utf-8")
    vistos = []

    def extraer(ruta):
        vistos.append(ruta)
        return "Apuntes de Base de Datos"

    organizar(origen, tmp_path / "Organizado", reglas=REGLAS, extractor=extraer)
    assert vistos == []


# --- CLI -------------------------------------------------------------------


def _ejecutar_contenido(tmp_path, *extra):
    return cli.main(
        [
            "ejecutar",
            str(tmp_path / "descargas"),
            "--salida",
            str(tmp_path / "Organizado"),
            "--logs-dir",
            str(tmp_path / "logs"),
        ]
        + list(extra)
    )


def test_ejecutar_con_docx_real(tmp_path):
    escribir_docx(
        tmp_path / "descargas" / "apunte.docx",
        ["Apuntes de Base de Datos", "Tema 4: Normalizacion"],
    )
    assert _ejecutar_contenido(tmp_path, "--contenido", "--seco") == 0
    assert (
        tmp_path / "Organizado" / "BaseDeDatos" / "Normalizacion" / "apunte.docx"
    ).is_file()


def test_ejecutar_docx_json_dice_origen_contenido(tmp_path, capsys):
    escribir_docx(
        tmp_path / "descargas" / "apunte.docx", ["Apuntes de Programacion java"]
    )
    assert _ejecutar_contenido(tmp_path, "--contenido", "--json") == 0
    datos = json.loads(capsys.readouterr().out)
    movimiento = next(m for m in datos["movimientos"] if m["nombre"] == "apunte.docx")
    assert movimiento["asignatura"] == "Programacion"
    assert movimiento["origen"] == "contenido"


def test_ejecutar_docx_sin_extra_es_error_humano_y_no_mueve(
    tmp_path, capsys, monkeypatch
):
    ruta = escribir_docx(
        tmp_path / "descargas" / "apunte.docx", ["Apuntes de Base de Datos"]
    )
    original = contenido.importlib.import_module

    def sin_docx(nombre, *args, **kwargs):
        if nombre == "docx":
            raise ImportError("no module named docx")
        return original(nombre, *args, **kwargs)

    monkeypatch.setattr(contenido.importlib, "import_module", sin_docx)
    assert _ejecutar_contenido(tmp_path, "--contenido", "--json") == 2
    assert "organizador[docx]" in capsys.readouterr().out
    assert ruta.exists()


def test_explicar_docx_fuente_contenido(tmp_path, capsys):
    ruta = escribir_docx(
        tmp_path / "apunte.docx", ["Apuntes de Base de Datos", "Normalizacion"]
    )
    assert (
        cli.main(["explicar", str(ruta), "--contenido", "--salida", str(tmp_path)]) == 0
    )
    salida = capsys.readouterr().out
    assert "Fuente: contenido" in salida
    assert "BaseDeDatos/Normalizacion" in salida


def test_revisar_docx_sugiere_contenido(tmp_path, monkeypatch, capsys):
    salida = tmp_path / "Organizado"
    revision = salida / "_revision"
    escribir_docx(
        revision / "apunte.docx",
        ["Apuntes de Base de Datos", "Tema 4: Normalizacion"],
    )
    respuestas = iter(["", ""])
    monkeypatch.setattr("builtins.input", lambda *_: next(respuestas))
    assert (
        cli.main(["revisar", "--salida", str(salida), "--interactivo", "--contenido"])
        == 0
    )
    assert (salida / "BaseDeDatos" / "Normalizacion" / "apunte.docx").is_file()
    assert "Movido a" in capsys.readouterr().out
