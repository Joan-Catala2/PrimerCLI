"""Pruebas de `aplicar`: propuesta determinista, confirmacion y reorganizacion.

Dos niveles: `sugerir_alias` (funcion pura de inferencia) y la accion con
`cli.main`, que es el camino real. Los casos feos: empate entre asignaturas,
token corto unico, EOF a mitad, alias ya catalogado, colision de nombres y
deshacer despues de reorganizar.
"""

import json

import pytest

from organizador import cli
from organizador.acciones.aplicar import AccionAplicar, sugerir_alias
from organizador.excepciones import ErrorDeUso
from organizador.presentacion.consola import Consola
from organizador.reglas import REGLAS_DEL_PAQUETE, Regla

# Un catalogo pequeno y determinista para las pruebas de inferencia.
CATALOGO = (
    Regla(
        "BaseDeDatos",
        ("basedatos", "basededatos", "base de datos", "bbdd", "sql"),
        (("Normalizacion", ("normalizacion",)),),
    ),
    Regla(
        "Programacion",
        ("programacion", "java", "python"),
        (("Algoritmos", ("algoritmo",)),),
    ),
    Regla(
        "EntornosDeDesarrollo",
        ("entornos", "git"),
        (("Git", ("github",)),),
    ),
)


def _revision(tmp_path, *nombres):
    revision = tmp_path / "Organizado" / "_revision"
    revision.mkdir(parents=True, exist_ok=True)
    for nombre in nombres:
        (revision / nombre).write_text("x", encoding="utf-8")
    return revision


# --- sugerir_alias (inferencia pura) ---------------------------------------


def test_propone_alias_largo_tras_asignatura():
    s = sugerir_alias("basededatos_transaccions.pdf", CATALOGO)
    assert s is not None and s.asignatura == "BaseDeDatos"
    assert s.alias == ("transaccions",)


def test_token_generico_no_propone_nada():
    # 'tema' y 'examen' refuerzan pero no son alias; 'apunts' tampoco.
    assert sugerir_alias("java_tema3_examen.pdf", CATALOGO) is None


def test_unico_token_corto_no_propone():
    # 'cv' (2 letras) no puede acabar en alias: terreno de falsos positivos.
    assert sugerir_alias("java_cv.pdf", CATALOGO) is None


def test_empate_entre_asignaturas_no_propone():
    # 'sql' es BaseDeDatos y 'algoritmos' Programacion: sin mayoria clara.
    assert sugerir_alias("sql_algoritmos_x9.pdf", CATALOGO) is None


def test_alias_ya_catalogado_no_propone():
    assert sugerir_alias("java_java.pdf", CATALOGO) is None


def test_propone_con_dos_tokens_cortos_desconocidos():
    s = sugerir_alias("java_ux_ui_rx.pdf", CATALOGO)
    assert s is not None and s.asignatura == "Programacion"
    assert s.alias == ("ux", "ui", "rx")  # dos cortos = propuesta conjunta


def test_compacto_multiword_cubre_sus_tokens():
    # 'base de datos' es un alias de varias palabras: no se propone 'datos'.
    assert sugerir_alias("base_de_datos_normalizacion.pdf", CATALOGO) is None


def test_sufijo_x_no_propone_alias():
    # 'x2' (2 letras, marcador de copia) no puede volverse alias jamas
    assert sugerir_alias("java_hilos_x2.pdf", CATALOGO).alias == ("hilos",)


def test_alias_de_tema_cuenta_como_evidencia():
    s = sugerir_alias("normalizacion_transaccions.sql", CATALOGO)
    assert s is not None and s.asignatura == "BaseDeDatos"


# --- fabrica y opciones imposibles ------------------------------------------


def test_reorganizar_sin_confirmar_es_error_de_uso(tmp_path):
    with pytest.raises(ErrorDeUso, match="--reorganizar requiere --confirmar"):
        AccionAplicar.desde_config(_args(tmp_path, reorganizar=True), Consola())


def _args(tmp_path, **datos):
    import argparse

    base = dict(
        accion="aplicar",
        salida=str(tmp_path / "Organizado"),
        reglas=None,
        logs_dir="organizador-logs",
        confirmar=False,
        reorganizar=False,
        seco=False,
        json=False,
    )
    base.update(datos)
    return argparse.Namespace(**base)


