"""Auditoria extremo a extremo de la CLI ejecutada como `python -m`.

Comprueba la capa que los tests unitarios no ven: el punto de entrada real,
los codigos de salida y que stdout sigue siendo JSON parseable. Todo se
ejecuta sin red y con variables de IA controladas.
"""

import json
import os
import runpy
import subprocess
import sys
from pathlib import Path

import pytest

from organizador import __version__

RAIZ = Path(__file__).resolve().parents[1]
CLAVE_FALSA = "CLAVE-FALSA-SIN-FORMATO"
VARIABLES_IA = (
    "ORGANIZADOR_API_KEY",
    "ORGANIZADOR_IA_URL",
    "ORGANIZADOR_IA_MODELO",
)


def _ejecutar(tmp_path, *args, clave=None):
    entorno = os.environ.copy()
    fuente = str(RAIZ / "src")
    entorno["PYTHONPATH"] = (
        fuente + os.pathsep + entorno["PYTHONPATH"]
        if entorno.get("PYTHONPATH")
        else fuente
    )
    for nombre in VARIABLES_IA:
        entorno.pop(nombre, None)
    if clave is not None:
        entorno["ORGANIZADOR_API_KEY"] = clave
    return subprocess.run(
        [sys.executable, "-m", "organizador"] + list(args),
        cwd=str(tmp_path),
        env=entorno,
        capture_output=True,
        text=True,
    )


def _preparar(tmp_path):
    origen = tmp_path / "descargas"
    origen.mkdir()
    (origen / "FOL_nomina.pdf").write_text("x", encoding="utf-8")
    salida = tmp_path / "Organizado"
    revision = salida / "_revision"
    revision.mkdir(parents=True)
    (revision / "trabajosql.pdf").write_text("x", encoding="utf-8")
    return origen, salida, revision


def test_punto_de_entrada_python_m_devuelve_version(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["organizador", "--version"])

    with pytest.raises(SystemExit) as salida:
        runpy.run_module("organizador", run_name="__main__")

    assert salida.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_cli_instalado_anuncia_los_seis_comandos(tmp_path):
    resultado = _ejecutar(tmp_path, "--help")

    assert resultado.returncode == 0
    for comando in (
        "ejecutar",
        "revisar",
        "deshacer",
        "reglas",
        "sugerir",
        "explicar",
    ):
        assert comando in resultado.stdout


def test_cli_instalado_json_de_tres_acciones_es_parseable(tmp_path):
    origen, salida, _ = _preparar(tmp_path)

    ejecutar = _ejecutar(
        tmp_path, "ejecutar", str(origen), "--salida", str(salida), "--json"
    )
    assert ejecutar.returncode == 0
    assert json.loads(ejecutar.stdout)["total"] == 1

    sugerir = _ejecutar(tmp_path, "sugerir", "--salida", str(salida), "--json")
    assert sugerir.returncode == 0
    propuestas = json.loads(sugerir.stdout)["propuestas"]
    assert propuestas[0]["destino"] == "BaseDeDatos/SQL"
    assert propuestas[0]["fuente"] == "heuristica"

    explicar = _ejecutar(
        tmp_path, "explicar", "trabajosql.pdf", "--salida", str(salida), "--json"
    )
    assert explicar.returncode == 0
    assert json.loads(explicar.stdout)["destino"] == "BaseDeDatos/SQL"

    texto = ejecutar.stdout + sugerir.stdout + explicar.stdout
    texto += ejecutar.stderr + sugerir.stderr + explicar.stderr
    assert "Bearer" not in texto
    assert "Authorization" not in texto


def test_cli_instalado_no_filtra_la_clave_de_entorno(tmp_path):
    origen, salida, _ = _preparar(tmp_path)
    _ejecutar(tmp_path, "ejecutar", str(origen), "--salida", str(salida), "--json")

    sugerir = _ejecutar(
        tmp_path,
        "sugerir",
        "--salida",
        str(salida),
        "--json",
        clave=CLAVE_FALSA,
    )
    explicar = _ejecutar(
        tmp_path,
        "explicar",
        "trabajosql.pdf",
        "--salida",
        str(salida),
        "--json",
        clave=CLAVE_FALSA,
    )

    texto = sugerir.stdout + sugerir.stderr + explicar.stdout + explicar.stderr
    assert CLAVE_FALSA not in texto
    assert "Bearer" not in texto


def test_cli_instalado_error_json_tiene_codigo_y_objeto_valido(tmp_path):
    resultado = _ejecutar(tmp_path, "ejecutar", str(tmp_path / "no_existe"), "--json")

    assert resultado.returncode == 1
    datos = json.loads(resultado.stdout)
    assert datos["ok"] is False
    assert datos["error"] == "CarpetaNoValidaError"
    assert resultado.stderr == ""


def test_cli_instalado_error_humano_no_muestra_traceback(tmp_path):
    resultado = _ejecutar(tmp_path, "ejecutar", str(tmp_path / "no_existe"))

    assert resultado.returncode == 1
    assert "Error:" in resultado.stderr
    assert "Traceback" not in resultado.stderr


def test_cli_instalado_aplicar_sin_confirmar_no_toca_archivos(tmp_path):
    _, salida, revision = _preparar(tmp_path)
    archivo = revision / "trabajosql.pdf"

    resultado = _ejecutar(
        tmp_path, "sugerir", "--salida", str(salida), "--aplicar", "--json"
    )

    assert resultado.returncode == 2
    datos = json.loads(resultado.stdout)
    assert datos["error"] == "ErrorDeUso"
    assert "--aplicar requiere --confirmar" in datos["mensaje"]
    assert archivo.is_file()
