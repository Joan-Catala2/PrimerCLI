"""Pruebas de `--contenido` (ADR-006): clasificar por el texto de un PDF.

Cubren el contrato del lector (`texto_pdf`: paginas, limites, cifrado y
basura), el emparejamiento por fronteras de palabra, la inyeccion del
extractor en el motor (el nombre siempre manda) y los dos comandos que lo
exponen. Los PDFs son reales, generados con `pypdf` (`tests/pdfs.py`);
sin el extra `organizador[pdf]` todo el modulo se salta (el dev extra lo
incluye, asi que en CI nunca se salta).
"""

import json

import pytest
from pdfs import escribir_pdf

from organizador import cli
from organizador.contenido import (
    ExtraccionFallida,
    clasificar_por_contenido,
    texto_pdf,
)
from organizador.excepciones import ErrorDeUso
from organizador.organizador import organizar
from organizador.reglas import Regla

pytest.importorskip("pypdf", reason="extra organizador[pdf] no instalado")

REGLAS = (
    Regla(
        "BaseDeDatos",
        ("basedatos", "base de datos", "sql", "bds"),
        (("Normalizacion", ("normalizacion", "normalizar")), ("SQL", ("sql",))),
    ),
    Regla("FOL", ("fol", "formacion"), ()),
    # Las reglas del catalogo interno para las pruebas del motor: sin ella,
    # `clasificar(nombre)` en `test_el_nombre_manda...` no clasificaria por
    # nombre y no estaria probando lo que dice probar.
    Regla("Programacion", ("programacion", "java"), (("Java", ("java",)),)),
)


# --- lector ---------------------------------------------------------------


def test_texto_pdf_respeta_max_paginas(tmp_path):
    ruta = escribir_pdf(
        tmp_path / "varias.pdf", ["primera", "segunda", "tercera", "cuarta"]
    )
    assert texto_pdf(ruta, 2) == "primera segunda"


def test_texto_pdf_valida_max_paginas():
    ruta = escribir_pdf("/tmp/plistapdf.pdf", ["x"])
    with pytest.raises(ErrorDeUso):
        texto_pdf(ruta, 0)


def test_alias_inutil_no_participa():
    corta = (Regla("X", ("x", "ab"), (("tema1", ("T1",)),)),)
    assert clasificar_por_contenido("x y T1", corta) == (None, None)


def test_texto_pdf_trunca_sin_reventar(tmp_path):
    ruta = escribir_pdf(tmp_path / "largo.pdf", ["xy" * 4000])
    texto = texto_pdf(ruta, 1)
    assert len(texto) <= 4000


def test_clasifica_con_las_reglas_del_paquete_por_defecto():
    pareja, detalle = clasificar_por_contenido("apuntes de Programacion java")
    assert pareja == ("Programacion", "Java")
    assert detalle["origen"] == "contenido"


def test_texto_pdf_con_archivo_basura_es_fallo_previsto(tmp_path):
    ruta = tmp_path / "roto.pdf"
    ruta.write_bytes(b"esto no es un pdf")
    with pytest.raises(ExtraccionFallida):
        texto_pdf(ruta, 1)


def test_texto_pdf_sin_extra_es_error_humano(tmp_path, monkeypatch):
    import organizador.contenido as contenido

    ruta = escribir_pdf(tmp_path / "ok.pdf", ["apuntes"])
    original = contenido.importlib.import_module

    def sin_pypdf(nombre, *args, **kwargs):
        if nombre == "pypdf":
            raise ImportError("no module named pypdf")
        return original(nombre, *args, **kwargs)

    monkeypatch.setattr(contenido.importlib, "import_module", sin_pypdf)
    with pytest.raises(ErrorDeUso) as error:
        contenido.texto_pdf(ruta, 1)
    assert "organizador[pdf]" in str(error.value)


# --- emparejamiento -------------------------------------------------------


