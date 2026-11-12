import json

import pytest

from organizador import __version__, cli


def _logs(base):
    return sorted((base / "organizador-logs").glob("*.json"))


def test_cli_escribe_log(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    origen = tmp_path / "descargas"
    origen.mkdir()
    (origen / "Programacion_java_tema1.pdf").write_text("x", encoding="utf-8")
    salida = tmp_path / "Organizado"

    codigo = cli.main(["ejecutar", str(origen), "--salida", str(salida)])

    assert codigo == 0
    logs = _logs(tmp_path)
    assert len(logs) == 1
    log = json.loads(logs[0].read_text(encoding="utf-8"))
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
    assert not (tmp_path / "organizador-logs").exists()
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
    assert _logs(tmp_path) == []
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
    assert not (tmp_path / "organizador-logs").exists()

    assert cli.main(["deshacer", "--log", str(ruta_log)]) == 0
    assert (origen / "FOL_nomina.pdf").exists()
    assert not ruta_log.exists()


def test_cli_log_no_organiza_el_historial(tmp_path, monkeypatch):
    origen = tmp_path / "descargas"
    origen.mkdir()
    monkeypatch.chdir(origen)
    (origen / "FOL_nomina.pdf").write_text("x", encoding="utf-8")
    salida = tmp_path / "Organizado"

    assert cli.main(["ejecutar", ".", "--salida", str(salida)]) == 0
    logs = _logs(origen)
    assert len(logs) == 1

    assert cli.main(["ejecutar", ".", "--salida", str(salida)]) == 0
    assert logs[0].exists()
    assert len(_logs(origen)) == 1


def test_cli_pasada_vacia_no_pisa_el_log(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    origen = tmp_path / "descargas"
    origen.mkdir()
    (origen / "FOL_nomina.pdf").write_text("x", encoding="utf-8")
    salida = tmp_path / "Organizado"

    assert cli.main(["ejecutar", str(origen), "--salida", str(salida)]) == 0
    assert cli.main(["ejecutar", str(origen), "--salida", str(salida)]) == 0

    logs = _logs(tmp_path)
    assert len(logs) == 1
    log = json.loads(logs[0].read_text(encoding="utf-8"))
    assert len(log["movimientos"]) == 1


def test_cli_deshacer_con_error_devuelve_1(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    origen = tmp_path / "descargas"
    origen.mkdir()
    (origen / "FOL_nomina.pdf").write_text("x", encoding="utf-8")
    salida = tmp_path / "Organizado"

    assert cli.main(["ejecutar", str(origen), "--salida", str(salida)]) == 0
    (salida / "FOL" / "Nomina" / "FOL_nomina.pdf").unlink()

    assert cli.main(["deshacer"]) == 1
    assert len(_logs(tmp_path)) == 1


def test_cli_deshacer_ultimos(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    origen = tmp_path / "descargas"
    origen.mkdir()
    (origen / "FOL_nomina.pdf").write_text("x", encoding="utf-8")
    salida = tmp_path / "Organizado"
    assert cli.main(["ejecutar", str(origen), "--salida", str(salida)]) == 0

    (origen / "BaseDeDatos_sql.pdf").write_text("x", encoding="utf-8")
    assert cli.main(["ejecutar", str(origen), "--salida", str(salida)]) == 0
    assert len(_logs(tmp_path)) == 2

    codigo = cli.main(["deshacer", "--ultimos", "2"])

    assert codigo == 0
    assert (origen / "FOL_nomina.pdf").exists()
    assert (origen / "BaseDeDatos_sql.pdf").exists()
    assert _logs(tmp_path) == []


def test_cli_revisar_interactivo_eof(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    salida = tmp_path / "Organizado"
    revision = salida / "_revision"
    revision.mkdir(parents=True)
    (revision / "raro.pdf").write_text("x", encoding="utf-8")

    def _eof(_):
        raise EOFError

    monkeypatch.setattr("builtins.input", _eof)

    codigo = cli.main(["revisar", "--salida", str(salida), "--interactivo"])

    assert codigo == 130
    assert (revision / "raro.pdf").exists()
    assert "Entrada cancelada" in capsys.readouterr().out


def _escribir_reglas_digitalizacion(ruta):
    ruta.parent.mkdir(parents=True, exist_ok=True)
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


def test_cli_reglas_personalizadas(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    origen = tmp_path / "descargas"
    origen.mkdir()
    (origen / "Digitalizacion_ofimatica.pdf").write_text("x", encoding="utf-8")
    salida = tmp_path / "Organizado"
    reglas = tmp_path / "mis_reglas.json"
    _escribir_reglas_digitalizacion(reglas)

    codigo = cli.main(
        [
            "ejecutar",
            str(origen),
            "--salida",
            str(salida),
            "--reglas",
            str(reglas),
        ]
    )

    assert codigo == 0
    assert (salida / "Digitalizacion" / "Ofimatica" / "Digitalizacion_ofimatica.pdf").exists()

    assert cli.main(["reglas", "--reglas", str(reglas)]) == 0
    texto = capsys.readouterr().out
    assert "Digitalizacion" in texto
    assert "Programacion" not in texto


def test_cli_reglas_usuario_autoload(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    origen = tmp_path / "descargas"
    origen.mkdir()
    (origen / "Digitalizacion_ofimatica.pdf").write_text("x", encoding="utf-8")
    salida = tmp_path / "Organizado"

    config = tmp_path / "config" / "organizador" / "reglas.json"
    _escribir_reglas_digitalizacion(config)

    codigo = cli.main(["ejecutar", str(origen), "--salida", str(salida)])

    assert codigo == 0
    assert (salida / "Digitalizacion" / "Ofimatica" / "Digitalizacion_ofimatica.pdf").exists()


def test_cli_reglas_invalidas_devuelven_1(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    origen = tmp_path / "descargas"
    origen.mkdir()
    (origen / "FOL_nomina.pdf").write_text("x", encoding="utf-8")
    reglas = tmp_path / "malas.json"
    reglas.write_text("{no es json", encoding="utf-8")

    codigo = cli.main(["ejecutar", str(origen), "--reglas", str(reglas)])

    assert codigo == 1
    assert "JSON invalido" in capsys.readouterr().err
