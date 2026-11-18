"""El pre-commit anti-claves: detecta tokens reales y no estorba con texto limpio."""

import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
GUION = RAIZ / "scripts" / "check_secretos.py"


def _ejecutar(*rutas):
    return subprocess.run(
        [sys.executable, str(GUION)] + [str(ruta) for ruta in rutas],
        cwd=str(RAIZ),
        capture_output=True,
        text=True,
    )


def test_detecta_una_clave_con_patron_conocido(tmp_path):
    archivo = tmp_path / "fichero.py"
    archivo.write_text("token = 'sk-{}'\n".format("a" * 24), encoding="utf-8")

    resultado = _ejecutar(archivo)
    assert resultado.returncode == 1
    assert archivo.name in resultado.stderr


def test_no_rechaza_un_archivo_limpio(tmp_path):
    archivo = tmp_path / "limpio.py"
    archivo.write_text("ORGANIZADOR_API_KEY = os.environ.get('X')\n", encoding="utf-8")

    resultado = _ejecutar(archivo)
    assert resultado.returncode == 0
    assert resultado.stderr == ""


@pytest.mark.parametrize(
    "prefijo",
    ["ghp_", "AIza", "github_pat_"],
)
def test_detecta_tokens_de_otros_proveedores(tmp_path, prefijo):
    archivo = tmp_path / "token.py"
    archivo.write_text("token = '{}{}'\n".format(prefijo, "b" * 32), encoding="utf-8")

    resultado = _ejecutar(archivo)

    assert resultado.returncode == 1
    assert archivo.name in resultado.stderr


def test_no_rechaza_documentacion_que_explica_variables(tmp_path):
    archivo = tmp_path / "README.md"
    archivo.write_text(
        "Define ORGANIZADOR_API_KEY en el entorno; nunca lo escribas aqui.\n",
        encoding="utf-8",
    )

    assert _ejecutar(archivo).returncode == 0


def test_env_example_solo_contiene_nombres_vacios():
    contenido = (RAIZ / ".env.example").read_text(encoding="utf-8")
    variables = {}
    for linea in contenido.splitlines():
        if linea and not linea.startswith("#"):
            nombre, valor = linea.split("=", 1)
            variables[nombre] = valor

    assert variables == {
        "ORGANIZADOR_API_KEY": "",
        "ORGANIZADOR_IA_URL": "",
        "ORGANIZADOR_IA_MODELO": "",
    }
