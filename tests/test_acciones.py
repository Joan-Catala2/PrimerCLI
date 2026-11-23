"""Pruebas de las fabricas: `Acciones.desde_config` y `*.desde_config`.

Lo que se comprueba aqui es el *contrato de construccion*: una configuracion
correcta produce la accion adecuada con sus dependencias resueltas, y una
configuracion imposible falla ANTES de tocar el disco. Por eso casi todos
los casos feos miran excepciones y no efectos en el sistema de archivos.
"""

import argparse
import json

import pytest

from organizador.acciones import Acciones
from organizador.acciones.aplicar import AccionAplicar
from organizador.acciones.base import Accion
from organizador.acciones.deshacer import AccionDeshacer
from organizador.acciones.ejecutar import AccionEjecutar
from organizador.acciones.explicar import AccionExplicar
from organizador.acciones.reglas import AccionReglas
from organizador.acciones.revisar import AccionRevisar
from organizador.acciones.sugerir import AccionSugerir
from organizador.excepciones import (
    AccionNoValida,
    ConfigError,
    ErrorDeUso,
)
from organizador.presentacion.consola import Consola


def _args(**datos):
    """Namespace de argparse minimo con los valores que pide cada accion."""
    base = dict(
        accion="ejecutar",
        origen=".",
        salida="Organizado",
        seco=False,
        simular=False,
        confirmar=False,
        log=None,
        logs_dir="organizador-logs",
        reglas=None,
        recursivo=False,
        extension=[],
        excluir=[],
        desde=None,
        json=False,
        interactivo=False,
        ultimos=1,
        listar=False,
        aplicar=False,
        reorganizar=False,
        nombre="ejemplo.pdf",
    )
    base.update(datos)
    return argparse.Namespace(**base)


def _consola():
    return Consola(json_mode=False)


# --- fabrica de registro -------------------------------------------------


def test_desde_config_devuelve_la_accion_de_cada_nombre():
    esperadas = {
        "ejecutar": AccionEjecutar,
        "revisar": AccionRevisar,
        "deshacer": AccionDeshacer,
        "reglas": AccionReglas,
        "sugerir": AccionSugerir,
        "explicar": AccionExplicar,
        "aplicar": AccionAplicar,
    }
    for nombre, clase in esperadas.items():
        accion = Acciones.desde_config(_args(accion=nombre), _consola())
        assert isinstance(accion, clase)
        # toda accion construida respeta el contrato base
        assert isinstance(accion, Accion)
        assert accion.nombre == nombre


def test_desde_config_con_accion_inventada_falla_al_construir():
    with pytest.raises(AccionNoValida, match="no reconocida"):
        Acciones.desde_config(_args(accion="teletransportar"), _consola())


def test_fecha_invalida_falla_antes_de_tocar_el_disco(tmp_path):
    """`--desde ayer` es ErrorDeUso al construir: ni se organiza nada."""
    with pytest.raises(ErrorDeUso, match="YYYY-MM-DD"):
        Acciones.desde_config(
            _args(accion="ejecutar", origen=str(tmp_path), desde="ayer"), _consola()
        )
    assert list(tmp_path.iterdir()) == []


def test_ultimos_cero_es_error_de_uso_en_la_fabrica():
    with pytest.raises(ErrorDeUso, match="--ultimos"):
        Acciones.desde_config(_args(accion="deshacer", ultimos=0), _consola())


def test_reglas_corruptas_falla_antes_de_cualquier_effeto(tmp_path):
    """ConfigError al construir: ni `_revision` ni logs se crean."""
    ruta = tmp_path / "reglas.json"
    ruta.write_text("{no", encoding="utf-8")

    with pytest.raises(ConfigError, match="JSON invalido"):
        Acciones.desde_config(_args(accion="reglas", reglas=str(ruta)), _consola())
    assert list(tmp_path.iterdir()) == [ruta]


def test_desde_config_no_monta_las_demas_acciones():
    """`reglas` no debe exigir opts de `ejecutar`: namespace minimo."""
    args = argparse.Namespace(accion="reglas", reglas=None)
    accion = Acciones.desde_config(args, _consola())
    assert isinstance(accion, AccionReglas)


def test_ejecutar_lleva_las_extensiones_aplanadas():
    args = _args(accion="ejecutar", extension=["pdf,txt", "md"])
    accion = Acciones.desde_config(args, _consola())
    assert accion.opciones["extensiones"] == ["pdf", "txt", "md"]


def test_json_mode_viaja_a_la_consola_de_la_accion():
    args = _args(accion="reglas")
    consola = Consola.desde_config(args)
    accion = Acciones.desde_config(args, consola)
    assert accion.consola is consola


def test_ejecutar_reusa_las_reglas_ya_cargadas(tmp_path):
    """La fabrica resuelve las dependencias una vez y las pasa dentro."""
    ruta = tmp_path / "reglas.json"
    ruta.write_text(
        json.dumps([{"asignatura": "X", "aliases": ["x"], "temas": []}]),
        encoding="utf-8",
    )
    accion = Acciones.desde_config(
        _args(accion="ejecutar", reglas=str(ruta)), _consola()
    )
    assert [r.asignatura for r in accion.reglas] == ["X"]
    assert accion.opciones["reglas"] is accion.reglas
