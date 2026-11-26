"""Fuzz de alias en `aplicar`: caracteres hostiles sobreviven el ida y vuelta.

El alias propuesto viene de tokens del nombre de archivo (`trocear` corta en
separadores, no en el resto), asi que puede llegar con comillas, emoji o 200
letras. El contrato que aqui se fija: el prompt se pinta, el JSON de reglas
del usuario sigue siendo parseable por `cargar_reglas`, y recargar las reglas
con el alias hostil sigue clasificando. Ningun token de control sobrevive al
troceado de nombre real de fichero, pero el test lo cubre por si acaso.
"""

import json

from organizador import cli
from organizador.reglas import cargar_reglas, clasificar

HOSTILES = (
    ('transaccions"', 'basededatos_transaccions".pdf'),
    ("tra'ns", "basededatos_tra'ns.pdf"),
    ("y" * 200, "basededatos_" + "y" * 200 + ".pdf"),
    ("\U0001f680sqlx", "basededatos_\U0001f680sqlx.pdf"),
    ("nandu", "basededatos_\u00f1andu.pdf"),
)


def _aplicar_todo(tmp_path, monkeypatch):
    revision = tmp_path / "Organizado" / "_revision"
    revision.mkdir(parents=True)
    for _, nombre in HOSTILES:
        (revision / nombre).write_text("x", encoding="utf-8")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setattr("builtins.input", lambda *_: "s")

    codigo = cli.main(
        ["aplicar", "--salida", str(tmp_path / "Organizado"), "--confirmar"]
    )

    assert codigo == 0
    return tmp_path / "config" / "organizador" / "reglas.json"


def test_alias_hostiles_sobreviven_el_round_trip(tmp_path, monkeypatch):
    ruta = _aplicar_todo(tmp_path, monkeypatch)
    datos = json.loads(ruta.read_text(encoding="utf-8"))  # JSON valido, no basura
    base = next(r for r in datos if r["asignatura"] == "BaseDeDatos")
    for alias, _ in HOSTILES:
        assert alias in base["aliases"], alias


def test_recargar_con_alias_hostiles_sigue_clasificando(tmp_path, monkeypatch):
    ruta = _aplicar_todo(tmp_path, monkeypatch)
    reglas = cargar_reglas(ruta)
    assert clasificar('basededatos_tra"ns_2.pdf', reglas) is not None
    assert clasificar("nandu.sql", reglas) == ("BaseDeDatos", "")


def test_el_prompt_no_revienta_con_alias_de_200_letras(tmp_path, monkeypatch, capsys):
    _aplicar_todo(tmp_path, monkeypatch)
    salida = capsys.readouterr().out
    assert "Propuestas:           5" in salida
    assert "Alias guardados:      5" in salida
