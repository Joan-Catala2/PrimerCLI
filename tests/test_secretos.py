"""El pre-commit anti-claves: detecta tokens reales y no estorba con texto limpio."""

import subprocess
import sys
from pathlib import Path

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