def test_alias_de_tres_letras_casa_por_frontera():
    pareja, detalle = clasificar_por_contenido("hoy toca fol y nada mas", REGLAS)
    assert pareja == ("FOL", "")
    assert detalle["alias_asignatura"] == "fol" and detalle["alias_tema"] == ""


def test_mysql_no_es_sql():
    pareja, _ = clasificar_por_contenido("instalando mysql en el servidor", REGLAS)
    assert pareja is None


def test_tema_detectado_con_frontera():
    pareja, detalle = clasificar_por_contenido(
        "Apuntes de Base de Datos, tema 4: normalizacion", REGLAS
    )
    assert pareja == ("BaseDeDatos", "Normalizacion")
    assert detalle["origen"] == "contenido" and detalle["tipo"] == "texto"
    assert detalle["alias_asignatura"] == "base de datos"
    assert detalle["alias_tema"] == "normalizacion"


def test_texto_vacio_no_da_nada():
    assert clasificar_por_contenido("", REGLAS) == (None, None)
    assert clasificar_por_contenido("   ", REGLAS) == (None, None)


def test_alias_usable_rechaza_cortos():
    corta = (Regla("X", ("x", "ab"), ()),)
    assert clasificar_por_contenido("x ab", corta) == (None, None)


# --- motor ---------------------------------------------------------------


def _origen_con(tmp_path, nombre):
    origen = tmp_path / "descargas"
    origen.mkdir(exist_ok=True)
    ruta = origen / nombre
    ruta.parent.mkdir(parents=True, exist_ok=True)
    return ruta


def _extraer_de_archivos(textos):
    """Extractor doble: keyed por nombre, devuelve el texto o lanza."""

    def extraer(ruta):
        texto = textos.get(str(ruta))
        if texto is None:
            raise ExtraccionFallida("el PDF no se pudo leer (prueba)")
        return texto

    return extraer


def test_sin_extractor_como_antes(tmp_path):
    ruta = _origen_con(tmp_path, "Tema4.pdf")
    ruta.write_bytes(b"x")
    resumen = organizar(tmp_path / "descargas", tmp_path / "Organizado", reglas=REGLAS)
    assert resumen["revision"] == ["Tema4.pdf"]
    assert resumen["avisos"] == []
    assert resumen["movimientos"][0]["origen"] == "nombre"


def test_extractor_clasifica_cuando_el_nombre_calla(tmp_path):
    ruta = _origen_con(tmp_path, "Tema4.pdf")
    ruta.write_bytes(b"x")
    extraer = _extraer_de_archivos(
        {str(ruta): "Apuntes de Base de Datos, normalizacion"}
    )

    resumen = organizar(
        tmp_path / "descargas",
        tmp_path / "Organizado",
        reglas=REGLAS,
        extractor=extraer,
    )
    movimiento = resumen["movimientos"][0]
    assert movimiento["asignatura"] == "BaseDeDatos"
    assert movimiento["tema"] == "Normalizacion"
    assert movimiento["origen"] == "contenido"
    assert (ruta.name, "BaseDeDatos", "Normalizacion") in resumen["organizados"]


def test_el_nombre_manda_aunque_el_contenido_diga_otra_cosa(tmp_path):
    ruta = _origen_con(tmp_path, "Programacion_java_tema1.pdf")
    ruta.write_bytes(b"x")

    def extraer(_):
        raise AssertionError("el extractor no debe leerse: el nombre ya clasifica")

    resumen = organizar(
        tmp_path / "descargas",
        tmp_path / "Organizado",
        reglas=REGLAS,
        extractor=extraer,
    )
    assert resumen["movimientos"][0]["asignatura"] == "Programacion"
    assert resumen["movimientos"][0]["origen"] == "nombre"


def test_extractor_ilegible_avisa_y_sigue_a_revision(tmp_path):
    ruta = _origen_con(tmp_path, "misterio.pdf")
    ruta.write_bytes(b"x")
    extraer = _extraer_de_archivos({})  # siempre lanza

    resumen = organizar(
        tmp_path / "descargas",
        tmp_path / "Organizado",
        reglas=REGLAS,
        extractor=extraer,
    )
    assert resumen["revision"] == ["misterio.pdf"]
    assert len(resumen["avisos"]) == 1
    assert "misterio.pdf" in resumen["avisos"][0]


