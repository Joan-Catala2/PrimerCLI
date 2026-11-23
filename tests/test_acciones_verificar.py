"""Pruebas de `verificar`: auditores, podar con papelera y restauracion exacta.

El contrato: sin `--podar` no se toca NADA. Con `--podar` sin `--confirmar`
tampoco. Con `--confirmar` se poda a la papelera del historial, y `deshacer`
(restauracion espejo) devuelve cada copia a su carpeta original exacta.
"""

import json

from organizador import cli


def _salida(tmp_path, *rutas):
    salida = tmp_path / "Organizado"
    for ruta in rutas:
        archivo = salida / ruta
        archivo.parent.mkdir(parents=True, exist_ok=True)
        archivo.write_bytes(b"contenido")
    return salida


def _logs(tmp_path):
    return sorted((tmp_path / "logs").glob("*.json"))


def _ejecutar(tmp_path, *extra):
    return cli.main(
        [
            "verificar",
            "--salida",
            str(tmp_path / "Organizado"),
            "--logs-dir",
            str(tmp_path / "logs"),
        ]
        + list(extra)
    )


# --- salidas y configuraciones imposibles ------------------------------------


def test_salida_inexistente_es_error_previsible(tmp_path, capsys):
    # main captura el OrganizadorError y devuelve su codigo, sin traceback
    codigo = cli.main(
        [
            "verificar",
            "--salida",
            str(tmp_path / "nada"),
            "--logs-dir",
            str(tmp_path / "logs"),
        ]
    )
    assert codigo == 1
    assert "No existe la carpeta de salida" in capsys.readouterr().err


def test_confirmar_sin_podar_es_error_de_uso(tmp_path, capsys):
    _salida(tmp_path, "FOL/a.pdf")
    assert _ejecutar(tmp_path, "--confirmar") == 2
    assert "--confirmar solo acompana a --podar" in capsys.readouterr().err


# --- detectores ---------------------------------------------------------------


def test_salida_limpia_devuelve_cero(tmp_path, capsys):
    _salida(tmp_path, "FOL/programacion_apuntes_tema1.pdf")
    assert _ejecutar(tmp_path, "--seco") == 0


def test_duplicados_detectados_por_hash(tmp_path, capsys):
    _salida(tmp_path, "FOL/a.pdf", "FOL/b.pdf", "FOL/c.pdf")
    assert _ejecutar(tmp_path) == 1
    salida = capsys.readouterr().out
    assert "duplicado:" in salida


def test_ignora_papelera_y_logs(tmp_path, monkeypatch, capsys):
    _salida(tmp_path, "FOL/a.pdf", "FOL/b.pdf")
    papelera = tmp_path / "logs" / ".papelera"
    papelera.mkdir(parents=True)
    (papelera / "a.pdf").write_bytes(b"contenido")
    (papelera / "b.pdf").write_bytes(b"contenido")
    assert _ejecutar(tmp_path) == 1
    salida_txt = capsys.readouterr().out
    assert ".papelera" not in salida_txt


def test_vacias_y_fuera_catalogo(tmp_path, capsys):
    salida = tmp_path / "Organizado"
    (salida / "ApuntesPrau").mkdir(parents=True)
    (salida / "ApuntesPrau" / "x.pdf").write_bytes(b"1")
    (salida / "Programacion").mkdir()
    assert _ejecutar(tmp_path) == 1
    texto = capsys.readouterr().out
    assert "fuera de catalogo: ApuntesPrau" in texto
    assert "carpeta vacia: Programacion" in texto


def test_atrapados_en_raiz_de_asignatura(tmp_path, capsys):
    _salida(tmp_path, "Programacion/java_tema_3.pdf")
    assert _ejecutar(tmp_path) == 1
    assert "atrapado: Programacion/java_tema_3.pdf -> Programacion/Java" in (
        capsys.readouterr().out
    )


def test_revision_reporta_aplicar_y_sugerir(tmp_path, capsys):
    _salida(tmp_path, "_revision/basededatos_transaccions.pdf")
    assert _ejecutar(tmp_path, "--json") == 1
    datos = json.loads(capsys.readouterr().out)
    assert datos["revision"] == {"total": 1, "aplicar": 1, "sugerir": 1}


def test_subproducto_de_navegador(tmp_path, capsys):
    _salida(tmp_path, "FOL/a.pdf")
    (tmp_path / "Organizado/FOL/a (1).pdf").write_bytes(b"distinto")
    assert _ejecutar(tmp_path) == 1
    assert "subproducto: FOL/a (1).pdf (copia de FOL/a.pdf)" in capsys.readouterr().out


