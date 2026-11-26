"""Regresiones del escaneo con permisos (modulo `escaneo.py`).

Un directorio que no se puede leer es un error previsible del usuario o del
sistema, no un bug: debe salir como mensaje humano con codigo 1 y sin
traceback (contrato de README "Errores previsibles"). Con `--recursivo` la
raiz ilegible sigue siendo error, pero una subcarpeta ilegible solo merece
un aviso: la pasada continua con lo que si se puede leer.

`chmod 000` no niega el acceso en Windows y root lo lee todo: si falta
alguna de las dos condiciones, skip honesto (nada de falsos verdes).
"""

import json
import os
import stat

import pytest

from organizador.cli import main
from organizador.escaneo import arbol, hijos
from organizador.excepciones import ErrorDeSistema
from organizador.organizador import organizar

pytestmark = pytest.mark.skipif(
    os.name != "posix" or (hasattr(os, "geteuid") and os.geteuid() == 0),
    reason="chmod 000 no niega lectura en Windows; root lo lee todo",
)


@pytest.fixture()
def sin_permiso(tmp_path):
    """Fabrica de carpetas 000 dentro de tmp_path, con restauracion final."""

    def _fabricar(nombre, contenido=("a.pdf",)):
        carpeta = tmp_path / nombre
        carpeta.mkdir()
        for archivo in contenido:
            (carpeta / archivo).touch()
        os.chmod(carpeta, 0)
        return carpeta

    yield _fabricar
    for ruta in sorted(tmp_path.rglob("*"), reverse=True):
        try:
            os.chmod(ruta, stat.S_IRWXU)
        except OSError:
            pass


def _texto(capsys):
    salidas = capsys.readouterr()
    texto = salidas.out + salidas.err
    assert "Traceback" not in texto
    return texto


def test_hijos_y_arbol_ilegibles_lanzan_error_humano(tmp_path, sin_permiso):
    ilegal = sin_permiso("ori")
    with pytest.raises(ErrorDeSistema) as info:
        hijos(ilegal)
    assert "No se puede leer" in str(info.value)
    with pytest.raises(ErrorDeSistema):
        arbol(ilegal)


def test_arbol_lista_symlinks_pero_no_desciende_por_ellos(tmp_path):
    raiz = tmp_path / "r"
    (raiz / "sub").mkdir(parents=True)
    (raiz / "sub" / "z.pdf").touch()
    (raiz / "a.pdf").touch()
    (raiz / "espejo").symlink_to(raiz, target_is_directory=True)
    (raiz / "roto.pdf").symlink_to("no-existe.pdf")
    assert arbol(raiz) == sorted(
        [
            raiz / "a.pdf",
            raiz / "espejo",
            raiz / "roto.pdf",
            raiz / "sub",
            raiz / "sub" / "z.pdf",
        ]
    )


def test_origen_ilegable_sale_como_error_humano(tmp_path, sin_permiso, capsys):
    origen = sin_permiso("ori")
    assert main(["ejecutar", str(origen)]) == 1
    texto = _texto(capsys)
    assert "Error:" in texto and "No se puede leer" in texto


def test_origen_ilegable_recursivo_tambien_es_error(tmp_path, sin_permiso, capsys):
    origen = sin_permiso("ori")
    assert main(["ejecutar", str(origen), "--recursivo"]) == 1
    assert "No se puede leer" in _texto(capsys)


def test_origen_ilegable_en_json_sigue_siendo_json(tmp_path, sin_permiso, capsys):
    origen = sin_permiso("ori")
    assert main(["ejecutar", str(origen), "--json"]) == 1
    documento = json.loads(capsys.readouterr().out)
    assert documento["ok"] is False and documento["error"] == "ErrorDeSistema"


def test_subcarpeta_ilegable_avisa_y_la_pasada_continua(tmp_path, sin_permiso):
    origen = tmp_path / "ori"
    origen.mkdir()
    (origen / "trabajosql.pdf").touch()
    sub = origen / "sub"
    sub.mkdir()
    (sub / "oculto.pdf").touch()
    os.chmod(sub, 0)
    resumen = organizar(origen, tmp_path / "salida", recursivo=True)
    assert [m["nombre"] for m in resumen["movimientos"]] == ["trabajosql.pdf"]
    assert any(str(sub) in aviso for aviso in resumen["avisos"])


def test_revisar_con_revision_ilegable_error_humano(tmp_path, capsys):
    revision = tmp_path / "Organizado" / "_revision"
    revision.mkdir(parents=True)
    (revision / "x.pdf").touch()
    os.chmod(revision, 0)
    salida = tmp_path / "Organizado"
    assert main(["revisar", "--salida", str(salida)]) == 1
    assert "No se puede leer" in _texto(capsys)


def test_deshacer_listar_con_logs_ilegibles_error_humano(tmp_path, sin_permiso, capsys):
    logs = sin_permiso("logs")
    assert main(["deshacer", "--logs-dir", str(logs), "--listar"]) == 1
    assert "No se puede leer" in _texto(capsys)


def test_verificar_con_salida_ilegable_error_humano(tmp_path, sin_permiso, capsys):
    salida = sin_permiso("Organizado")
    assert main(["verificar", "--salida", str(salida)]) == 1
    assert "No se puede leer" in _texto(capsys)
