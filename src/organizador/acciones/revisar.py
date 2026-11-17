"""Accion `revisar`: lista y (opcionalmente) recoloca _revision.

La parte interactiva sigue el mismo guion que en la v2.2: Enter acepta la
sugerencia, `-` quita el tema, `q` termina y un EOF deja el resto en
revision sin perder nada. El codigo 130 (cancelado por el usuario) se
conserva por compatibilidad.
"""

from ..organizador import limpiar_vacias, mover_archivo
from ..reglas import REVISION, clasificar
from .base import Accion


def mapa_temas(reglas):
    """Devuelve {asignatura: [temas]} a partir de las reglas efectivas."""
    temas: dict = {}
    for regla in reglas or ():
        lista = temas.setdefault(regla.asignatura, [])
        for tema, _ in regla.temas:
            if tema not in lista:
                lista.append(tema)
    return temas


class _Salir(Exception):
    """El usuario ha pulsado 'q': se termina la sesion de revision."""


class _SinCambio(Exception):
    """El usuario ha saltado este archivo (Enter o asignatura invalida)."""


class AccionRevisar(Accion):
    nombre = "revisar"

    def __init__(self, consola, salida, reglas, interactivo=False):
        super().__init__(consola)
        self.salida = salida
        self.reglas = reglas
        self.interactivo = interactivo

    @classmethod
    def desde_config(cls, args, consola):
        from pathlib import Path

        from ..reglas import reglas_efectivas

        return cls(
            consola=consola,
            salida=Path(args.salida).resolve(),
            reglas=reglas_efectivas(args.reglas),
            interactivo=args.interactivo,
        )

    def ejecutar(self):
        carpeta = self.salida / REVISION
        if not carpeta.is_dir():
            return self._sin_carpeta(carpeta)

        archivos = sorted(p for p in carpeta.iterdir() if p.is_file())
        if not self.interactivo:
            return self._listar(carpeta, archivos)
        return self._interactivo(carpeta, archivos)

    # --- sin carpeta / listado -------------------------------------------

    def _sin_carpeta(self, carpeta):
        if self.consola.json_mode:
            self._emitir(
                carpeta,
                existe=False,
                archivos=[],
                total=0,
                movidos=[],
                pendientes=0,
                cancelado=False,
            )
            return 0
        self.consola.linea("No existe la carpeta de revisión: {}".format(carpeta))
        return 0

    def _listar(self, carpeta, archivos):
        if self.consola.json_mode:
            self._emitir(
                carpeta,
                existe=True,
                archivos=[archivo.name for archivo in archivos],
                total=len(archivos),
            )
            return 0
        for archivo in archivos:
            self.consola.linea(archivo.name)
        self.consola.linea()
        self.consola.linea("Archivos a revisar: {}".format(len(archivos)))
        return 0

    # --- interactivo -------------------------------------------------------

    def _interactivo(self, carpeta, archivos):
        consola = self.consola
        asignaturas = {regla.asignatura for regla in (self.reglas or ())}
        temas_por_asignatura = mapa_temas(self.reglas)
        consola.linea(
            "Asignaturas disponibles: {}".format(", ".join(sorted(asignaturas)))
        )

        movidos = []
        cancelado = False
        salir = False
        for numero, archivo in enumerate(archivos, start=1):
            consola.linea()
            consola.linea("[{}/{}] {}".format(numero, len(archivos), archivo.name))

            sugerencia = clasificar(archivo.name, self.reglas)
            sug_asignatura, sug_tema = sugerencia if sugerencia else ("", "")

            try:
                asignatura, tema = self._preguntar_destino(
                    asignaturas,
                    temas_por_asignatura,
                    sug_asignatura,
                    sug_tema,
                )
            except _SinCambio:
                continue
            except _Salir:
                salir = True
                break
            except EOFError:
                consola.linea()
                consola.linea("Entrada cancelada; se deja el resto en revisión.")
                cancelado = True
                break

            destino = mover_archivo(archivo, self._destino(asignatura, tema))
            movidos.append(
                {
                    "nombre": archivo.name,
                    "asignatura": asignatura,
                    "tema": tema,
                    "destino": str(destino),
                }
            )
            consola.linea("Movido a {}".format(destino.relative_to(self.salida)))

        if movidos:
            limpiar_vacias(self.salida)

        return self._cierre(carpeta, archivos, movidos, cancelado, salir)

    def _preguntar_destino(
        self, asignaturas, temas_por_asignatura, sug_asignatura, sug_tema
    ):
        """Una ronda de preguntas -> (asignatura, tema).

        Lanza `_Salir` si el usuario escribe 'q' y `_SinCambio` si hay que
        saltarse el archivo. Excepciones locales del metodo: control de
        flujo sin flags de estado repartidos por la clase.
        """
        consola = self.consola

        if sug_asignatura:
            pregunta = "Asignatura [{}] (Enter para aceptar, q para salir): "
            pregunta = pregunta.format(sug_asignatura)
        else:
            pregunta = "Asignatura (Enter para saltar, q para salir): "
        respuesta = consola.preguntar(pregunta).strip()
        if respuesta.lower() == "q":
            raise _Salir

        asignatura = respuesta or sug_asignatura
        if not asignatura:
            raise _SinCambio

        if asignatura not in asignaturas:
            if not consola.respuesta_si(
                '¿Crear asignatura "{}"? [s/N]: '.format(asignatura),
            ):
                consola.linea("Asignatura no válida, se salta.")
                raise _SinCambio
            asignaturas.add(asignatura)
            temas_por_asignatura.setdefault(asignatura, [])

        temas = temas_por_asignatura.get(asignatura, [])
        if temas:
            consola.linea("Temas: {}".format(", ".join(temas)))

        tema_sugerido = sug_tema if asignatura == sug_asignatura else ""
        if tema_sugerido:
            pregunta_tema = "Tema [{}] (Enter para aceptar, '-' para ninguno): "
            pregunta_tema = pregunta_tema.format(tema_sugerido)
        else:
            pregunta_tema = "Tema (opcional, '-' para ninguno): "

        respuesta = consola.preguntar(pregunta_tema).strip()
        if respuesta.lower() == "q":
            raise _Salir
        if respuesta == "-":
            tema = ""
        else:
            tema = respuesta or tema_sugerido

        if tema and temas and tema not in temas:
            if consola.respuesta_si('¿Crear tema "{}"? [s/N]: '.format(tema)):
                temas.append(tema)
            else:
                consola.linea("Tema no válido, se usa sin tema.")
                tema = ""

        return asignatura, tema

    def _destino(self, asignatura, tema):
        destino_dir = self.salida / asignatura
        if tema:
            destino_dir = destino_dir / tema
        return destino_dir

    def _cierre(self, carpeta, archivos, movidos, cancelado, salir):
        if self.consola.json_mode:
            self._emitir(
                carpeta,
                existe=True,
                archivos=[archivo.name for archivo in archivos],
                total=len(archivos),
                movidos=movidos,
                pendientes=len(archivos) - len(movidos),
                cancelado=cancelado,
                salir=salir,
            )
            return 130 if cancelado else 0

        self.consola.linea()
        self.consola.linea("Archivos movidos: {}".format(len(movidos)))
        self.consola.linea("Pendientes:       {}".format(len(archivos) - len(movidos)))
        if salir:
            self.consola.linea("Sesión terminada; se deja el resto en revisión.")
        return 130 if cancelado else 0

    def _emitir(self, carpeta, **datos):
        from ..presentacion import emitir_json

        emitir_json(dict(salida=str(self.salida), carpeta=str(carpeta), **datos))