def test_json_valido_y_con_estructura(tmp_path, capsys):
    _salida(tmp_path, "FOL/a.pdf", "FOL/b.pdf")
    assert _ejecutar(tmp_path, "--json") == 1
    datos = json.loads(capsys.readouterr().out)
    assert datos["ok"] is False and datos["accion"] == "verificar"
    assert datos["duplicados"] == [["FOL/a.pdf", "FOL/b.pdf"]]
    assert datos["errores"] == []


# --- podar ---------------------------------------------------------------------


def test_podar_sin_confirmar_no_toca_nada(tmp_path, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "n")
    _salida(tmp_path, "FOL/a.pdf", "FOL/b.pdf")
    assert _ejecutar(tmp_path, "--podar") == 1
    assert (tmp_path / "Organizado/FOL/a.pdf").exists()
    assert (tmp_path / "Organizado/FOL/b.pdf").exists()
    assert not (tmp_path / "logs/.papelera").exists()


def test_podar_eof_no_toca_nada(tmp_path, monkeypatch):
    def _eof(_):
        raise EOFError

    monkeypatch.setattr("builtins.input", _eof)
    _salida(tmp_path, "FOL/a.pdf", "FOL/b.pdf")
    assert _ejecutar(tmp_path, "--podar") == 1
    assert (tmp_path / "Organizado/FOL/b.pdf").exists()


def test_podar_json_sin_confirmar_avisa_y_no_mueve(tmp_path, capsys):
    _salida(tmp_path, "FOL/a.pdf", "FOL/b.pdf")
    assert _ejecutar(tmp_path, "--podar", "--json") == 1
    assert "requiere --confirmar" in capsys.readouterr().err


def test_podar_conserva_primera_y_va_a_papelera(tmp_path, capsys):
    _salida(tmp_path, "FOL/a.pdf", "FOL/z.pdf")
    assert _ejecutar(tmp_path, "--podar", "--confirmar") == 1
    assert (tmp_path / "Organizado/FOL/a.pdf").exists()
    assert not (tmp_path / "Organizado/FOL/z.pdf").exists()
    assert (tmp_path / "logs/.papelera/z.pdf").is_file()
    assert len(_logs(tmp_path)) == 1  # un unico log de poda, marca restaurar


def test_despues_de_podar_reaudita_y_deja_cero_duplicados(tmp_path, capsys):
    _salida(tmp_path, "FOL/a.pdf", "FOL/b.pdf", "FOL/c.pdf")
    assert _ejecutar(tmp_path, "--podar", "--confirmar") == 1
    assert "Duplicados:         0" in capsys.readouterr().out
    assert _ejecutar(tmp_path, "--json") == 0


def test_deshacer_restaura_las_copias_a_su_carpeta(tmp_path, capsys):
    _salida(tmp_path, "FOL/a.pdf", "FOL/b.pdf")
    _ejecutar(tmp_path, "--podar", "--confirmar")
    assert not (tmp_path / "Organizado/FOL/b.pdf").exists()

    codigo = cli.main(["deshacer", "--logs-dir", str(tmp_path / "logs")])

    assert codigo == 0
    assert (tmp_path / "Organizado/FOL/b.pdf").is_file()
    assert "logs" not in str((tmp_path / "Organizado/FOL/b.pdf").resolve())


def test_restauracion_multi_carpeta_devuelve_a_cada_una(tmp_path):
    _salida(tmp_path, "FOL/a.pdf", "FOL/b.pdf")
    (tmp_path / "Organizado/Programacion").mkdir()
    (tmp_path / "Organizado/Programacion/java_tema1.pdf").write_bytes(b"contenido")
    _ejecutar(tmp_path, "--podar", "--confirmar")
    assert not (tmp_path / "Organizado/Programacion/java_tema1.pdf").exists()

    assert cli.main(["deshacer", "--logs-dir", str(tmp_path / "logs")]) == 0

    assert (tmp_path / "Organizado/Programacion/java_tema1.pdf").is_file()
    assert (tmp_path / "Organizado/FOL/b.pdf").is_file()


def test_podar_con_nombre_repetido_usa_sufijo(tmp_path):
    _salida(tmp_path, "FOL/a.pdf", "FOL/b.pdf")
    papelera = tmp_path / "logs/.papelera"
    papelera.mkdir(parents=True)
    (papelera / "b.pdf").write_bytes(
        b"previo",
    )
    assert _ejecutar(tmp_path, "--podar", "--confirmar") == 1
    assert (papelera / "b.pdf").read_bytes() == b"previo"
    assert (papelera / "b-1.pdf").read_bytes() == b"contenido"


