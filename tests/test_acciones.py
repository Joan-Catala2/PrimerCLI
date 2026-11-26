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
from organizador.acciones.verificar import AccionVerificar
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
        podar=False,
        nombre="ejemplo.pdf",
        contenido=False,
        contenido_max_paginas=3,
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
        "verificar": AccionVerificar,
    }
    for nombre, clase in esperadas.items():
        accion = Acciones.desde_config(_args(accion=nombre), _consola())
        assert isinstance(accion, clase)
        # toda accion construida respeta el contrato base
        assert isinstance(accion, Accion)
        assert accion.nombre == nombre


def test_accion_nueva_se_despacha_sin_tocar_el_nucleo(monkeypatch, capsys):
    """Prueba viviente del ADR-002: una accion es una clase + su registro.

    Se define una accion jamas vista por el codigo (`palabras`), se inyecta
    en una COPIA del diccionario de registro y la fabrica la construye y la
    ejecuta sin que motor, presentacion ni excepciones hayan cambiado un
    byte. El registro original queda intacto para los demas candados.
    """

    class AccionPalabras(Accion):
        nombre = "palabras"

        def __init__(self, consola, nombres):
            super().__init__(consola)
            self.nombres = nombres

        @classmethod
        def desde_config(cls, args, consola):
            return cls(consola=consola, nombres=list(args.nombre))

        def ejecutar(self):
            for nombre in self.nombres:
                self.consola.linea(str(len(nombre.split())))
            return 0

    original = dict(Acciones._IMPLEMENTACIONES)
    ampliadas = dict(original)
    ampliadas["palabras"] = AccionPalabras
    monkeypatch.setattr(Acciones, "_IMPLEMENTACIONES", ampliadas)

    accion = Acciones.desde_config(
        _args(accion="palabras", nombre=["dos palabras aqui"]), _consola()
    )

    assert isinstance(accion, AccionPalabras)  # la fabrica la construye
    assert accion.ejecutar() == 0  # y el contrato base se cumple
    assert "3" in capsys.readouterr().out
    assert Acciones._IMPLEMENTACIONES is ampliadas  # copia: el original fuera


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
    assert accion.opciones["extensiones"] == ["pdf", "txt", "md"]  # type: ignore[attr-defined]


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
    assert [r.asignatura for r in accion.reglas] == ["X"]  # type: ignore[attr-defined]
    assert accion.opciones["reglas"] is accion.reglas  # type: ignore[attr-defined]


# --- flags de contenido (ADR-006) -----------------------------------------


def test_ejecutar_con_contenido_inyecta_extractor(tmp_path):
    """`--contenido` convierte la bandera en un extractor real en las opts."""
    accion = Acciones.desde_config(_args(accion="ejecutar", contenido=True), _consola())
    assert callable(accion.opciones.get("extractor"))  # type: ignore[attr-defined]


def test_ejecutar_sin_contenido_no_inyecta_extractor(tmp_path):
    accion = Acciones.desde_config(_args(accion="ejecutar"), _consola())
    assert "extractor" not in accion.opciones  # type: ignore[attr-defined]


def test_contenido_max_paginas_invalido_falla_antes_de_tocar_nada():
    from organizador.excepciones import ErrorDeUso

    with pytest.raises(ErrorDeUso):
        Acciones.desde_config(
            _args(accion="ejecutar", contenido=True, contenido_max_paginas=0),
            _consola(),
        )


def test_revisar_con_contenido_inyecta_extractor():
    accion = Acciones.desde_config(_args(accion="revisar", contenido=True), _consola())
    assert callable(accion.extractor)  # type: ignore[attr-defined]


def test_explicar_con_contenido_inyecta_extractor():
    accion = Acciones.desde_config(_args(accion="explicar", contenido=True), _consola())
    assert callable(accion.extractor)  # type: ignore[attr-defined]
