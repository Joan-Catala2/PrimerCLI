"""Accion `explicar`: justifica por qué un nombre acaba en un destino.

Combina la prueba documental de `reglas.json` (alias y tipo de coincidencia)
con una frase del proveedor de IA si está disponible. Si la IA falla, se
muestra igualmente la explicación local y se avisa por stderr.

Con `--contenido` (ADR-006/007), si el nombre es un PDF o DOCX sin
coincidencia en las reglas, se intenta explicar (y mostrar) la clasificacion
por el texto del documento: `Fuente: contenido`.
"""

from pathlib import Path

from ..excepciones import ErrorDeUso, IAIndisponible
from ..proveedor import Explicacion, ProveedorIA
from ..reglas import REVISION, explicar_match
from .base import Accion
from .util import ruta_de


class AccionExplicar(Accion):
    """Explica una clasificación concreta sin mover archivos."""

    nombre = "explicar"

    def __init__(self, consola, archivo, salida, reglas, proveedor, extractor=None):
        super().__init__(consola)
        self.archivo = archivo
        self.salida = salida
        self.reglas = reglas
        self.proveedor = proveedor
        self.extractor = extractor

    @classmethod
    def desde_config(cls, args, consola):
        from ..reglas import reglas_efectivas

        nombre = getattr(args, "nombre", "")
        if not nombre:
            raise ErrorDeUso("explicar necesita un nombre de archivo.")
        extractor = None
        if getattr(args, "contenido", False):
            from ..contenido import texto_documento

            max_paginas = args.contenido_max_paginas
            if max_paginas < 1:
                raise ErrorDeUso("--contenido-max-paginas debe ser 1 o mas.")
            ruta_documento = Path(nombre)

            def extraer():
                return texto_documento(ruta_documento, max_paginas)

            extractor = extraer
        return cls(
            consola=consola,
            archivo=Path(nombre).name,
            salida=ruta_de(args.salida, "--salida"),
            reglas=reglas_efectivas(args.reglas),
            proveedor=ProveedorIA.desde_env(),
            extractor=extractor,
        )

    def _coincidencia_por_contenido(self, nombre):
        """Explicacion por texto del documento: `--contenido` con un nombre
        que no clasifica. Sin extractor, sin extension leible o con lectura
        fallida, None (el aviso corre a cargo del extractor; aqui no se
        interrumpe nada).
        """
        from ..contenido import ExtraccionFallida, clasificar_por_contenido, es_lexible

        if self.extractor is None or not es_lexible(nombre):
            return None

        try:
            texto = self.extractor()
        except (ExtraccionFallida, OSError):
            return None
        _, detalle = clasificar_por_contenido(texto, self.reglas)
        return detalle

    def ejecutar(self):
        nombre = Path(self.archivo).name
        coincidencia = explicar_match(nombre, self.reglas)
        if coincidencia is None:
            coincidencia = self._coincidencia_por_contenido(nombre)
        asignatura = coincidencia["asignatura"] if coincidencia else ""
        tema = coincidencia["tema"] if coincidencia else ""
        razon_local = (
            coincidencia["razon"]
            if coincidencia
            else (
                "Ningún alias de las reglas coincide con '{}'; por eso acabaría "
                "en _revision.".format(nombre)
            )
        )
        destino = "{}/{}".format(asignatura, tema) if tema else asignatura
        destino = destino or REVISION

        if coincidencia is not None and coincidencia.get("origen") == "contenido":
            explicacion = Explicacion(
                texto=coincidencia["razon"],
                fuente="contenido",
                razon_local=coincidencia["razon"],
            )
            return self._mostrar(nombre, destino, explicacion)

        try:
            explicacion = self.proveedor.explicar(nombre, destino, self.reglas)
        except IAIndisponible as error:
            self.consola.aviso(
                "IA no disponible ({}); se usa la explicación de las reglas.".format(
                    error
                )
            )
            explicacion = Explicacion(
                texto=razon_local, fuente="reglas", razon_local=razon_local
            )
        else:
            explicacion = Explicacion(
                texto=explicacion.texto,
                fuente=explicacion.fuente,
                razon_local=razon_local,
            )

        return self._mostrar(nombre, destino, explicacion)

    def _mostrar(self, nombre, destino, explicacion):
        if self.consola.json_mode:
            from ..presentacion import emitir_json

            emitir_json(
                {
                    "ok": True,
                    "accion": self.nombre,
                    "nombre": nombre,
                    "destino": destino,
                    "texto": explicacion.texto,
                    "fuente": explicacion.fuente,
                    "razon_local": explicacion.razon_local,
                }
            )
            return 0

        self.consola.linea("Archivo: {}".format(nombre))
        self.consola.linea("Destino: {}".format(destino))
        self.consola.linea("Razón: {}".format(explicacion.texto))
        self.consola.linea("Fuente: {}".format(explicacion.fuente))
        return 0
