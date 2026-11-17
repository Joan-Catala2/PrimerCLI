"""Consola: la unica capa que imprime y pide datos al usuario.

Un modo (humano o JSON) decide donde va cada mensaje: en humano, el detalle
y los avisos van por stdout/stderr normal; en JSON, stdout esta reservado
para el documento, asi que preguntas y avisos viajan por stderr.

`movimientos` importa REVISION dentro del metodo (no arriba): presentar
filas y definir la marca "_revision" es responsabilidad de las reglas, y el
import local evita el ciclo presentacion -> reglas.
"""

import sys
from pathlib import Path


class Consola:
    def __init__(self, json_mode=False):
        self.json_mode = json_mode

    @classmethod
    def desde_config(cls, args):
        """Crea la consola a partir de la configuracion parseada.

        `getattr` porque no todos los subcomandos (p. ej. `reglas`)
        declaran `--json`; en ese caso el modo humano es el unico sentido.
        """
        return cls(json_mode=getattr(args, "json", False))

    def aviso(self, mensaje):
        """Mensaje en stderr; en modo JSON stdout debe quedar limpio."""
        print(mensaje, file=sys.stderr)

    def cancelar(self, mensaje):
        """Aviso de cancelacion; en humano va a stdout (es info normal)."""
        if self.json_mode:
            self.aviso(mensaje)
        else:
            print(mensaje)

    def preguntar(self, texto):
        """Pide un dato; en modo JSON el enunciado va a stderr."""
        if self.json_mode:
            print(texto, end="", file=sys.stderr, flush=True)
            return input()
        return input(texto)

    def confirmar(self, total):
        """Pide confirmacion; un EOFError se interpreta como 'no'."""
        texto = "¿Mover {} archivos? [s/N]: ".format(total)
        try:
            if self.json_mode:
                print(texto, end="", file=sys.stderr, flush=True)
                respuesta = input()
            else:
                respuesta = input(texto)
        except EOFError:
            if self.json_mode:
                print(file=sys.stderr)
            return False
        return respuesta.strip().lower() in {"s", "si", "sí", "y", "yes"}

    def respuesta_si(self, texto):
        """Pregunta de si/no. Un EOFError se propaga al llamador."""
        respuesta = self.preguntar(texto)
        return respuesta.strip().lower() in {"s", "si", "sí", "y", "yes"}

    def error_humano(self, error):
        """Error previsible como mensaje humano, sin traceback."""
        print("Error: {}".format(error), file=sys.stderr)

    # --- Presentacion de resumenes -------------------------------------

    def movimientos(self, resumen, salida, etiqueta="[OK]"):
        """Muestra el detalle de los movimientos de un resumen.

        `resumen` es el dict de `organizador.organizar`; las filas de
        `_revision` se marcan con [?] en vez de con la etiqueta normal.
        """
        from organizador.reglas import REVISION

        for movimiento in resumen["movimientos"]:
            relativo = Path(movimiento["destino"]).relative_to(salida)
            marca = "[?]" if movimiento["asignatura"] == REVISION else etiqueta
            self.linea("{} {} -> {}".format(marca, movimiento["nombre"], relativo))

    def deshechos(self, resumen):
        """Muestra los archivos devueltos por un deshacer."""
        for movimiento in resumen["deshechos"]:
            self.linea(
                "[UNDO] {} -> {}".format(movimiento["nombre"], movimiento["destino"])
            )
        for fallo in resumen["errores"]:
            self.aviso("[!] {} -> {}".format(fallo["nombre"], fallo["error"]))

    def resumen(self, lineas):
        """Cabecera 'Resumen' + pares (clave, valor) alineados (humano).

        En modo JSON stdout esta reservado al documento: no se pinta nada.
        """
        if self.json_mode:
            return
        print()
        print("Resumen")
        for clave, valor in lineas:
            # Las claves de 20+ caracteres (p.ej. "Archivos procesados:")
            # quedan pegadas al valor: era el mismo alineado en la v2.2.
            print("  {:<20}{}".format(clave + ":", valor))

    def linea(self, mensaje=""):
        """Mensaje humano directo a stdout (cabeceras, avisos de sesion).

        Silencioso en modo JSON: el documento ya lleva esa informacion.
        """
        if not self.json_mode:
            print(mensaje)

    def errores(self, resumen):
        """Vaca los errores de un resumen por stderr."""
        for fallo in resumen["errores"]:
            self.aviso("[!] {} -> {}".format(fallo["nombre"], fallo["error"]))
