import json

import pytest

from organizador.excepciones import ConfigError, OrganizadorError
from organizador.reglas import (
    cargar_reglas,
    clasificar,
    reglas_efectivas,
    ruta_reglas_usuario,
)


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


@pytest.mark.parametrize(
    "nombre, esperado",
    [
        ("trabajosql.pdf", ("BaseDeDatos", "SQL")),
        ("contrasql.pdf", ("BaseDeDatos", "SQL")),
        ("trabajo_de_sql.pdf", ("BaseDeDatos", "SQL")),
        ("GithubApuntes.pdf", ("EntornosDeDesarrollo", "Git")),
        ("recipe.pdf", None),
        ("digit.pdf", None),
        ("tema4_ip.pdf", None),
        ("hipotesis_tema2.pdf", None),
    ],
)
def test_matching_compacto_sin_falsos_positivos(nombre, esperado):
    assert clasificar(nombre) == esperado


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

    with pytest.raises(ConfigError, match="JSON invalido"):
        cargar_reglas(ruta)


def test_cargar_reglas_valida_campos(tmp_path):
    ruta = tmp_path / "reglas.json"
    ruta.write_text(json.dumps([{"asignatura": "X", "aliases": []}]), encoding="utf-8")

    with pytest.raises(ConfigError, match="aliases"):
        cargar_reglas(ruta)


def test_cargar_reglas_fichero_inexistente_es_error_previsible(tmp_path):
    """Caso feo: `--reglas` apunta a una ruta que no existe."""
    with pytest.raises(ConfigError, match="No existe el fichero de reglas"):
        cargar_reglas(tmp_path / "no_existe.json")


def test_cargar_reglas_carpeta_es_error_previsible(tmp_path):
    """Caso feo: la ruta de `--reglas` es una carpeta, no un JSON."""
    carpeta = tmp_path / "una_carpeta"
    carpeta.mkdir()

    with pytest.raises(ConfigError, match="es una carpeta"):
        cargar_reglas(carpeta)


def test_todo_error_de_reglas_es_organizador_error(tmp_path):
    """Un error de config nunca debe escapar como excepción no prevista."""
    ruta = tmp_path / "reglas.json"
    ruta.write_text("{no es json", encoding="utf-8")

    with pytest.raises(OrganizadorError):
        cargar_reglas(ruta)


def _regla_digitalizacion(ruta):
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


def test_clasificar_con_reglas_personalizadas(tmp_path):
    ruta = tmp_path / "reglas.json"
    _regla_digitalizacion(ruta)
    reglas = cargar_reglas(ruta)

    assert clasificar("Digitalizacion_ofimatica.pdf", reglas) == (
        "Digitalizacion",
        "Ofimatica",
    )
    assert clasificar("FOL_nomina.pdf", reglas) is None


def test_reglas_efectivas_explicitas(tmp_path):
    ruta = tmp_path / "reglas.json"
    _regla_digitalizacion(ruta)

    reglas = reglas_efectivas(ruta)

    assert [r.asignatura for r in reglas] == ["Digitalizacion"]


def test_reglas_efectivas_fusiona_usuario(tmp_path, monkeypatch):
    usuario = ruta_reglas_usuario()
    usuario.parent.mkdir(parents=True, exist_ok=True)
    _regla_digitalizacion(usuario)

    reglas = reglas_efectivas()
    nombres = [r.asignatura for r in reglas]

    assert nombres[0] == "Digitalizacion"
    assert "Programacion" in nombres
    assert "FOL" in nombres


def test_reglas_efectivas_usuario_sobrescribe(tmp_path, monkeypatch):
    usuario = ruta_reglas_usuario()
    usuario.parent.mkdir(parents=True, exist_ok=True)
    usuario.write_text(
        json.dumps(
            [
                {
                    "asignatura": "FOL",
                    "aliases": ["fol"],
                    "temas": [{"tema": "Custom", "aliases": ["custom"]}],
                }
            ]
        ),
        encoding="utf-8",
    )

    reglas = reglas_efectivas()
    fol = [r for r in reglas if r.asignatura == "FOL"]

    assert len(fol) == 1
    assert fol[0].temas == (("Custom", ("custom",)),)
