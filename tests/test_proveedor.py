"""Pruebas del proveedor de IA: fabrica, HTTP simulado y fallback.

La clave de prueba NO es una clave real: el test comprueba precisamente que
no aparece en `str`, `repr` ni mensajes. Ningun test llama a una red real.
"""

import json
import urllib.error

import pytest

from organizador.excepciones import IAIndisponible
from organizador.proveedor import (
    ProveedorApi,
    ProveedorHeuristico,
    ProveedorIA,
)
from organizador.reglas import Regla

REGLAS = (
    Regla("BaseDeDatos", ("basedatos", "sql"), (("SQL", ("sql", "consulta")),)),
    Regla("Programacion", ("programacion", "java"), (("Java", ("java",)),)),
)
CLAVE = "clave-de-prueba-no-real"


class _Respuesta:
    """Sustituto del objeto que devuelve `urlopen`."""

    def __init__(self, objeto):
        self.objeto = objeto

    def __enter__(self):
        return self

    def __exit__(self, tipo, valor, traza):
        return False

    def read(self):
        return json.dumps(self.objeto).encode("utf-8")


def _abrir_falso(objeto):
    vistas = []

    def abrir(solicitud, timeout=None):
        vistas.append((solicitud, timeout))
        return _Respuesta(objeto)

    return abrir, vistas


def _respuesta_ia(contenido):
    return {
        "choices": [
            {
                "message": {
                    "content": contenido
                    if isinstance(contenido, str)
                    else json.dumps(contenido)
                }
            }
        ]
    }


def test_desde_env_sin_configuracion_devuelve_el_fallback(monkeypatch):
    for nombre in (
        "ORGANIZADOR_API_KEY",
        "ORGANIZADOR_IA_URL",
        "ORGANIZADOR_IA_MODELO",
    ):
        monkeypatch.delenv(nombre, raising=False)

    proveedor = ProveedorIA.desde_env()
    assert isinstance(proveedor, ProveedorHeuristico)
    assert proveedor.disponible is False


def test_desde_env_con_configuracion_no_revela_la_clave(monkeypatch):
    monkeypatch.setenv("ORGANIZADOR_API_KEY", CLAVE)
    monkeypatch.setenv("ORGANIZADOR_IA_URL", "https://ejemplo.invalid/v1/chat")
    monkeypatch.setenv("ORGANIZADOR_IA_MODELO", "modelo-de-prueba")

    proveedor = ProveedorIA.desde_env()
    assert isinstance(proveedor, ProveedorApi)
    assert proveedor.disponible is True
    assert CLAVE not in str(proveedor)
    assert CLAVE not in repr(proveedor)


def test_desde_env_necesita_las_tres_variables(monkeypatch):
    monkeypatch.setenv("ORGANIZADOR_API_KEY", CLAVE)
    monkeypatch.setenv("ORGANIZADOR_IA_URL", "https://ejemplo.invalid/v1/chat")
    monkeypatch.delenv("ORGANIZADOR_IA_MODELO", raising=False)

    assert isinstance(ProveedorIA.desde_env(), ProveedorHeuristico)


def test_heuristico_sugiere_y_explica_con_reglas_propias():
    proveedor = ProveedorHeuristico()

    sugerencias = proveedor.sugerir(["trabajosql.pdf", "desconocido.pdf"], REGLAS)
    assert sugerencias[0].asignatura == "BaseDeDatos"
    assert sugerencias[0].tema == "SQL"
    assert sugerencias[0].fuente == "heuristica"
    assert sugerencias[1].asignatura == ""

    explicacion = proveedor.explicar("trabajosql.pdf", "BaseDeDatos/SQL", REGLAS)
    assert "sql" in explicacion.texto
    assert explicacion.fuente == "heuristica"


def test_api_sugiere_con_respuesta_valida():
    contenido = {
        "sugerencias": [
            {
                "nombre": "trabajosql.pdf",
                "asignatura": "BaseDeDatos",
                "tema": "SQL",
                "confianza": 0.93,
                "razon": "por el alias sql",
            }
        ]
    }
    abrir, vistas = _abrir_falso(_respuesta_ia(contenido))
    proveedor = ProveedorApi(
        CLAVE, "https://ejemplo.invalid/v1/chat", "modelo-de-prueba", abrir=abrir
    )

    sugerencias = proveedor.sugerir(["trabajosql.pdf"], REGLAS)
    assert len(sugerencias) == 1
    assert sugerencias[0].asignatura == "BaseDeDatos"
    assert sugerencias[0].tema == "SQL"
    assert sugerencias[0].fuente == "ia"
    assert vistas[0][1] == ProveedorApi.TIEMPO_ESPERA


def test_api_descarta_asignatura_inventada_y_cae_al_fallback():
    contenido = {
        "sugerencias": [
            {
                "nombre": "trabajosql.pdf",
                "asignatura": "AsignaturaInventada",
                "tema": "SQL",
                "confianza": 1,
                "razon": "inventada",
            }
        ]
    }
    abrir, _ = _abrir_falso(_respuesta_ia(contenido))
    proveedor = ProveedorApi(
        CLAVE, "https://ejemplo.invalid/v1/chat", "modelo-de-prueba", abrir=abrir
    )

    sugerencia = proveedor.sugerir(["trabajosql.pdf"], REGLAS)[0]
    assert sugerencia.asignatura == "BaseDeDatos"
    assert sugerencia.fuente == "heuristica"


def test_api_con_json_basura_lanza_ia_indisponible():
    abrir, _ = _abrir_falso(_respuesta_ia("esto no es json"))
    proveedor = ProveedorApi(
        CLAVE, "https://ejemplo.invalid/v1/chat", "modelo-de-prueba", abrir=abrir
    )

    with pytest.raises(IAIndisponible, match="JSON"):
        proveedor.sugerir(["trabajosql.pdf"], REGLAS)


def test_api_sin_red_lanza_ia_indisponible():
    def abrir(solicitud, timeout=None):
        raise urllib.error.URLError("sin red")

    proveedor = ProveedorApi(
        CLAVE, "https://ejemplo.invalid/v1/chat", "modelo-de-prueba", abrir=abrir
    )
    with pytest.raises(IAIndisponible, match="contactar"):
        proveedor.explicar("trabajosql.pdf", "BaseDeDatos/SQL", REGLAS)


def test_api_explica_con_respuesta_valida():
    abrir, _ = _abrir_falso(_respuesta_ia({"texto": "Por el alias sql en el nombre."}))
    proveedor = ProveedorApi(
        CLAVE, "https://ejemplo.invalid/v1/chat", "modelo-de-prueba", abrir=abrir
    )

    explicacion = proveedor.explicar("trabajosql.pdf", "BaseDeDatos/SQL", REGLAS)
    assert explicacion.texto == "Por el alias sql en el nombre."
    assert explicacion.fuente == "ia"
    assert "sql" in explicacion.razon_local
