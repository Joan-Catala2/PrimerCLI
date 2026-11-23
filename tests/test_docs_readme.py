"""El README es la especificacion visible: si un comando no esta documentado,
no existe para quien instala la CLI. Esta prueba evita documentacion a la
deriva tras anyadir o renombrar comandos.
"""

import re
from pathlib import Path

import pytest

from organizador.cli import _construir_parser

RAIZ = Path(__file__).resolve().parents[1]
README = RAIZ / "README.md"

# Los seis comandos que debe documentar el README (y los que expone argparse).
COMANDOS = ("ejecutar", "revisar", "deshacer", "reglas", "sugerir", "explicar")


def _subcomandos_parser():
    parser = _construir_parser()
    for accion in parser._actions:
        choices = getattr(accion, "choices", None)
        if choices and set(COMANDOS) <= set(choices):
            return set(choices)
    raise AssertionError("el parser no declara subcomandos")


def test_parser_expon_los_seis_comandos():
    assert _subcomandos_parser() == set(COMANDOS)


@pytest.mark.parametrize("comando", COMANDOS)
def test_readme_documenta_el_comando(comando):
    texto = README.read_text(encoding="utf-8")
    assert re.search(rf"organizador {comando}\b", texto), (
        f"el README no documenta `organizador {comando}`"
    )
    assert re.search(rf"^- `{comando}`:", texto, flags=re.MULTILINE), (
        f"el README no explica què fa `{comando}` en la lista de opciones"
    )


def test_readme_no_promete_variables_de_entorno_inexistentes():
    """Solo las tres variables del ADR-003 son reales; nada de env vars fantasma."""
    texto = README.read_text(encoding="utf-8")
    assert set(re.findall(r"ORGANIZADOR_[A-Z_]+", texto)) == {
        "ORGANIZADOR_API_KEY",
        "ORGANIZADOR_IA_URL",
        "ORGANIZADOR_IA_MODELO",
    }
