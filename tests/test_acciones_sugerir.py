"""Pruebas de `sugerir`: propuestas, aplicacion opcional y degradacion.

Los casos feos son los que importan aqui: sin carpeta, `--aplicar` sin
confirmar y una API que falla. En ninguno se mueve un archivo por sorpresa.
"""

import argparse
import json

import pytest

from organizador import cli
from organizador.acciones import Acciones
from organizador.acciones.sugerir import AccionSugerir
from organizador.excepciones import ErrorDeUso, IAIndisponible
from organizador.presentacion.consola import Consola
from organizador.proveedor import Explicacion, ProveedorIA, Sugerencia
from organizador.registro import Registro
from organizador.reglas import Regla

REGLAS = (Regla("BaseDeDatos", ("basedatos", "sql"), (("SQL", ("sql", "consulta")),)),)


class ProveedorFalso(ProveedorIA):
    """Proveedor controlado: devuelve lo que le decimos o lanza un error."""

    disponible = True

    def __init__(self, sugerencias=None, error=None):
        self.sugerencias = sugerencias or []
        self.error = error

    def sugerir(self, nombres, reglas):
        if self.error is not None:
            raise self.error
        return self.sugerencias

    def explicar(self, nombre, destino, reglas):
        return Explicacion("Explicación de prueba", "ia")


class ConsolaQueConfirma(Consola):
    def confirmar(self, total):
        return True


class ConsolaQueRechaza(Consola):
    def confirmar(self, total):
        return False


class ConsolaJsonQueConfirma(Consola):
    def __init__(self):
        super().__init__(json_mode=True)

    def confirmar(self, total):
        return True


def _preparar(tmp_path, proveedor, aplicar=False, confirmar=False, consola=None):
    salida = tmp_path / "Organizado"
    revision = salida / "_revision"
    revision.mkdir(parents=True)
    (revision / "trabajosql.pdf").write_text("contenido", encoding="utf-8")
    accion = AccionSugerir(
        consola=consola or Consola(json_mode=False),
        salida=salida,
        reglas=REGLAS,
        proveedor=proveedor,
        registro=Registro(tmp_path / "logs"),
        aplicar=aplicar,
        confirmar=confirmar,
    )
    return accion, salida, revision


def _sugerencia():
    return Sugerencia(
        nombre="trabajosql.pdf",
        asignatura="BaseDeDatos",
        tema="SQL",
        confianza=0.9,
        fuente="ia",
        razon="por el alias sql",
    )


def test_sugerir_muestra_la_propuesta_sin_mover_nada(tmp_path, capsys):
    accion, _, revision = _preparar(tmp_path, ProveedorFalso([_sugerencia()]))

    assert accion.ejecutar() == 0
    salida = capsys.readouterr().out
    assert "trabajosql.pdf" in salida
    assert "BaseDeDatos" in salida
    assert "SQL" in salida
    assert "90%" in salida
    assert "Solo propuestas" in salida
    assert (revision / "trabajosql.pdf").is_file()


def test_sugerir_json_es_valido_y_no_escribe_en_stdout(tmp_path, capsys):
    accion, _, _ = _preparar(
        tmp_path,
        ProveedorFalso([_sugerencia()]),
        consola=Consola(json_mode=True),
    )

    assert accion.ejecutar() == 0
    capturado = capsys.readouterr()
    datos = json.loads(capturado.out)
    assert datos["ok"] is True
    assert datos["total"] == 1
    assert datos["propuestas"][0]["destino"] == "BaseDeDatos/SQL"
    assert datos["propuestas"][0]["aplicado"] is False
    assert capturado.err == ""


def test_sugerir_sin_carpeta_devuelve_json_vacio(tmp_path, capsys):
    accion = AccionSugerir(
        consola=Consola(json_mode=True),
        salida=tmp_path / "NoExiste",
        reglas=REGLAS,
        proveedor=ProveedorFalso(),
        registro=Registro(tmp_path / "logs"),
    )

    assert accion.ejecutar() == 0
    datos = json.loads(capsys.readouterr().out)
    assert datos["total"] == 0
    assert datos["propuestas"] == []


def test_aplicar_sin_confirmar_falla_antes_de_crear_nada(tmp_path):
    args = argparse.Namespace(
        accion="sugerir",
        salida=str(tmp_path / "Organizado"),
        reglas=None,
        logs_dir=str(tmp_path / "logs"),
        aplicar=True,
        confirmar=False,
        json=False,
    )

    with pytest.raises(ErrorDeUso, match="--aplicar requiere --confirmar"):
        Acciones.desde_config(args, Consola())
    assert not (tmp_path / "Organizado").exists()


def test_api_caida_cae_a_heuristicas_y_sigue(tmp_path, capsys):
    proveedor = ProveedorFalso(error=IAIndisponible("sin red"))
    accion, _, revision = _preparar(tmp_path, proveedor)

    assert accion.ejecutar() == 0
    capturado = capsys.readouterr()
    assert "IA no disponible" in capturado.err
    assert "heuristica" in capturado.out
    assert (revision / "trabajosql.pdf").is_file()


