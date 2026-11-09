import json

import pytest

from organizador import __version__, cli


def test_cli_escribe_log(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    origen = tmp_path / "descargas"
    origen.mkdir()
    (origen / "Programacion_java_tema1.pdf").write_text("x", encoding="utf-8")
    salida = tmp_path / "Organizado"

    codigo = cli.main(["ejecutar", str(origen), "--salida", str(salida)])

    assert codigo == 0
    log = json.loads((tmp_path / "organizador.log.json").read_text(encoding="utf-8"))
    assert log["origen"] == str(origen.resolve())
    assert log["salida"] == str(salida.resolve())
    assert log["errores"] == []
    assert log["movimientos"] == [
        {
            "nombre": "Programacion_java_tema1.pdf",
            "asignatura": "Programacion",
            "tema": "Java",
            "destino": str(
                salida / "Programacion" / "Java" / "Programacion_java_tema1.pdf"
            ),
        }
    ]
    assert "Programacion/Java/Programacion_java_tema1.pdf" in capsys.readouterr().out


def test_cli_simular_no_escribe_log(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    origen = tmp_path / "descargas"
    origen.mkdir()
    (origen / "FOL_nomina.pdf").write_text("x", encoding="utf-8")
    salida = tmp_path / "Organizado"

    codigo = cli.main(["ejecutar", str(origen), "--salida", str(salida), "--simular"])

    assert codigo == 0
    assert not (tmp_path / "organizador.log.json").exists()
    assert not salida.exists()


def test_cli_salida_dentro_del_origen_devuelve_error(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    origen = tmp_path / "descargas"
    origen.mkdir()
    (origen / "FOL_nomina.pdf").write_text("x", encoding="utf-8")

    codigo = cli.main(
        ["ejecutar", str(origen), "--salida", str(origen / "Organizado")]
    )

    assert codigo == 1
    assert "dentro del origen" in capsys.readouterr().err


def test_cli_revisar(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    salida = tmp_path / "Organizado"
    revision = salida / "_revision"
    revision.mkdir(parents=True)
    (revision / "a.pdf").write_text("x", encoding="utf-8")
    (revision / "b.pdf").write_text("x", encoding="utf-8")

    codigo = cli.main(["revisar", "--salida", str(salida)])

    assert codigo == 0
    texto = capsys.readouterr().out
    assert "a.pdf" in texto
    assert "b.pdf" in texto
    assert "Archivos a revisar: 2" in texto


def test_cli_revisar_interactivo(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    salida = tmp_path / "Organizado"
    revision = salida / "_revision"
    revision.mkdir(parents=True)
    archivo = revision / "raro.pdf"
    archivo.write_text("x", encoding="utf-8")
    respuestas = iter(["FOL", "Nomina"])
    monkeypatch.setattr("builtins.input", lambda _: next(respuestas))

    codigo = cli.main(["revisar", "--salida", str(salida), "--interactivo"])

    assert codigo == 0
    assert (salida / "FOL" / "Nomina" / "raro.pdf").exists()
    assert not archivo.exists()
    assert not revision.exists()
    assert "Archivos movidos: 1" in capsys.readouterr().out


def test_cli_deshacer(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    origen = tmp_path / "descargas"
    origen.mkdir()
    (origen / "FOL_nomina.pdf").write_text("x", encoding="utf-8")
    salida = tmp_path / "Organizado"
    assert cli.main(["ejecutar", str(origen), "--salida", str(salida)]) == 0
    assert not (origen / "FOL_nomina.pdf").exists()

    codigo = cli.main(["deshacer"])

    assert codigo == 0
    assert (origen / "FOL_nomina.pdf").exists()
    assert not (tmp_path / "organizador.log.json").exists()
    assert "[UNDO]" in capsys.readouterr().out


def test_cli_deshacer_sin_log(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    codigo = cli.main(["deshacer"])

    assert codigo == 0
    assert "No hay log" in capsys.readouterr().out


def test_cli_version(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["--version"])

    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_cli_reglas(capsys):
    codigo = cli.main(["reglas"])

    assert codigo == 0
    texto = capsys.readouterr().out
    assert "Programacion" in texto
    assert "  - Java" in texto
    assert "FOL" in texto


def test_cli_log_personalizado(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    origen = tmp_path / "descargas"
    origen.mkdir()
    (origen / "FOL_nomina.pdf").write_text("x", encoding="utf-8")
    salida = tmp_path / "Organizado"
    ruta_log = tmp_path / "logs" / "custom.json"

    codigo = cli.main(
        [
            "ejecutar",
            str(origen),
            "--salida",
            str(salida),
            "--log",
            str(ruta_log),
        ]
    )

    assert codigo == 0
    assert ruta_log.exists()
    assert not (tmp_path / "organizador.log.json").exists()

    assert cli.main(["deshacer", "--log", str(ruta_log)]) == 0
    assert (origen / "FOL_nomina.pdf").exists()
    assert not ruta_log.exists()