def test_extractor_no_toca_los_no_pdf(tmp_path):
    ruta = _origen_con(tmp_path, "apuntes.txt")
    ruta.write_bytes(b"x")
    called = []

    def extraer(r):
        called.append(r)
        return ""

    organizar(
        tmp_path / "descargas",
        tmp_path / "Organizado",
        reglas=REGLAS,
        extractor=extraer,
    )
    assert called == []  # el motor pregunta por contenido solo a los .pdf


# --- CLI ejecutar ---------------------------------------------------------


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


def test_ejecutar_contenido_con_pdf_real(tmp_path, capsys):
    escribir_pdf(
        tmp_path / "descargas" / "examen_1.pdf",
        ["Examen final de Base de Datos", "Tema 4: Normalizacion"],
    )
    assert _ejecutar_contenido(tmp_path, "--contenido", "--seco") == 0
    assert (tmp_path / "Organizado" / "BaseDeDatos" / "Normalizacion").is_dir()


def test_ejecutar_contenido_json_muestra_origen(tmp_path, capsys):
    escribir_pdf(
        tmp_path / "descargas" / "sin_nombre.pdf", ["apuntes de Programacion java"]
    )
    assert _ejecutar_contenido(tmp_path, "--contenido", "--json") == 0
    datos = json.loads(capsys.readouterr().out)
    movimiento = next(
        m for m in datos["movimientos"] if m["nombre"] == "sin_nombre.pdf"
    )
    assert movimiento["origen"] == "contenido"


def test_ejecutar_sin_contenido_ignora_el_pdf(tmp_path, capsys):
    escribir_pdf(tmp_path / "descargas" / "sin_nombre.pdf", ["Programacion java"])
    assert _ejecutar_contenido(tmp_path, "--json") == 0
    datos = json.loads(capsys.readouterr().out)
    assert datos["revision"] == ["sin_nombre.pdf"]


def test_contenido_max_paginas_invalido_es_error_de_uso(tmp_path, capsys):
    assert (
        _ejecutar_contenido(tmp_path, "--contenido", "--contenido-max-paginas", "0")
        == 2
    )
    assert "1 o mas" in capsys.readouterr().err


def test_pdf_ilegible_en_ejecutar_avisa_y_no_rompe(tmp_path, capsys):
    ruta = _origen_con(tmp_path, "roto.pdf")
    ruta.write_bytes(b"ni pdf es")
    assert _ejecutar_contenido(tmp_path, "--contenido", "--json") == 0
    datos = json.loads(capsys.readouterr().out)
    assert datos["revision"] == ["roto.pdf"]
    assert any("roto.pdf" in aviso for aviso in datos["avisos"])
    # la CLI sigue siendo sincera: el JSON lleva el aviso, y en modo humano
    # sale por stderr (lo comprueba el mismo caso sin --json abajo)


def test_deshacer_devuelve_lo_clasificado_por_contenido(tmp_path):
    ruta = escribir_pdf(
        tmp_path / "descargas" / "apunte.pdf", ["Apuntes de Base de Datos"]
    )
    assert _ejecutar_contenido(tmp_path, "--contenido", "--seco") == 0
    assert not ruta.exists()
    assert (tmp_path / "Organizado" / "BaseDeDatos" / "apunte.pdf").exists()

    assert cli.main(["deshacer", "--logs-dir", str(tmp_path / "logs")]) == 0
    assert ruta.exists()


# --- CLI explicar ---------------------------------------------------------


