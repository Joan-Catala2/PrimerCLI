import pytest

from organizador.excepciones import CarpetaNoValidaError, OrganizadorError
from organizador.organizador import deshacer, organizar


def _crear_origen(tmp_path):
    origen = tmp_path / "descargas"
    origen.mkdir()
    return origen


def test_organiza_archivo_en_asignatura_y_tema(tmp_path):
    origen = _crear_origen(tmp_path)
    archivo = origen / "Programacion_java_tema1.pdf"
    archivo.write_text("x", encoding="utf-8")
    salida = tmp_path / "Organizado"

    resumen = organizar(origen, salida)

    destino = salida / "Programacion" / "Java" / archivo.name
    assert destino.exists()
    assert not archivo.exists()
    assert resumen["organizados"] == [(archivo.name, "Programacion", "Java")]
    assert resumen["revision"] == []
    assert resumen["errores"] == []
    assert resumen["movimientos"] == [
        {
            "nombre": archivo.name,
            "asignatura": "Programacion",
            "tema": "Java",
            "destino": str(destino),
        }
    ]


def test_no_sobrescribe_y_anade_sufijo(tmp_path):
    origen = _crear_origen(tmp_path)
    salida = tmp_path / "Organizado"
    nombre = "FOL_nomina.pdf"

    (origen / nombre).write_text("primero", encoding="utf-8")
    organizar(origen, salida)

    (origen / nombre).write_text("segundo", encoding="utf-8")
    organizar(origen, salida)

    carpeta = salida / "FOL" / "Nomina"
    assert (carpeta / nombre).exists()
    assert (carpeta / "FOL_nomina-1.pdf").exists()


def test_simular_no_mueve_ni_crea_carpetas(tmp_path):
    origen = _crear_origen(tmp_path)
    archivo = origen / "BaseDeDatos_sql.pdf"
    archivo.write_text("x", encoding="utf-8")
    salida = tmp_path / "Organizado"

    resumen = organizar(origen, salida, simular=True)

    assert archivo.exists()
    assert not salida.exists()
    assert resumen["movimientos"][0]["asignatura"] == "BaseDeDatos"
    assert resumen["movimientos"][0]["tema"] == "SQL"
    assert resumen["movimientos"][0]["destino"] == str(
        salida / "BaseDeDatos" / "SQL" / archivo.name
    )


def test_revision_mueve_a_revision(tmp_path):
    origen = _crear_origen(tmp_path)
    archivo = origen / "apuntes_scan_03.pdf"
    archivo.write_text("x", encoding="utf-8")
    salida = tmp_path / "Organizado"

    resumen = organizar(origen, salida)

    assert (salida / "_revision" / archivo.name).exists()
    assert resumen["organizados"] == []
    assert resumen["revision"] == [archivo.name]


def test_ignora_temporales_y_log(tmp_path):
    origen = _crear_origen(tmp_path)
    nombres = ["archivo.part", ".DS_Store", "~$temp.docx", "organizador.log.json"]
    for nombre in nombres:
        (origen / nombre).write_text("x", encoding="utf-8")
    salida = tmp_path / "Organizado"

    resumen = organizar(origen, salida)

    assert resumen["movimientos"] == []
    assert not salida.exists()
    for nombre in nombres:
        assert (origen / nombre).exists()


def test_salida_dentro_del_origen_falla(tmp_path):
    origen = _crear_origen(tmp_path)

    with pytest.raises(CarpetaNoValidaError, match="dentro del origen"):
        organizar(origen, origen / "Organizado")


def test_origen_inexistente_es_error_previsible(tmp_path):
    """Caso feo: el origen no existe; debe ser mensaje humano, no OSError."""
    with pytest.raises(CarpetaNoValidaError, match="No existe la carpeta"):
        organizar(tmp_path / "no_existe", tmp_path / "Organizado")


def test_origen_es_un_archivo_no_una_carpeta(tmp_path):
    """Caso feo: pasar un fichero como origen da un mensaje especifico."""
    archivo = tmp_path / "soy_un_archivo.txt"
    archivo.write_text("x", encoding="utf-8")

    with pytest.raises(CarpetaNoValidaError, match="no es una carpeta"):
        organizar(archivo, tmp_path / "Organizado")


def test_afirmar_falla_como_error_previsible():
    """`afirmar` es una asercion de desarrollo que sobrevive a python -O."""
    from organizador.excepciones import afirmar

    afirmar(True, "esto no debe lanzar")

    with pytest.raises(OrganizadorError, match="Error interno"):
        afirmar(False, "invariante rota")


def test_deshacer_devuelve_archivos_al_origen(tmp_path):
    origen = _crear_origen(tmp_path)
    archivo = origen / "FOL_nomina.pdf"
    archivo.write_text("x", encoding="utf-8")
    salida = tmp_path / "Organizado"
    resumen = organizar(origen, salida)
    registro = {
        "origen": str(origen.resolve()),
        "salida": str(salida.resolve()),
        "movimientos": resumen["movimientos"],
    }

    resultado = deshacer(registro)

    assert (origen / "FOL_nomina.pdf").exists()
    assert resultado["deshechos"] == [
        {"nombre": "FOL_nomina.pdf", "destino": str(origen / "FOL_nomina.pdf")}
    ]
    assert resultado["errores"] == []
    assert salida.exists()
    assert list(salida.iterdir()) == []


def test_deshacer_no_sobrescribe(tmp_path):
    origen = _crear_origen(tmp_path)
    archivo = origen / "FOL_nomina.pdf"
    archivo.write_text("original", encoding="utf-8")
    salida = tmp_path / "Organizado"
    resumen = organizar(origen, salida)

    (origen / "FOL_nomina.pdf").write_text("nuevo", encoding="utf-8")
    registro = {
        "origen": str(origen.resolve()),
        "salida": str(salida.resolve()),
        "movimientos": resumen["movimientos"],
    }

    resultado = deshacer(registro)

    assert (origen / "FOL_nomina.pdf").read_text(encoding="utf-8") == "nuevo"
    assert (origen / "FOL_nomina-1.pdf").exists()
    assert resultado["errores"] == []
