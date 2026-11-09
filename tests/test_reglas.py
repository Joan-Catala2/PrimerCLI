import json

import pytest

from organizador.reglas import cargar_reglas, clasificar


@pytest.mark.parametrize(
    "nombre, esperado",
    [
        ("Programacion_java_tema1.pdf", ("Programacion", "Java")),
        ("BaseDeDatos_sql_apuntes.pdf", ("BaseDeDatos", "SQL")),
        ("SistemasInformaticos_redes.pdf", ("SistemasInformaticos", "Redes")),
        ("EntornosDeDesarrollo_git.pdf", ("EntornosDeDesarrollo", "Git")),
        ("LlenguatgeDeMarques_html.pdf", ("LlenguatgeDeMarques", "HTML")),
        ("Ingles_phrasal_verbs.pdf", ("Ingles", "PhrasalVerbs")),
        ("FOL_nomina.pdf", ("FOL", "Nomina")),
        ("IPE_curriculo.pdf", ("IPE", "Curriculo")),
    ],
)
def test_clasifica_asignaturas(nombre, esperado):
    assert clasificar(nombre) == esperado


def test_clasifica_asignatura_sin_tema():
    assert clasificar("programacion_apuntes.pdf") == ("Programacion", "")


def test_no_clasifica_desconocido():
    assert clasificar("apuntes_scan_03.pdf") is None


def test_no_confunde_fol_con_folder():
    assert clasificar("folder_apuntes.pdf") is None


def test_cargar_reglas_personalizadas(tmp_path):
    ruta = tmp_path / "reglas.json"
    ruta.write_text(
        json.dumps(
            [
                {
                    "asignatura": "Digitalizacion",
                    "aliases": ["digitalizacion"],
                    "temas": [{"tema": "Ofimatica", "aliases": ["ofimatica"]}],
                }
            ]
        ),
        encoding="utf-8",
    )

    reglas = cargar_reglas(ruta)

    assert reglas[0].asignatura == "Digitalizacion"
    assert reglas[0].temas == (("Ofimatica", ("ofimatica",)),)


def test_cargar_reglas_json_invalido(tmp_path):
    ruta = tmp_path / "reglas.json"
    ruta.write_text("{no es json", encoding="utf-8")

    with pytest.raises(ValueError, match="JSON invalido"):
        cargar_reglas(ruta)


def test_cargar_reglas_valida_campos(tmp_path):
    ruta = tmp_path / "reglas.json"
    ruta.write_text(
        json.dumps([{"asignatura": "X", "aliases": []}]), encoding="utf-8"
    )

    with pytest.raises(ValueError, match="aliases"):
        cargar_reglas(ruta)
