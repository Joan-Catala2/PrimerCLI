"""Accion `ejecutar`: organiza una carpeta de origen por asignatura y tema.

La accion orquesta motor (organizar), registro (logs) y consola (salida).
La fecha de `--desde` se valida en la fabrica: el parser solo acepta texto;
quien sabe de formatos es esta capa, que puede explicar el error en humano.
"""

from pathlib import Path

from ..excepciones import ErrorDeUso
from ..organizador import organizar
from .base import Accion
from .util import extensiones_de, parsear_fecha


class AccionEjecutar(Accion):
    nombre = "ejecutar"

    def __init__(
        self,
        consola,
        origen,
        salida,
        reglas,
        registro,
        opciones,
        simular=False,
        confirmar=False,
        seco=False,
        log=None,
    ):
        super().__init__(consola)
        self.origen = origen
        self.salida = salida
        self.reglas = reglas
        self.registro = registro
        self.opciones = opciones
        self.simular = simular
        self.confirmar = confirmar
        self.seco = seco
        self.log = log

    @classmethod
    def desde_config(cls, args, consola):
        from ..registro import Registro
        from ..reglas import reglas_efectivas

        reglas = reglas_efectivas(args.reglas)
        opciones = {
            "reglas": reglas,
            "recursivo": args.recursivo,
            "extensiones": extensiones_de(args.extension),
            "excluir": args.excluir,
            "desde": parsear_fecha(args.desde),
            "ignorar": [Path(args.logs_dir).resolve()],
        }
        if getattr(args, "contenido", False):
            from ..contenido import texto_documento

            max_paginas = args.contenido_max_paginas
            if max_paginas < 1:
                raise ErrorDeUso("--contenido-max-paginas debe ser 1 o mas.")

            def extraer(ruta):
                return texto_documento(ruta, max_paginas)

            opciones["extractor"] = extraer
        return cls(
            consola=consola,
            origen=Path(args.origen).resolve(),
            salida=Path(args.salida).resolve(),
            reglas=reglas,
            registro=Registro.desde_config(args),
            opciones=opciones,
            simular=args.simular,
            confirmar=args.confirmar,
            seco=args.seco,
            log=args.log,
        )

    def ejecutar(self):
        simulado = self.simular or self.confirmar
        resumen = organizar(self.origen, self.salida, simular=simulado, **self.opciones)

        cancelado = False
        if self.confirmar and not self.simular:
            if resumen["movimientos"]:
                if not self.consola.json_mode and not self.seco:
                    self.consola.movimientos(resumen, self.salida, "[SIM]")
                if self.consola.confirmar(len(resumen["movimientos"])):
                    resumen = organizar(
                        self.origen, self.salida, simular=False, **self.opciones
                    )
                    simulado = False
                else:
                    cancelado = True
                    simulado = True
            else:
                # Nada que confirmar: la pasada real (vaciar origen y no
                # mover) es lo que se ejecuta ya.
                simulado = False

        ruta_log = self._guardar_si_procede(resumen, simulado)
        return self._mostrar(resumen, simulado, cancelado, ruta_log)

    # --- partes de ejecutar ---------------------------------------------

    def _guardar_si_procede(self, resumen, simulado):
        """Escribe el log solo si hubo movimientos o errores reales.

        Los avisos de lectura (documentos cifrados o ilegibles) no lo justifican:
        no hubo efectos que deshacer.
        """
        if simulado or not (resumen["movimientos"] or resumen["errores"]):
            return None
        ruta_log = None
        aviso = self.consola.aviso
        if self.log is not None:
            ruta_log = self.registro.ruta_unica(
                self.log, self.origen, self.salida, aviso
            )
            self.registro.avisar_sobrescritura(ruta_log, aviso)
        try:
            if ruta_log is not None:
                self.registro.guardar(self.origen, self.salida, resumen, ruta_log)
            else:
                ruta_log = self.registro.guardar_historial(
                    self.origen, self.salida, resumen
                )
        except OSError as error:
            aviso("Aviso: no se pudo escribir el log: {}".format(error))
        return ruta_log

    def _mostrar(self, resumen, simulado, cancelado, ruta_log):
        total = len(resumen["organizados"]) + len(resumen["revision"])
        consola = self.consola

        if consola.json_mode:
            self._mostrar_json(resumen, total, simulado, cancelado, ruta_log)
            return 0

        if cancelado:
            consola.linea("Cancelado; no se ha movido nada.")
            return 0

        if not self.seco:
            consola.movimientos(resumen, self.salida, "[SIM]" if simulado else "[OK]")
        consola.errores(resumen)
        for aviso in resumen["avisos"]:
            consola.aviso(aviso)

        lineas = [
            ("Archivos procesados", total),
            ("Organizados", len(resumen["organizados"])),
            ("A revisar", len(resumen["revision"])),
            ("Errores", len(resumen["errores"])),
            ("Filtrados", resumen["filtrados"]),
            ("Destino", self.salida),
        ]
        if ruta_log is not None:
            lineas.append(("Log", ruta_log))
        if simulado:
            lineas.append(("Modo", "simulación (no se ha movido nada)"))
        consola.resumen(lineas)
        return 0

    def _mostrar_json(self, resumen, total, simulado, cancelado, ruta_log):
        from ..presentacion import emitir_json

        emitir_json(
            {
                "origen": str(self.origen),
                "salida": str(self.salida),
                "simulado": simulado,
                "cancelado": cancelado,
                "movimientos": resumen["movimientos"],
                "organizados": [
                    {"nombre": nombre, "asignatura": asignatura, "tema": tema}
                    for nombre, asignatura, tema in resumen["organizados"]
                ],
                "revision": resumen["revision"],
                "errores": resumen["errores"],
                "avisos": resumen["avisos"],
                "filtrados": resumen["filtrados"],
                "total": total,
                "log": str(ruta_log) if ruta_log is not None else None,
            }
        )
        if cancelado:
            self.consola.cancelar("Cancelado; no se ha movido nada.")
