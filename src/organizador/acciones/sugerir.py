"""Accion `sugerir`: propone destinos para los archivos de `_revision`.

Por defecto solo propone: no mueve nada. `--aplicar` exige `--confirmar`,
así que el usuario ve primero el plan y debe escribir 's' antes de que se
toque ningún archivo. Si la IA no está disponible, la accion avisa y usa las
reglas locales; el resto de comandos no depende de la IA.
"""

from pathlib import Path

from ..excepciones import ErrorDeUso, IAIndisponible
from ..organizador import mover_archivo
from ..proveedor import ProveedorHeuristico, ProveedorIA
from ..reglas import REVISION
from .base import Accion


class AccionSugerir(Accion):
    """Muestra sugerencias de IA (o de reglas) para la carpeta de revision."""

    nombre = "sugerir"

    def __init__(
        self,
        consola,
        salida,
        reglas,
        proveedor,
        registro,
        aplicar=False,
        confirmar=False,
    ):
        super().__init__(consola)
        self.salida = salida
        self.reglas = reglas
        self.proveedor = proveedor
        self.registro = registro
        self.aplicar = aplicar
        self.confirmar = confirmar

    @classmethod
    def desde_config(cls, args, consola):
        from ..registro import Registro
        from ..reglas import reglas_efectivas

        if getattr(args, "aplicar", False) and not getattr(args, "confirmar", False):
            raise ErrorDeUso(
                "--aplicar requiere --confirmar: primero verás el plan y "
                "deberás confirmarlo antes de mover archivos."
            )
        return cls(
            consola=consola,
            salida=Path(args.salida).resolve(),
            reglas=reglas_efectivas(args.reglas),
            proveedor=ProveedorIA.desde_env(),
            registro=Registro.desde_config(args),
            aplicar=getattr(args, "aplicar", False),
            confirmar=getattr(args, "confirmar", False),
        )

    def ejecutar(self):
        carpeta = self.salida / REVISION
        if not carpeta.is_dir():
            return self._sin_carpeta(carpeta)

        archivos = sorted(p for p in carpeta.iterdir() if p.is_file())
        if not archivos:
            return self._vacio(carpeta)

        sugerencias = self._pedir_sugerencias([archivo.name for archivo in archivos])
        aplicados, errores = self._aplicar(archivos, sugerencias)
        return self._mostrar(carpeta, sugerencias, aplicados, errores)

    # --- proveedor ---------------------------------------------------------

    def _pedir_sugerencias(self, nombres):
        if not getattr(self.proveedor, "disponible", False):
            self.consola.aviso(
                "IA no configurada; se usan las reglas locales. Define "
                "ORGANIZADOR_API_KEY, ORGANIZADOR_IA_URL y "
                "ORGANIZADOR_IA_MODELO para activarla."
            )
        try:
            return list(self.proveedor.sugerir(nombres, self.reglas))
        except IAIndisponible as error:
            self.consola.aviso(
                "IA no disponible ({}); se usan las reglas locales.".format(error)
            )
            return list(ProveedorHeuristico().sugerir(nombres, self.reglas))

    # --- aplicacion opcional -----------------------------------------------

    def _aplicar(self, archivos, sugerencias):
        if not self.aplicar:
            return [], []

        candidatos = [
            (archivo, sugerencia)
            for archivo, sugerencia in zip(archivos, sugerencias)
            if sugerencia.asignatura and sugerencia.asignatura != REVISION
        ]
        if not candidatos:
            self.consola.linea("No hay propuestas aplicables; no se ha movido nada.")
            return [], []
        if not self.consola.confirmar(len(candidatos)):
            self.consola.cancelar("Cancelado; no se ha movido nada.")
            return [], []

        aplicados = []
        errores = []
        for archivo, sugerencia in candidatos:
            destino_dir = self.salida / sugerencia.asignatura
            if sugerencia.tema:
                destino_dir = destino_dir / sugerencia.tema
            try:
                destino = mover_archivo(archivo, destino_dir)
            except OSError as error:
                errores.append({"nombre": archivo.name, "error": str(error)})
                continue
            aplicados.append(
                {
                    "nombre": archivo.name,
                    "asignatura": sugerencia.asignatura,
                    "tema": sugerencia.tema,
                    "destino": str(destino),
                }
            )

        if aplicados:
            self._guardar_log(aplicados)
        return aplicados, errores

    def _guardar_log(self, aplicados):
        resumen = {"movimientos": aplicados, "errores": []}
        try:
            self.registro.guardar_historial(
                self.salida / REVISION, self.salida, resumen
            )
        except OSError as error:
            self.consola.aviso("Aviso: no se pudo escribir el log: {}".format(error))

    # --- presentacion ------------------------------------------------------

    @staticmethod
    def _destino(sugerencia):
        if not sugerencia.asignatura:
            return REVISION
        if sugerencia.tema:
            return "{}/{}".format(sugerencia.asignatura, sugerencia.tema)
        return sugerencia.asignatura

    def _sin_carpeta(self, carpeta):
        if self.consola.json_mode:
            return self._emitir(carpeta, [], [], [])
        self.consola.linea("No existe la carpeta de revisión: {}".format(carpeta))
        return 0

    def _vacio(self, carpeta):
        if self.consola.json_mode:
            return self._emitir(carpeta, [], [], [])
        self.consola.linea("No hay archivos pendientes en {}".format(carpeta))
        return 0

    def _mostrar(self, carpeta, sugerencias, aplicados, errores):
        if self.consola.json_mode:
            return self._emitir(carpeta, sugerencias, aplicados, errores)

        self.consola.linea(
            "{:<28} {:<16} {:<14} {:>6}  {}".format(
                "ARCHIVO", "ASIGNATURA", "TEMA", "CONF.", "FUENTE"
            )
        )
        for sugerencia in sugerencias:
            self.consola.linea(
                "{:<28} {:<16} {:<14} {:>5.0%}  {}".format(
                    sugerencia.nombre[:28],
                    sugerencia.asignatura[:16],
                    sugerencia.tema[:14],
                    sugerencia.confianza,
                    sugerencia.fuente,
                )
            )
        self.consola.errores({"errores": errores})
        self.consola.resumen(
            [
                ("Archivos propuestos", len(sugerencias)),
                ("Aplicados", len(aplicados)),
                ("Errores", len(errores)),
                ("Carpeta", carpeta),
            ]
        )
        if not self.aplicar:
            self.consola.linea("Solo propuestas: no se ha movido ningún archivo.")
        return 0

    def _emitir(self, carpeta, sugerencias, aplicados, errores):
        from ..presentacion import emitir_json

        aplicados_por_nombre = {item["nombre"] for item in aplicados}
        propuestas = []
        for sugerencia in sugerencias:
            datos = sugerencia.a_dict()
            datos["destino"] = self._destino(sugerencia)
            datos["aplicado"] = sugerencia.nombre in aplicados_por_nombre
            propuestas.append(datos)
        emitir_json(
            {
                "ok": True,
                "accion": self.nombre,
                "carpeta": str(carpeta),
                "propuestas": propuestas,
                "aplicados": aplicados,
                "errores": errores,
                "total": len(propuestas),
            }
        )
        return 0
