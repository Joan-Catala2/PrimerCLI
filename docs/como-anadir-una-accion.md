# Cómo añadir una acción (sin tocar el núcleo)

El contrato está en `src/organizador/acciones/base.py` y su justificación en
`docs/adr/002-una-accion-una-clase.md`: **una acción = una clase con fábrica**,
registrada en un diccionario. El motor (`organizador.py`), la presentación
(`presentacion/`) y las excepciones no se tocan nunca al añadir un comando.
Anadir `aplicar`, `verificar` o `--contenido` lo demostró: ninguna de esas
fases modificó el contrato.

Añadir una acción son **tres pasos mecánicos** (uno es un solo `import`):

## Paso 1 — La clase (`src/organizador/acciones/mi_accion.py`)

Hereda de `Accion` e implementa los dos métodos abstractos. El ejemplo
mínimo completo (cuenta palabras del nombre; sirve tal cual de plantilla):

```python
"""Accion `palabras`: cuenta las palabras de un nombre de archivo."""

from pathlib import Path

from .base import Accion


class AccionPalabras(Accion):
    nombre = "palabras"

    def __init__(self, consola, nombres):
        super().__init__(consola)
        self.nombres = nombres

    @classmethod
    def desde_config(cls, args, consola):
        # Aqui van las decisiones de configuracion: validar, resolver
        # dependencias (reglas_efectivas, Registro.desde_config, ...) y
        # rechazar lo imposible con ErrorDeUso/ConfigError. Todo error que
        # salga de aqui se muestra como mensaje humano, sin traceback, y
        # NO se ha tocado el disco todavia.
        nombres = getattr(args, "nombre", []) or []
        return cls(consola=consola, nombres=nombres)

    def ejecutar(self):
        # Devuelve SIEMPRE el codigo de salida: 0 bien, 1 fallo previsible,
        # 2 error de uso (ver excepciones.py, `codigo_salida`).
        for nombre in self.nombres:
            self.consola.linea(
                "{}: {} palabras".format(
                    nombre, len(Path(nombre).stem.replace("_", " ").split())
                )
            )
        return 0
```

Reglas del contrato:

- `desde_config` **valida antes de ejecutar**: fecha mal, banderas
  incompatibles o reglas corruptas deben morir aquí (patrón probado en
  `tests/test_acciones.py::test_fecha_invalida_falla_antes_de_tocar_el_disco`).
- `ejecutar` **no imprime directamente**: usa `self.consola` (`linea`,
  `resumen`, `aviso`, `emitir_json` via `presentacion`). Así el `--json`
  funciona gratis.
- Sin efectos sorpresa: si la acción borra, sobrescribe o mueve, ofrece
  `--simular` y `--confirmar` (míralos en `ejecutar.py` y `verificar.py`) y
  deja `deshacer` (log en `registro.py`).
- Errores previsibles: lanza los de `excepciones.py`, nunca `ValueError`
  pelado. Los invariantes internos se comprueban con `afirmar()`.

## Paso 2 — El registro (`src/organizador/acciones/__init__.py`)

Una línea en el diccionario `_IMPLEMENTACIONES` (y su `import` arriba):

```python
from .palabras import AccionPalabras
# ...
_IMPLEMENTACIONES = { ..., "palabras": AccionPalabras }
```

## Paso 3 — El parser (`src/organizador/cli.py`)

Un bloque en `_construir_parser()`, solo estructura (sin lógica de negocio,
igual que los existentes):

```python
palabras = sub.add_parser("palabras", help="cuenta palabras de un nombre")
palabras.add_argument("nombre", nargs="+", help="nombres a contar")
```

## Los candados (esto no es opcional, y es gratis)

La suite fuerza el registro correcto: si tu acción no está en la fábrica o
no está documentada, los tests existentes revientan solos.

| Candado | Qué exige de tu acción |
|---|---|
| `tests/test_acciones.py::test_desde_config_devuelve_la_accion_de_cada_nombre` | está en `_IMPLEMENTACIONES` (el test recorre el diccionario, no una lista fija) y construye con los `_args` de prueba: si tu acción lee flags nuevos, añade sus defaults a `_args` |
| `tests/test_docs_readme.py` (parametrizado sobre `COMANDOS`) | el README la documenta: bloque de uso `organizador palabras ...`, entrada `- \`palabras\`: ...`, y ninguna bandera fantasma. **Al ser una tupla fija en el test, tienes que añadir tu comando a `COMANDOS`** (y al revés: un comando en `COMANDOS` sin clase o sin README rompe la suite) |
| `tests/test_cli_end_to_end.py::test_cli_instalado_anuncia_los_ocho_comandos` | el `--help` real la lista; actualiza la lista del test (y el número del nombre si te da por renombrarlo) |

Además, para tu acción: un `tests/test_acciones_palabras.py` con el camino
feliz y sus casos feos (lista vacía, nombre raro, unicode), y la entrada en
`docs/CHANGELOG.md`.

## Checklist final

1. [ ] Clase en `acciones/mi_accion.py` (`desde_config` valida, `ejecutar`
       devuelve código).
2. [ ] Línea en `_IMPLEMENTACIONES`.
3. [ ] Subparser en `cli.py` (flags con defaults que `_args` iguale).
4. [ ] README: bloque de uso + lista + ejemplo (el candado lo vigila).
5. [ ] Prueba propia (feliz + feos) y actualización del candado de `--help`.
6. [ ] `CHANGELOG.md` y, si decide algo de diseño, un ADR nuevo.

Si el criterio del curso dice "anadir una acción no exige tocar el código",
esta guía es la respuesta: se **añade**, no se **modifica** el núcleo. Los
únicos toques fuera de tu fichero son un `import`, una línea de diccionario
y un subparser declarativo — exactamente la extensión prevista por el ADR-002.
