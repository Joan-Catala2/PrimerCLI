"""Genera el `data.json` del escudo de cobertura desde `coverage.xml`.

Self-hosted: sin servicio externo. La accion del workflow sube el JSON a la
rama `badges`, y el README lo pinta con shields.io (modo endpoint).

Uso: `python scripts/badge.py coverage.xml data.json`.
"""

import json
import sys
import xml.etree.ElementTree as ET

UMBRAL = 85


def porcentaje(ruta):
    raiz = ET.parse(ruta).getroot()
    try:
        return float(raiz.get("line-rate")) * 100
    except (TypeError, ValueError) as error:
        raise SystemExit("coverage.xml sin 'line-rate' valido: {}".format(error))


def data(pct):
    return {
        "schemaVersion": 1,
        "label": "coverage",
        "message": "{:.0f}%".format(pct),
        "color": "brightgreen" if pct >= UMBRAL else "red",
    }


def main(argv):
    if len(argv) != 3:
        raise SystemExit("uso: badge.py coverage.xml data.json")
    pct = porcentaje(argv[1])
    with open(argv[2], "w", encoding="utf-8") as archivo:
        json.dump(data(pct), archivo, ensure_ascii=False)
        archivo.write("\n")
    print("cobertura {:.2f}% -> {}".format(pct, argv[2]))


if __name__ == "__main__":
    main(sys.argv)