def test_seco_solo_resumen(tmp_path, capsys):
    _salida(tmp_path, "FOL/a.pdf", "FOL/b.pdf")
    assert _ejecutar(tmp_path, "--seco") == 1
    texto = capsys.readouterr().out
    assert "Resumen" in texto and "duplicado:" not in texto


def test_podar_se_deshace_por_ruta_exacta(tmp_path):
    """`deshacer --log` con un log de poda devuelve cada copia a su carpeta."""
    _salida(tmp_path, "FOL/a.pdf", "FOL/b.pdf")
    (tmp_path / "Organizado/Programacion").mkdir()
    (tmp_path / "Organizado/Programacion/java_tema1.pdf").write_bytes(b"contenido")
    _ejecutar(tmp_path, "--podar", "--confirmar")

    rutas = _logs(tmp_path)
    assert len(rutas) == 1  # un unico log por ejecucion de poda
    assert cli.main(["deshacer", "--log", str(rutas[0])]) == 0

    assert (tmp_path / "Organizado/FOL/b.pdf").is_file()
    assert (tmp_path / "Organizado/Programacion/java_tema1.pdf").is_file()


def test_papelera_queda_vacia_tras_deshacer(tmp_path):
    _salida(tmp_path, "FOL/a.pdf", "FOL/b.pdf")
    _ejecutar(tmp_path, "--podar", "--confirmar")
    rutas = _logs(tmp_path)
    cli.main(["deshacer", "--log", str(rutas[0])])
    papelera = tmp_path / "logs/.papelera"
    assert not papelera.exists() or not list(papelera.iterdir())


def test_deshacer_historial_reviente_poda_y_purga(tmp_path):
    """`deshacer` a secas (historial) tambien restaura desde la papelera."""
    _salida(tmp_path, "FOL/a.pdf", "FOL/b.pdf")
    _ejecutar(tmp_path, "--podar", "--confirmar")
    assert cli.main(["deshacer", "--logs-dir", str(tmp_path / "logs")]) == 0
    assert (tmp_path / "Organizado/FOL/b.pdf").is_file()
    papelera = tmp_path / "logs/.papelera"
    assert not papelera.exists() or not list(papelera.iterdir())


def test_deshacer_simular_no_toca_papelera_ni_copia(tmp_path):
    _salida(tmp_path, "FOL/a.pdf", "FOL/b.pdf")
    _ejecutar(tmp_path, "--podar", "--confirmar")
    ruta = _logs(tmp_path)[0]
    assert cli.main(["deshacer", "--log", str(ruta), "--simular"]) == 0
    assert (tmp_path / "logs/.papelera/b.pdf").is_file()
    assert not (tmp_path / "Organizado/FOL/b.pdf").exists()
    assert ruta.exists()  # simulacion: el log sigue vivo


def test_restaurar_papelera_sin_copia_es_error_humano(tmp_path):
    """Copia borrada de la papelera a mano: error por archivo, sin traceback."""
    from organizador.acciones.deshacer import _restaurar_papelera
    from organizador.registro import Registro

    datos = {
        "origen": str(tmp_path / "logs"),
        "movimientos": [
            {
                "nombre": "x.pdf",
                "asignatura": "",
                "tema": "",
                "destino": str(tmp_path / "Organizado/FOL/x.pdf"),
            }
        ],
    }
    resumen = _restaurar_papelera(datos, Registro(tmp_path / "logs"))
    assert resumen["deshechos"] == []
    assert resumen["errores"][0]["nombre"] == "x.pdf"
    assert "papelera" in resumen["errores"][0]["error"]


def test_deshacer_poda_json_valido(tmp_path, monkeypatch, capsys):
    """`deshacer` de una poda, en modo JSON: un unico documento parseable."""
    _salida(tmp_path, "FOL/a.pdf", "FOL/b.pdf")
    _ejecutar(
        tmp_path, "--podar", "--confirmar", "--json"
    )  # JSON primero: stdout limpio
    capsys.readouterr()
    ruta = _logs(tmp_path)[0]
    assert cli.main(["deshacer", "--log", str(ruta), "--json"]) == 0
    datos = json.loads(capsys.readouterr().out)
    assert len(datos["deshechos"]) == 1 and not datos["errores"]


def test_purga_no_rompe_si_la_papelera_ya_no_existe(tmp_path):
    from organizador.acciones.deshacer import AccionDeshacer
    from organizador.presentacion.consola import Consola
    from organizador.registro import Registro

    accion = AccionDeshacer(Consola(), Registro(tmp_path / "logs"))
    accion._purga_papelera()  # no lanza: la papelera brilla por su ausencia
