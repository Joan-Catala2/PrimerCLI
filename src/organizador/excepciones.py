"""Jerarquía de errores de la CLI `organizador`.

Todos los errores previsibles derivan de `OrganizadorError` y llevan un
mensaje en lenguaje humano. `main` los captura y los imprime sin traceback;
un traceback en pantalla solo debe verse ante bugs reales.

Cada error lleva `codigo_salida` para que la CLI devuelva siempre un código
de salida coherente con la naturaleza del fallo.
"""


class OrganizadorError(Exception):
    """Error previsible de la CLI. Nunca debe salir como traceback."""

    codigo_salida = 1


class ConfigError(OrganizadorError):
    """Reglas o logs con formato, contenido o ruta incorrectos."""


class AccionNoValida(OrganizadorError):
    """Se ha pedido una acción que la CLI no conoce."""

    codigo_salida = 2


class ErrorDeUso(AccionNoValida):
    """Combinación de opciones imposible (fecha mal, --ultimos 0, ...)."""


class CarpetaNoValidaError(OrganizadorError):
    """El origen no existe, no es una carpeta o la salida cae dentro de él."""


class ErrorDeArchivo(OrganizadorError):
    """Un archivo o carpeta no está donde el log decía, o no se puede leer."""


class ErrorDeSistema(OrganizadorError):
    """Fallo del sistema operativo no atribuible a un solo archivo."""


class IAIndisponible(OrganizadorError):
    """El proveedor de IA no responde o devuelve un formato inesperado.

    Las acciones de IA capturan este error y siguen con las reglas locales:
    la falta de red o de configuración nunca rompe el comando.
    """


def afirmar(condicion, mensaje):
    """Aserción de *desarrollo* que sobrevive a `python -O`.

    Distingue dos cosas que un `assert` normal no distingue:

    - **Invariante de desarrollo**: si falla, hay un bug en el motor. El
      `assert` de Python basta, pero desaparece con `python -O` y dejaría
      pasar el estado roto en silencio.
    - **Condición que debe seguir violando en producción**: aquí `afirmar`
      lanza siempre `OrganizadorError` con mensaje humano, de modo que la
      CLI la muestra igual que el resto de errores previsibles.

    Usar `afirmar` en el motor obliga a decidir, para cada invariante, qué
    significa que se incumpla; el `assert` a secas solo vale para
    comprobaciones que de verdad pueden eliminarse con `-O`.
    """
    if not condicion:
        raise OrganizadorError("Error interno: {}".format(mensaje))
