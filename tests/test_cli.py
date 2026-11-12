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

    codigo = cli.main(["ejecutar", str(origen), "--salida", str(origen / "Organizado")])

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
    assert (
        salida / "Digitalizacion" / "Ofimatica" / "Digitalizacion_ofimatica.pdf"
    ).exists()

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
    assert (
        salida / "Digitalizacion" / "Ofimatica" / "Digitalizacion_ofimatica.pdf"
    ).exists()


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


def test_cli_recursivo(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    origen = tmp_path / "descargas"
    anidada = origen / "sub"
    anidada.mkdir(parents=True)
    (anidada / "Programacion_java_tema1.pdf").write_text("x", encoding="utf-8")
    salida = tmp_path / "Organizado"

    codigo = cli.main(["ejecutar", str(origen), "--salida", str(salida), "--recursivo"])

    assert codigo == 0
    assert (salida / "Programacion" / "Java" / "Programacion_java_tema1.pdf").exists()


def test_cli_extension_filtra(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    origen = tmp_path / "descargas"
    origen.mkdir()
    (origen / "FOL_nomina.pdf").write_text("x", encoding="utf-8")
    (origen / "notas.txt").write_text("x", encoding="utf-8")
    salida = tmp_path / "Organizado"

    codigo = cli.main(
        [
            "ejecutar",
            str(origen),
            "--salida",
            str(salida),
            "--extension",
            "pdf",
        ]
    )

    assert codigo == 0
    assert (salida / "FOL" / "Nomina" / "FOL_nomina.pdf").exists()
    assert (origen / "notas.txt").exists()


def test_cli_excluir_patron(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    origen = tmp_path / "descargas"
    origen.mkdir()
    (origen / "FOL_nomina.pdf").write_text("x", encoding="utf-8")
    (origen / "FOL_nomina_borrador.pdf").write_text("x", encoding="utf-8")
    salida = tmp_path / "Organizado"

    codigo = cli.main(
        [
            "ejecutar",
            str(origen),
            "--salida",
            str(salida),
            "--excluir",
            "*borrador*",
        ]
    )

    assert codigo == 0
    assert (salida / "FOL" / "Nomina" / "FOL_nomina.pdf").exists()
    assert (origen / "FOL_nomina_borrador.pdf").exists()


def test_cli_desde_fecha(tmp_path, monkeypatch):
    import os
    from datetime import datetime

    monkeypatch.chdir(tmp_path)
    origen = tmp_path / "descargas"
    origen.mkdir()
    viejo = origen / "FOL_nomina.pdf"
    nuevo = origen / "BaseDeDatos_sql.pdf"
    viejo.write_text("x", encoding="utf-8")
    nuevo.write_text("x", encoding="utf-8")
    antiguo = datetime(2020, 1, 1).timestamp()
    os.utime(viejo, (antiguo, antiguo))
    salida = tmp_path / "Organizado"

    codigo = cli.main(
        [
            "ejecutar",
            str(origen),
            "--salida",
            str(salida),
            "--desde",
            "2021-01-01",
        ]
    )

    assert codigo == 0
    assert viejo.exists()
    assert not (salida / "FOL").exists()
    assert (salida / "BaseDeDatos" / "SQL" / "BaseDeDatos_sql.pdf").exists()


def test_cli_desde_invalido(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    origen = tmp_path / "descargas"
    origen.mkdir()

    codigo = cli.main(["ejecutar", str(origen), "--desde", "ayer"])

    assert codigo == 1
    assert "YYYY-MM-DD" in capsys.readouterr().err


def test_cli_recursivo_no_organiza_el_historial(tmp_path, monkeypatch):
    origen = tmp_path / "descargas"
    origen.mkdir()
    monkeypatch.chdir(origen)
    (origen / "FOL_nomina.pdf").write_text("x", encoding="utf-8")
    salida = tmp_path / "Organizado"

    assert cli.main(["ejecutar", ".", "--salida", str(salida), "--recursivo"]) == 0
    assert len(_logs(origen)) == 1

    assert cli.main(["ejecutar", ".", "--salida", str(salida), "--recursivo"]) == 0
    assert len(_logs(origen)) == 1
    assert not any(salida.rglob("*.json"))


def test_cli_json_ejecutar(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    origen = tmp_path / "descargas"
    origen.mkdir()
    (origen / "FOL_nomina.pdf").write_text("x", encoding="utf-8")
    (origen / "notas.txt").write_text("x", encoding="utf-8")
    salida = tmp_path / "Organizado"

    codigo = cli.main(
        [
            "ejecutar",
            str(origen),
            "--salida",
            str(salida),
            "--extension",
            "pdf",
            "--json",
        ]
    )

    assert codigo == 0
    datos = json.loads(capsys.readouterr().out)
    assert datos["simulado"] is False
    assert datos["cancelado"] is False
    assert datos["filtrados"] == 1
    assert datos["total"] == 1
    assert datos["movimientos"][0]["asignatura"] == "FOL"
    assert datos["log"] is not None


def test_cli_json_revisar(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    salida = tmp_path / "Organizado"
    revision = salida / "_revision"
    revision.mkdir(parents=True)
    (revision / "a.pdf").write_text("x", encoding="utf-8")

    codigo = cli.main(["revisar", "--salida", str(salida), "--json"])

    assert codigo == 0
    datos = json.loads(capsys.readouterr().out)
    assert datos["existe"] is True
    assert datos["total"] == 1
    assert datos["archivos"] == ["a.pdf"]


def test_cli_confirmar_si(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    origen = tmp_path / "descargas"
    origen.mkdir()
    (origen / "FOL_nomina.pdf").write_text("x", encoding="utf-8")
    salida = tmp_path / "Organizado"
    monkeypatch.setattr("builtins.input", lambda _: "s")

    codigo = cli.main(["ejecutar", str(origen), "--salida", str(salida), "--confirmar"])

    assert codigo == 0
    assert (salida / "FOL" / "Nomina" / "FOL_nomina.pdf").exists()
    assert len(_logs(tmp_path)) == 1


def test_cli_confirmar_no(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    origen = tmp_path / "descargas"
    origen.mkdir()
    (origen / "FOL_nomina.pdf").write_text("x", encoding="utf-8")
    salida = tmp_path / "Organizado"
    monkeypatch.setattr("builtins.input", lambda _: "n")

    codigo = cli.main(["ejecutar", str(origen), "--salida", str(salida), "--confirmar"])

    assert codigo == 0
    assert (origen / "FOL_nomina.pdf").exists()
    assert not salida.exists()
    assert _logs(tmp_path) == []
    assert "Cancelado" in capsys.readouterr().out


def test_cli_confirmar_json(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    origen = tmp_path / "descargas"
    origen.mkdir()
    (origen / "FOL_nomina.pdf").write_text("x", encoding="utf-8")
    salida = tmp_path / "Organizado"
    monkeypatch.setattr("builtins.input", lambda: "s")

    codigo = cli.main(
        [
            "ejecutar",
            str(origen),
            "--salida",
            str(salida),
            "--confirmar",
            "--json",
        ]
    )

    assert codigo == 0
    datos = json.loads(capsys.readouterr().out)
    assert datos["simulado"] is False
    assert (salida / "FOL" / "Nomina" / "FOL_nomina.pdf").exists()


def test_cli_deshacer_listar(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    origen = tmp_path / "descargas"
    origen.mkdir()
    (origen / "FOL_nomina.pdf").write_text("x", encoding="utf-8")
    salida = tmp_path / "Organizado"
    assert cli.main(["ejecutar", str(origen), "--salida", str(salida)]) == 0

    codigo = cli.main(["deshacer", "--listar"])

    assert codigo == 0
    texto = capsys.readouterr().out
    assert "1 movimientos" in texto
    assert (salida / "FOL" / "Nomina" / "FOL_nomina.pdf").exists()
    assert len(_logs(tmp_path)) == 1


def test_cli_deshacer_listar_json(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    origen = tmp_path / "descargas"
    origen.mkdir()
    (origen / "FOL_nomina.pdf").write_text("x", encoding="utf-8")
    salida = tmp_path / "Organizado"
    assert cli.main(["ejecutar", str(origen), "--salida", str(salida)]) == 0

    capsys.readouterr()
    codigo = cli.main(["deshacer", "--listar", "--json"])

    assert codigo == 0
    datos = json.loads(capsys.readouterr().out)
    assert len(datos["logs"]) == 1
    assert datos["logs"][0]["movimientos"] == 1


def test_cli_deshacer_simular(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    origen = tmp_path / "descargas"
    origen.mkdir()
    (origen / "FOL_nomina.pdf").write_text("x", encoding="utf-8")
    salida = tmp_path / "Organizado"
    assert cli.main(["ejecutar", str(origen), "--salida", str(salida)]) == 0

    codigo = cli.main(["deshacer", "--simular"])

    assert codigo == 0
    texto = capsys.readouterr().out
    assert "[UNDO]" in texto
    assert "simulación" in texto
    assert (salida / "FOL" / "Nomina" / "FOL_nomina.pdf").exists()
    assert len(_logs(tmp_path)) == 1


def test_cli_deshacer_simular_json(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    origen = tmp_path / "descargas"
    origen.mkdir()
    (origen / "FOL_nomina.pdf").write_text("x", encoding="utf-8")
    salida = tmp_path / "Organizado"
    assert cli.main(["ejecutar", str(origen), "--salida", str(salida)]) == 0

    capsys.readouterr()
    codigo = cli.main(["deshacer", "--simular", "--json"])

    assert codigo == 0
    datos = json.loads(capsys.readouterr().out)
    assert datos["simulado"] is True
    assert datos["logs"][0]["borrado"] is False
    assert (salida / "FOL" / "Nomina" / "FOL_nomina.pdf").exists()
    assert len(_logs(tmp_path)) == 1


def test_cli_confirmar_eof(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    origen = tmp_path / "descargas"
    origen.mkdir()
    (origen / "FOL_nomina.pdf").write_text("x", encoding="utf-8")
    salida = tmp_path / "Organizado"

    def _eof(_):
        raise EOFError

    monkeypatch.setattr("builtins.input", _eof)

    codigo = cli.main(["ejecutar", str(origen), "--salida", str(salida), "--confirmar"])

    assert codigo == 0
    assert (origen / "FOL_nomina.pdf").exists()
    assert "Cancelado" in capsys.readouterr().out


def test_cli_extension_coma(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    origen = tmp_path / "descargas"
    origen.mkdir()
    (origen / "FOL_nomina.pdf").write_text("x", encoding="utf-8")
    (origen / "notas.txt").write_text("x", encoding="utf-8")
    salida = tmp_path / "Organizado"

    codigo = cli.main(
        ["ejecutar", str(origen), "--salida", str(salida), "--extension", "pdf,txt"]
    )

    assert codigo == 0
    assert (salida / "FOL" / "Nomina" / "FOL_nomina.pdf").exists()
    assert (salida / "_revision" / "notas.txt").exists()


def test_cli_deshacer_log_inexistente(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    codigo = cli.main(["deshacer", "--log", str(tmp_path / "no.json")])

    assert codigo == 0
    assert "No hay log" in capsys.readouterr().out


def test_cli_deshacer_log_invalido(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    ruta = tmp_path / "malo.json"
    ruta.write_text("{no", encoding="utf-8")

    codigo = cli.main(["deshacer", "--log", str(ruta)])

    assert codigo == 1
    assert "log inválido" in capsys.readouterr().err


def test_cli_deshacer_log_simular_json(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    origen = tmp_path / "descargas"
    origen.mkdir()
    (origen / "FOL_nomina.pdf").write_text("x", encoding="utf-8")
    salida = tmp_path / "Organizado"
    ruta_log = tmp_path / "logs" / "custom.json"
    assert (
        cli.main(
            [
                "ejecutar",
                str(origen),
                "--salida",
                str(salida),
                "--log",
                str(ruta_log),
            ]
        )
        == 0
    )
    capsys.readouterr()

    codigo = cli.main(["deshacer", "--log", str(ruta_log), "--simular", "--json"])

    assert codigo == 0
    datos = json.loads(capsys.readouterr().out)
    assert datos["simulado"] is True
    assert datos["borrado"] is False
    assert datos["deshechos"][0]["nombre"] == "FOL_nomina.pdf"
    assert ruta_log.exists()
    assert (salida / "FOL" / "Nomina" / "FOL_nomina.pdf").exists()


def test_cli_deshacer_listar_un_log(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    origen = tmp_path / "descargas"
    origen.mkdir()
    (origen / "FOL_nomina.pdf").write_text("x", encoding="utf-8")
    salida = tmp_path / "Organizado"
    ruta_log = tmp_path / "logs" / "custom.json"
    assert (
        cli.main(
            [
                "ejecutar",
                str(origen),
                "--salida",
                str(salida),
                "--log",
                str(ruta_log),
            ]
        )
        == 0
    )
    capsys.readouterr()

    codigo = cli.main(["deshacer", "--listar", "--log", str(ruta_log)])

    assert codigo == 0
    assert "1 movimientos" in capsys.readouterr().out


def test_cli_deshacer_listar_vacio(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    codigo = cli.main(["deshacer", "--listar"])

    assert codigo == 0
    assert "No hay logs" in capsys.readouterr().out


def test_cli_revisar_json_sin_carpeta(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    salida = tmp_path / "Organizado"

    codigo = cli.main(["revisar", "--salida", str(salida), "--json"])

    assert codigo == 0
    datos = json.loads(capsys.readouterr().out)
    assert datos["existe"] is False
    assert datos["total"] == 0


def test_cli_revisar_interactivo_json(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    salida = tmp_path / "Organizado"
    revision = salida / "_revision"
    revision.mkdir(parents=True)
    (revision / "raro.pdf").write_text("x", encoding="utf-8")
    respuestas = iter(["FOL", "Nomina"])
    monkeypatch.setattr("builtins.input", lambda: next(respuestas))

    codigo = cli.main(["revisar", "--salida", str(salida), "--interactivo", "--json"])

    assert codigo == 0
    datos = json.loads(capsys.readouterr().out)
    assert datos["movidos"][0]["asignatura"] == "FOL"
    assert datos["pendientes"] == 0
    assert (salida / "FOL" / "Nomina" / "raro.pdf").exists()


def test_cli_avisa_sobrescritura_log(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    origen = tmp_path / "descargas"
    origen.mkdir()
    (origen / "FOL_nomina.pdf").write_text("x", encoding="utf-8")
    salida = tmp_path / "Organizado"
    ruta_log = tmp_path / "logs" / "custom.json"
    assert (
        cli.main(
            [
                "ejecutar",
                str(origen),
                "--salida",
                str(salida),
                "--log",
                str(ruta_log),
            ]
        )
        == 0
    )
    capsys.readouterr()

    (origen / "BaseDeDatos_sql.pdf").write_text("x", encoding="utf-8")
    assert (
        cli.main(
            [
                "ejecutar",
                str(origen),
                "--salida",
                str(salida),
                "--log",
                str(ruta_log),
            ]
        )
        == 0
    )

    assert "se sobrescribira el log" in capsys.readouterr().err


def test_cli_revisar_acepta_sugerencia(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    salida = tmp_path / "Organizado"
    revision = salida / "_revision"
    revision.mkdir(parents=True)
    (revision / "FOL_nomina.pdf").write_text("x", encoding="utf-8")
    monkeypatch.setattr("builtins.input", lambda _: "")

    codigo = cli.main(["revisar", "--salida", str(salida), "--interactivo"])

    assert codigo == 0
    assert (salida / "FOL" / "Nomina" / "FOL_nomina.pdf").exists()


def test_cli_revisar_crea_asignatura(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    salida = tmp_path / "Organizado"
    revision = salida / "_revision"
    revision.mkdir(parents=True)
    (revision / "raro.pdf").write_text("x", encoding="utf-8")
    respuestas = iter(["Nueva", "s", "TemaX"])
    monkeypatch.setattr("builtins.input", lambda _: next(respuestas))

    codigo = cli.main(["revisar", "--salida", str(salida), "--interactivo"])

    assert codigo == 0
    assert (salida / "Nueva" / "TemaX" / "raro.pdf").exists()


def test_cli_revisar_crea_tema(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    salida = tmp_path / "Organizado"
    revision = salida / "_revision"
    revision.mkdir(parents=True)
    (revision / "FOL_nomina.pdf").write_text("x", encoding="utf-8")
    respuestas = iter(["", "Otro", "s"])
    monkeypatch.setattr("builtins.input", lambda _: next(respuestas))

    codigo = cli.main(["revisar", "--salida", str(salida), "--interactivo"])

    assert codigo == 0
    assert (salida / "FOL" / "Otro" / "FOL_nomina.pdf").exists()


def test_cli_revisar_sin_tema(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    salida = tmp_path / "Organizado"
    revision = salida / "_revision"
    revision.mkdir(parents=True)
    (revision / "FOL_nomina.pdf").write_text("x", encoding="utf-8")
    respuestas = iter(["", "-"])
    monkeypatch.setattr("builtins.input", lambda _: next(respuestas))

    codigo = cli.main(["revisar", "--salida", str(salida), "--interactivo"])

    assert codigo == 0
    assert (salida / "FOL" / "FOL_nomina.pdf").exists()


def test_cli_revisar_salir(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    salida = tmp_path / "Organizado"
    revision = salida / "_revision"
    revision.mkdir(parents=True)
    (revision / "raro.pdf").write_text("x", encoding="utf-8")
    monkeypatch.setattr("builtins.input", lambda _: "q")

    codigo = cli.main(["revisar", "--salida", str(salida), "--interactivo"])

    assert codigo == 0
    assert (revision / "raro.pdf").exists()
    assert "Sesión terminada" in capsys.readouterr().out