# --- accion por CLI (camino real) --------------------------------------------


def test_propuesta_sin_confirmar_no_toca_reglas_ni_mueve(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    _revision(tmp_path, "basededatos_transaccions.pdf")

    codigo = cli.main(["aplicar", "--salida", str(tmp_path / "Organizado")])

    assert codigo == 0
    salida = capsys.readouterr().out
    assert "BaseDeDatos" in salida and "transaccions" in salida
    assert not (tmp_path / "config" / "organizador" / "reglas.json").exists()
    assert (
        tmp_path / "Organizado" / "_revision" / "basededatos_transaccions.pdf"
    ).exists()


def _con_reglas_json(nombre):
    return json.dumps(
        [{"asignatura": nombre, "aliases": [nombre.lower()], "temas": []}]
    )


def test_confirmar_guarda_alias_fusionando_con_previas(tmp_path, monkeypatch):
    config = tmp_path / "config"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config))
    reglas_previas = config / "organizador"
    reglas_previas.mkdir(parents=True)
    (reglas_previas / "reglas.json").write_text(
        _con_reglas_json("FOL"), encoding="utf-8"
    )
    _revision(tmp_path, "basededatos_transaccions.pdf", "java_hilos_tema1.pdf")
    monkeypatch.setattr("builtins.input", lambda _: "s")

    codigo = cli.main(
        ["aplicar", "--salida", str(tmp_path / "Organizado"), "--confirmar"]
    )

    assert codigo == 0
    guardadas = json.loads((reglas_previas / "reglas.json").read_text(encoding="utf-8"))
    fol = [r for r in guardadas if r["asignatura"] == "FOL"]
    assert fol == [{"asignatura": "FOL", "aliases": ["fol"], "temas": []}]
    bd = [r for r in guardadas if r["asignatura"] == "BaseDeDatos"]
    assert "transaccions" in bd[0]["aliases"]
    assert "sql" in bd[0]["aliases"]  # hereda los aliases del paquete al nacer
    prog = [r for r in guardadas if r["asignatura"] == "Programacion"]
    assert "hilos" in prog[0]["aliases"]
    # nada movido: las propuestas siguen en _revision
    assert (
        tmp_path / "Organizado" / "_revision" / "basededatos_transaccions.pdf"
    ).exists()


