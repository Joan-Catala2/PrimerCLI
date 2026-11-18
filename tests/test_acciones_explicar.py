"""Pruebas de `explicar`: razon local, IA simulada y JSON limpio."""

import json

from organizador.acciones.explicar import AccionExplicar
from organizador.excepciones import IAIndisponible
from organizador.presentacion.consola import Consola
from organizador.proveedor import (
    Explicacion,
    ProveedorHeuristico,
    ProveedorIA,
)
from organizador.reglas import Regla

REGLAS = (Regla("BaseDeDatos", ("basedatos", "sql"), (("SQL", ("sql", "consulta")),)),)


class ProveedorFalso(ProveedorIA):
    disponible = True

    def __init__(self, explicacion=None, error=None):
        self.explicacion = explicacion
        self.error = error

    def sugerir(self, nombres, reglas):
        return []

    def explicar(self, nombre, destino, reglas):
        if self.error is not None:
            raise self.error
        return self.explicacion


def _accion(tmp_path, proveedor, nombre="trabajosql.pdf", json_mode=False):
    return AccionExplicar(
        consola=Consola(json_mode=json_mode),
        archivo=nombre,
        salida=tmp_path / "Organizado",
        reglas=REGLAS,
        proveedor=proveedor,
    )


def test_explicar_con_ia_devuelve_la_frase_y_el_destino(tmp_path, capsys):
    proveedor = ProveedorFalso(
        Explicacion("Por el alias sql del nombre.", "ia", "local")
    )
    accion = _accion(tmp_path, proveedor)

    assert accion.ejecutar() == 0
    salida = capsys.readouterr().out
    assert "Por el alias sql" in salida
    assert "BaseDeDatos/SQL" in salida
    assert "Fuente: ia" in salida


def test_explicar_json_es_valido(tmp_path, capsys):
    proveedor = ProveedorFalso(Explicacion("Por el alias sql.", "ia"))
    accion = _accion(tmp_path, proveedor, json_mode=True)

    assert accion.ejecutar() == 0
    datos = json.loads(capsys.readouterr().out)
    assert datos["ok"] is True
    assert datos["destino"] == "BaseDeDatos/SQL"
    assert datos["fuente"] == "ia"
    assert datos["razon_local"]


def test_explicar_nombre_sin_reglas_dice_revision(tmp_path, capsys):
    accion = _accion(tmp_path, ProveedorHeuristico(), nombre="incomprensible.pdf")

    assert accion.ejecutar() == 0
    salida = capsys.readouterr().out
    assert "_revision" in salida
    assert "Ningún alias" in salida


def test_explicar_con_ia_caida_usa_la_razon_local(tmp_path, capsys):
    proveedor = ProveedorFalso(error=IAIndisponible("timeout"))
    accion = _accion(tmp_path, proveedor)

    assert accion.ejecutar() == 0
    capturado = capsys.readouterr()
    assert "IA no disponible" in capturado.err
    assert "alias 'sql'" in capturado.out
    assert "Fuente: reglas" in capturado.out
