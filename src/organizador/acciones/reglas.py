"""Accion `reglas`: muestra asignaturas y temas disponibles."""

from ..reglas import ruta_reglas_usuario
from .base import Accion


class AccionReglas(Accion):
    """Lista las reglas efectivas (usuario + paquete, o las de `--reglas`)."""

    nombre = "reglas"

    def __init__(self, consola, reglas):
        super().__init__(consola)
        self.reglas = reglas

    @classmethod
    def desde_config(cls, args, consola):
        from ..reglas import reglas_efectivas

        return cls(consola, reglas_efectivas(args.reglas))

    def ejecutar(self):
        usuario = ruta_reglas_usuario()
        if usuario.is_file():
            self.consola.linea("Reglas del usuario: {}".format(usuario))
        for regla in self.reglas:
            self.consola.linea(regla.asignatura)
            for tema, _ in regla.temas:
                self.consola.linea("  - {}".format(tema))
        return 0