def test_rechazar_no_escribe_nada(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    _revision(tmp_path, "basededatos_transaccions.pdf")
    monkeypatch.setattr("builtins.input", lambda _: "n")

    codigo = cli.main(
        ["aplicar", "--salida", str(tmp_path / "Organizado"), "--confirmar"]
    )

    assert codigo == 0
    assert not (tmp_path / "config" / "organizador" / "reglas.json").exists()


def test_eof_a_mitad_no_escribe_nada(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    _revision(tmp_path, "basededatos_transaccions.pdf", "java_hilos.pdf")

    respuestas = iter(["s", EOFError])

    def _input(_):
        valor = next(respuestas)
        if valor is EOFError:
            raise EOFError
        return valor

    monkeypatch.setattr("builtins.input", _input)

    codigo = cli.main(
        ["aplicar", "--salida", str(tmp_path / "Organizado"), "--confirmar"]
    )

    assert codigo == 0
    assert not (tmp_path / "config" / "organizador" / "reglas.json").exists()


def test_reorganizar_mueve_con_alias_nuevos_y_deja_log_deshacible(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    _revision(tmp_path, "entorns_ignorats.pdf", "programacio_poo.pdf")
    monkeypatch.setattr("builtins.input", lambda _: "s")

    codigo = cli.main(
        [
            "aplicar",
            "--salida",
            str(tmp_path / "Organizado"),
            "--logs-dir",
            str(tmp_path / "logs"),
            "--confirmar",
            "--reorganizar",
        ]
    )

    assert codigo == 0
    revision = tmp_path / "Organizado" / "_revision"
    assert (
        tmp_path / "Organizado" / "EntornosDeDesarrollo" / "entorns_ignorats.pdf"
    ).exists()
    # 'programacio' no es alias de nada: su archivo sigue en _revision
    assert (revision / "programacio_poo.pdf").exists()
    logs = sorted((tmp_path / "logs").glob("*.json"))
    assert len(logs) == 1

    # `deshacer` revierte: el archivo vuelve a _revision
    codigo = cli.main(["deshacer", "--logs-dir", str(tmp_path / "logs")])
    assert codigo == 0
    assert (revision / "entorns_ignorats.pdf").exists()


def test_reorganizar_respeta_el_sufijo_anti_colision(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    destino = tmp_path / "Organizado" / "EntornosDeDesarrollo"
    destino.mkdir(parents=True)
    (destino / "entorns_ignorats.pdf").write_text("previo", encoding="utf-8")
    _revision(tmp_path, "entorns_ignorats.pdf")
    monkeypatch.setattr("builtins.input", lambda _: "s")

    codigo = cli.main(
        [
            "aplicar",
            "--salida",
            str(tmp_path / "Organizado"),
            "--logs-dir",
            str(tmp_path / "logs"),
            "--confirmar",
            "--reorganizar",
        ]
    )

    assert codigo == 0
    assert (destino / "entorns_ignorats.pdf").read_text(encoding="utf-8") == "previo"
    assert (destino / "entorns_ignorats-1.pdf").exists()


def test_json_de_aplicar_es_valido(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    _revision(tmp_path, "basededatos_transaccions.pdf")

    codigo = cli.main(["aplicar", "--salida", str(tmp_path / "Organizado"), "--json"])

    assert codigo == 0
    datos = json.loads(capsys.readouterr().out)
    assert datos["ok"] is True and datos["accion"] == "aplicar"
    assert datos["propuestas"][0]["asignatura"] == "BaseDeDatos"
    assert datos["total"] == 1


def test_sin_carpeta_revision_json_valido_y_codigo_cero(tmp_path, capsys):
    codigo = cli.main(["aplicar", "--salida", str(tmp_path / "Organizado"), "--json"])

    assert codigo == 0
    datos = json.loads(capsys.readouterr().out)
    assert datos["propuestas"] == [] and datos["total"] == 0


def test_seco_solo_imprime_resumen(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    _revision(tmp_path, "basededatos_transaccions.pdf")

    codigo = cli.main(["aplicar", "--salida", str(tmp_path / "Organizado"), "--seco"])

    assert codigo == 0
    salida = capsys.readouterr().out
    assert "Resumen" in salida
    assert "transaccions.pdf" not in salida


def test_aplicar_con_reglas_propias_guarda_en_el_mismo_fichero(tmp_path, monkeypatch):
    reglas = tmp_path / "mis_reglas.json"
    reglas.write_text(
        json.dumps([{"asignatura": "Matemates", "aliases": ["mates"]}]),
        encoding="utf-8",
    )
    _revision(tmp_path, "mates_logica.pdf")
    monkeypatch.setattr("builtins.input", lambda _: "s")

    codigo = cli.main(
        [
            "aplicar",
            "--salida",
            str(tmp_path / "Organizado"),
            "--reglas",
            str(reglas),
            "--confirmar",
        ]
    )

    assert codigo == 0
    guardadas = json.loads(reglas.read_text(encoding="utf-8"))
    assert guardadas == [
        {"asignatura": "Matemates", "aliases": ["mates", "logica"], "temas": []}
    ]


# --- el catalogo empaquetado tambien es inferible ----------------------------


def test_sugerir_alias_funciona_con_el_catalogo_del_paque():
    # 'programacio' casa compacto con 'programacion' (candidata doble):
    # sin mayoria clara no se propone nada, que es el comportamiento seguro.
    assert sugerir_alias("programacio_poo.pdf", REGLAS_DEL_PAQUETE) is None
    # 'poo' esta contenido en 'pseudocodigo' (alias del paquete): se descarta
    # por variante. Un token realmente ajeno al catalogo si se propone.
    assert sugerir_alias("Programacion_poo.pdf", REGLAS_DEL_PAQUETE) is None
    s = sugerir_alias("Programacion_cohorts.pdf", REGLAS_DEL_PAQUETE)
    assert s is not None and s.asignatura == "Programacion"
    assert s.alias == ("cohorts",)
