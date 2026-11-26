"""Ctrl+C y permisos del historial: senales e interrupciones humanas.

Dos niveles, mismo contrato: ninguna senal del usuario (EOF ya estaba;
aqui SIGINT/KeyboardInterrupt) sale con traceback, y un historial sin
permisos degrada a aviso honesto, no a `PermissionError` en crudo (la
poda de `verificar` era el unico sitio sin cubrir: el `mkdir` de la
papelera estaba fuera de cualquier `try`).

La marca `skipif` de los tests de senal es POSIX: en Windows no existe
`signal.SIGINT` portable para un hijo, y `chmod` no niega permisos.
"""

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from organizador import cli

pytestmark = pytest.mark.skipif(
    os.name != "posix", reason="SIGINT a hijos y chmod solo en POSIX"
)

RAIZ = Path(__file__).resolve().parents[1]


def _interrumpida(_prompt=""):
    raise KeyboardInterrupt


@pytest.fixture()
def con_propuesta_aplicable(tmp_path, monkeypatch):
    """`Organizado/_revision` con un archivo que `aplicar` sabe proponer."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    revision = tmp_path / "Organizado" / "_revision"
    revision.mkdir(parents=True)
    (revision / "basededatos_transaccions.pdf").write_text("x", encoding="utf-8")
    return tmp_path


# --- KeyboardInterrupt -> 130 humano (paraguas de `cli.main`) -----------------


def test_ctrl_c_en_confirmar_de_vuelve_130_sin_mover_nada(
    tmp_path, monkeypatch, capsys
):
    origen = tmp_path / "descargas"
    origen.mkdir()
    (origen / "trabajosql.pdf").write_text("x", encoding="utf-8")
    monkeypatch.setattr("builtins.input", _interrumpida)

    codigo = cli.main(["ejecutar", str(origen), "--confirmar"])

    captured = capsys.readouterr()
    assert codigo == 130
    assert "Cancelado por el usuario (Ctrl+C)." in captured.out
    assert "Traceback" not in captured.out + captured.err
    assert (origen / "trabajosql.pdf").exists()  # confirmar pregunta ANTES de mover
    assert not (tmp_path / "organizador-logs").exists()


def test_ctrl_c_en_revisar_interactivo_devuelve_130(tmp_path, monkeypatch, capsys):
    revision = tmp_path / "Organizado" / "_revision"
    revision.mkdir(parents=True)
    (revision / "raro.pdf").write_text("x", encoding="utf-8")
    monkeypatch.setattr("builtins.input", _interrumpida)

    codigo = cli.main(
        ["revisar", "--salida", str(tmp_path / "Organizado"), "--interactivo"]
    )

    assert codigo == 130
    assert "Traceback" not in capsys.readouterr().out + capsys.readouterr().err
    assert (revision / "raro.pdf").exists()


def test_ctrl_c_en_aplicar_no_escribe_reglas(
    con_propuesta_aplicable, monkeypatch, capsys
):
    tmp_path = con_propuesta_aplicable
    monkeypatch.setattr("builtins.input", _interrumpida)

    codigo = cli.main(
        ["aplicar", "--salida", str(tmp_path / "Organizado"), "--confirmar"]
    )

    assert codigo == 130
    assert "Traceback" not in capsys.readouterr().err
    assert not (tmp_path / "config" / "organizador" / "reglas.json").exists()
    assert (
        tmp_path / "Organizado" / "_revision" / "basededatos_transaccions.pdf"
    ).exists()


def test_ctrl_c_en_podar_no_crea_papelera(tmp_path, monkeypatch, capsys):
    salida = tmp_path / "Organizado"
    (salida / "FOL").mkdir(parents=True)
    (salida / "FOL" / "a.pdf").write_bytes(b"mismo")
    (salida / "FOL" / "b.pdf").write_bytes(b"mismo")
    monkeypatch.setattr("builtins.input", _interrumpida)

    codigo = cli.main(
        [
            "verificar",
            "--salida",
            str(salida),
            "--logs-dir",
            str(tmp_path / "logs"),
            "--podar",
        ]
    )

    assert codigo == 130  # `--podar` sin `--confirmar` pregunta; el Ctrl+C
    assert not (tmp_path / "logs" / ".papelera").exists()  # pilla antes del mkdir


def test_ctrl_c_en_json_cierra_prompt_sin_soltar_texto(tmp_path, monkeypatch, capsys):
    origen = tmp_path / "descargas"
    origen.mkdir()
    (origen / "trabajosql.pdf").write_text("x", encoding="utf-8")
    monkeypatch.setattr("builtins.input", _interrumpida)

    codigo = cli.main(["ejecutar", str(origen), "--confirmar", "--json"])

    captured = capsys.readouterr()
    assert codigo == 130
    assert captured.out == ""  # stdout sigue virgen: aqui solo viviria JSON
    assert captured.err.endswith("\n")  # el prompt a medias quedo cerrado


# --- SIGINT real (senal del SO, no monkeypatch) -------------------------------


def _con_sigint_real(argv, cwd):
    """Lanza la CLI con stdin bloqueado y le manda SIGINT mientras pregunta.

    La tuberia de stdin se deja abierta del lado del test: `input()` queda
    esperando (nada de EOF) hasta que la senal la interrumpe, igual que en
    una terminal real.
    """
    lectura, escritura = os.pipe()
    entorno = dict(os.environ, PYTHONPATH=str(RAIZ / "src"))
    proc = subprocess.Popen(
        [sys.executable, "-m", "organizador", *argv],
        stdin=lectura,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=str(cwd),
        env=entorno,
    )
    os.close(lectura)
    time.sleep(0.6)  # dejar que la fabrica monte todo y el prompt salga
    os.kill(proc.pid, signal.SIGINT)
    salida = proc.communicate(timeout=15)
    os.close(escritura)
    return proc.returncode, salida


def test_sigint_real_en_confirmar_130_sin_traceback(tmp_path):
    origen = tmp_path / "descargas"
    origen.mkdir()
    (origen / "trabajosql.pdf").write_text("x", encoding="utf-8")

    codigo, (out, err) = _con_sigint_real(
        ["ejecutar", str(origen), "--confirmar"], tmp_path
    )

    assert codigo == 130
    assert "Cancelado por el usuario (Ctrl+C)." in out
    assert "Traceback" not in out + err
    assert (origen / "trabajosql.pdf").exists()


# --- D4: historial/papelera sin permisos (degradacion, no traceback) ---------


def _duplicados(salida):
    (salida / "FOL").mkdir(parents=True)
    (salida / "FOL" / "a.pdf").write_bytes(b"mismo")
    (salida / "FOL" / "b.pdf").write_bytes(b"mismo")


@pytest.fixture()
def chmod_disponible(tmp_path):
    yield
    for ruta in (tmp_path / "logs", tmp_path):
        try:
            os.chmod(ruta, 0o755)
        except OSError:
            pass


def test_podar_con_historial_ilegible_avisa_y_no_rompe(tmp_path, chmod_disponible):
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        pytest.skip("root lee carpetas 000: sin caso que probar")
    salida = tmp_path / "Organizado"
    _duplicados(salida)
    logs = tmp_path / "logs"
    logs.mkdir()
    os.chmod(logs, 0)

    codigo = cli.main(
        [
            "verificar",
            "--salida",
            str(salida),
            "--logs-dir",
            str(logs),
            "--podar",
            "--confirmar",
        ]
    )

    assert codigo == 1
    assert (salida / "FOL" / "a.pdf").is_file()
    assert (salida / "FOL" / "b.pdf").is_file()


def test_podar_ilegible_en_json_sigue_siendo_json(tmp_path, chmod_disponible, capsys):
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        pytest.skip("root lee carpetas 000")
    salida = tmp_path / "Organizado"
    _duplicados(salida)
    logs = tmp_path / "logs"
    logs.mkdir()
    os.chmod(logs, 0)

    codigo = cli.main(
        [
            "verificar",
            "--salida",
            str(salida),
            "--logs-dir",
            str(logs),
            "--podar",
            "--confirmar",
            "--json",
        ]
    )

    documento = json.loads(capsys.readouterr().out)  # no debe petar al parsear
    assert codigo == 1
    assert documento["ok"] is False
    assert documento["podados"] == []


def test_sugerir_aplicar_con_historial_ilegible_degrada_a_aviso(
    tmp_path, chmod_disponible, capsys
):
    """Mover puede fallar por log: no al reves. Aviso y rc 0, no traceback."""
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        pytest.skip("root lee carpetas 000")
    revision = tmp_path / "Organizado" / "_revision"
    revision.mkdir(parents=True)
    (revision / "examen redes.pdf").write_text("x", encoding="utf-8")
    logs = tmp_path / "logs"
    logs.mkdir()
    os.chmod(logs, 0)

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr("builtins.input", lambda _: "s")
    codigo = cli.main(
        [
            "sugerir",
            "--salida",
            str(tmp_path / "Organizado"),
            "--logs-dir",
            str(logs),
            "--aplicar",
            "--confirmar",
        ]
    )
    monkeypatch.undo()

    assert codigo == 0
    assert not (revision / "examen redes.pdf").exists()  # movido
    assert (tmp_path / "Organizado" / "SistemasInformaticos" / "Redes").is_dir()
