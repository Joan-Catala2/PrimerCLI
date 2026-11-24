"""El escudo self-hosted se genera del coverage.xml real."""

import importlib.util
import sys
from pathlib import Path

import pytest

_RUTA = Path(__file__).resolve().parents[1] / "scripts" / "badge.py"
_ESPEC = importlib.util.spec_from_file_location("badge", _RUTA)
assert _ESPEC is not None and _ESPEC.loader is not None
badge = importlib.util.module_from_spec(_ESPEC)
sys.modules["badge"] = badge
_ESPEC.loader.exec_module(badge)


def _xml(tmp_path, rate):
    ruta = tmp_path / "coverage.xml"
    ruta.write_text(
        '<coverage line-rate="{}"></coverage>'.format(rate), encoding="utf-8"
    )
    return ruta


def test_porcentaje_y_color_bueno(tmp_path):
    assert badge.porcentaje(_xml(tmp_path, "0.9319")) == pytest.approx(93.19)
    assert badge.data(93.19)["color"] == "brightgreen"


def test_por_debajo_del_umbral_en_rojo(tmp_path):
    assert badge.porcentaje(_xml(tmp_path, "0.80")) == pytest.approx(80.0)
    assert badge.data(80.0)["color"] == "red"


def test_mensaje_redondeado(tmp_path):
    assert badge.data(93.19)["message"] == "93%"


def test_xml_roto_es_error_de_cl(tmp_path):
    ruta = tmp_path / "coverage.xml"
    ruta.write_text("<coverage></coverage>", encoding="utf-8")
    with pytest.raises(SystemExit):
        badge.porcentaje(ruta)
