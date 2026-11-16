"""Salida JSON para consumo por scripts.

Dos funciones: `emitir_json` para el resultado normal de una accion y
`error_json` para los errores previsibles, de modo que un script que pide
`--json` nunca reciba texto plano donde espera JSON.
"""

import json
import sys


def emitir_json(datos):
    """Escribe `datos` como JSON a stdout (una sola linea legible)."""
    json.dump(datos, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


def error_json(error):
    """Emite un error previsible como objeto JSON valido (`ok: false`)."""
    emitir_json(
        {
            "ok": False,
            "error": type(error).__name__,
            "mensaje": str(error),
        }
    )