def test_aplicar_confirmado_mueve_y_deja_log(tmp_path):
    proveedor = ProveedorFalso([_sugerencia()])
    accion, salida, revision = _preparar(
        tmp_path,
        proveedor,
        aplicar=True,
        confirmar=True,
        consola=ConsolaQueConfirma(),
    )

    assert accion.ejecutar() == 0
    assert not (revision / "trabajosql.pdf").exists()
    assert (salida / "BaseDeDatos" / "SQL" / "trabajosql.pdf").is_file()
    assert list((tmp_path / "logs").glob("*.json"))


def test_aplicar_rechazado_no_mueve_nada(tmp_path):
    proveedor = ProveedorFalso([_sugerencia()])
    accion, _, revision = _preparar(
        tmp_path,
        proveedor,
        aplicar=True,
        confirmar=True,
        consola=ConsolaQueRechaza(),
    )

    assert accion.ejecutar() == 0
    assert (revision / "trabajosql.pdf").is_file()


def test_sugerir_aplicado_se_puede_deshacer(tmp_path, monkeypatch, capsys):
    accion, _, revision = _preparar(
        tmp_path,
        ProveedorFalso([_sugerencia()]),
        aplicar=True,
        confirmar=True,
        consola=ConsolaQueConfirma(),
    )
    assert accion.ejecutar() == 0

    monkeypatch.chdir(tmp_path)
    codigo = cli.main(["deshacer", "--logs-dir", str(tmp_path / "logs")])

    assert codigo == 0
    assert (revision / "trabajosql.pdf").is_file()
    assert "[UNDO]" in capsys.readouterr().out


def test_sin_propuestas_aplicar_no_mueve_ni_escribe_log(tmp_path):
    sin_destino = Sugerencia(
        nombre="trabajosql.pdf", fuente="ia", razon="sin propuesta fiable"
    )
    accion, _, revision = _preparar(
        tmp_path,
        ProveedorFalso([sin_destino]),
        aplicar=True,
        confirmar=True,
        consola=ConsolaQueConfirma(),
    )

    assert accion.ejecutar() == 0
    assert (revision / "trabajosql.pdf").is_file()
    assert not list((tmp_path / "logs").glob("*.json"))


def test_aplicar_sin_tema_mueve_a_la_raiz_de_la_asignatura(tmp_path):
    sin_tema = Sugerencia(
        nombre="trabajosql.pdf",
        asignatura="BaseDeDatos",
        tema="",
        confianza=0.7,
        fuente="ia",
        razon="solo asignatura",
    )
    accion, salida, _ = _preparar(
        tmp_path,
        ProveedorFalso([sin_tema]),
        aplicar=True,
        confirmar=True,
        consola=ConsolaQueConfirma(),
    )

    assert accion.ejecutar() == 0
    assert (salida / "BaseDeDatos" / "trabajosql.pdf").is_file()


def test_error_al_mover_se_cuenta_en_json(tmp_path, monkeypatch, capsys):
    def fallar(*args, **kwargs):
        raise OSError("permiso denegado")

    monkeypatch.setattr("organizador.acciones.sugerir.mover_archivo", fallar)
    accion, _, revision = _preparar(
        tmp_path,
        ProveedorFalso([_sugerencia()]),
        aplicar=True,
        confirmar=True,
        consola=ConsolaJsonQueConfirma(),
    )

    assert accion.ejecutar() == 0
    datos = json.loads(capsys.readouterr().out)
    assert datos["errores"][0]["error"] == "permiso denegado"
    assert (revision / "trabajosql.pdf").is_file()


def test_error_al_escribir_el_log_avisa_y_no_rompe(tmp_path, capsys):
    def fallar(*args, **kwargs):
        raise OSError("disco lleno")

    accion, salida, _ = _preparar(
        tmp_path,
        ProveedorFalso([_sugerencia()]),
        aplicar=True,
        confirmar=True,
        consola=ConsolaQueConfirma(),
    )
    accion.registro.guardar_historial = fallar

    assert accion.ejecutar() == 0
    assert (salida / "BaseDeDatos" / "SQL" / "trabajosql.pdf").is_file()
    assert "no se pudo escribir el log" in capsys.readouterr().err


def test_sugerir_sin_carpeta_en_humano_avisa(tmp_path, capsys):
    accion = AccionSugerir(
        consola=Consola(),
        salida=tmp_path / "NoExiste",
        reglas=REGLAS,
        proveedor=ProveedorFalso(),
        registro=Registro(tmp_path / "logs"),
    )

    assert accion.ejecutar() == 0
    assert "No existe la carpeta de revisión" in capsys.readouterr().out


def test_sugerir_carpeta_vacia_en_humano_avisa(tmp_path, capsys):
    salida = tmp_path / "Organizado"
    (salida / "_revision").mkdir(parents=True)
    accion = AccionSugerir(
        consola=Consola(),
        salida=salida,
        reglas=REGLAS,
        proveedor=ProveedorFalso(),
        registro=Registro(tmp_path / "logs"),
    )

    assert accion.ejecutar() == 0
    assert "No hay archivos pendientes" in capsys.readouterr().out