def test_explicar_contenido_fuente_contenido(tmp_path, capsys):
    ruta = tmp_path / "examen_resuelto.pdf"
    escribir_pdf(ruta, ["Apuntes de Base de Datos", "Tema 4: Normalizacion"])
    assert (
        cli.main(["explicar", str(ruta), "--contenido", "--salida", str(tmp_path)]) == 0
    )
    salida = capsys.readouterr().out
    assert "Fuente: contenido" in salida
    assert "BaseDeDatos/Normalizacion" in salida


def test_explicar_contenido_json_muestra_origen(tmp_path, capsys):
    ruta = tmp_path / "sin_nombre.pdf"
    escribir_pdf(ruta, ["apuntes de Programacion"])
    assert (
        cli.main(
            ["explicar", str(ruta), "--contenido", "--json", "--salida", str(tmp_path)]
        )
        == 0
    )
    datos = json.loads(capsys.readouterr().out)
    assert datos["fuente"] == "contenido"


def test_explicar_ilegible_con_contenido_no_revienta(tmp_path, capsys):
    ruta = tmp_path / "roto.pdf"
    ruta.write_bytes(b"para nada un pdf")
    assert cli.main(["explicar", str(ruta), "--contenido"]) == 0
    assert "_revision" in capsys.readouterr().out


# --- CLI revisar -----------------------------------------------------------


def test_revisar_interactivo_sugiere_contenido(tmp_path, monkeypatch, capsys):
    """`examen_resuelto.pdf` no clasifica por nombre (por eso cae en
    _revision); con --contenido la sugerencia sale marcada y Enter acepta.
    La marca va al prompt, y el prompt no se imprime: se demuestra que la
    sugerencia por contenido funciona con dos Enter (aceptar asignatura y
    tema) y el archivo acaba en BaseDeDatos/Normalizacion."""
    salida = tmp_path / "Organizado"
    carpeta = salida / "_revision"
    carpeta.mkdir(parents=True)
    escribir_pdf(
        carpeta / "examen_resuelto.pdf",
        ["Apuntes de Base de Datos", "Tema 4: Normalizacion"],
    )

    respuestas = iter(["", ""])
    monkeypatch.setattr("builtins.input", lambda *_: next(respuestas))
    codigo = cli.main(
        [
            "revisar",
            "--salida",
            str(salida),
            "--interactivo",
            "--contenido",
        ]
    )
    assert codigo == 0
    assert (salida / "BaseDeDatos" / "Normalizacion" / "examen_resuelto.pdf").exists()
    assert "Movido a" in capsys.readouterr().out


def test_revisar_interactivo_marca_contenido_en_el_prompt(
    tmp_path, monkeypatch, capsys
):
    """La marca `(contenido)` va al prompt, que en humano no se imprime:
    se verifica con un doble de `Consola.preguntar` (el prompt real que
    recibira el usuario)."""
    monkeypatch.chdir(tmp_path)
    salida = tmp_path / "Organizado"
    (salida / "_revision").mkdir(parents=True)
    escribir_pdf(salida / "_revision" / "examen_resuelto.pdf", ["Base de Datos"])

    from organizador.presentacion.consola import Consola

    prompts = []
    respuestas = iter(["BaseDeDatos", "-"])

    def preguntar(self, texto):
        prompts.append(texto)
        return next(respuestas)

    monkeypatch.setattr(Consola, "preguntar", preguntar)
    codigo = cli.main(
        ["revisar", "--salida", str(salida), "--interactivo", "--contenido"]
    )
    assert codigo == 0
    assert any("[BaseDeDatos] (contenido)" in p for p in prompts)
    assert (salida / "BaseDeDatos" / "examen_resuelto.pdf").exists()


def test_revisar_contenido_json_ignora_a_los_no_pdf(tmp_path, capsys):
    salida = tmp_path / "Organizado"
    (salida / "_revision").mkdir(parents=True)
    (salida / "_revision" / "nota.txt").write_text(
        "Programacion java", encoding="utf-8"
    )
    assert cli.main(["revisar", "--salida", str(salida), "--contenido", "--json"]) == 0
    datos = json.loads(capsys.readouterr().out)
    assert datos["archivos"] == ["nota.txt"]
