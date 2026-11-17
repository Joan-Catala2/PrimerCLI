# ADR 001 — La clasificacion vive en un JSON externo, no en el codigo

- **Estado**: Aceptado
- **Fecha**: 2026-11-17
- **Contexto**: v1.0 (decisión retrospectiva documentada en el refactor de la v2.3)

## Contexto

El CLI clasifica archivos por asignatura y tema buscando palabras clave en
el nombre del archivo. En la v1 el conjunto de palabras vivia en
diccionarios de Python dentro de `organizador.py`: anadir una asignatura
significaba editar el codigo, entender el matching y reinstalar el paquete.
Los alumnos (usuarios finales) no pueden mantener su propio clasificador si
cada alias nuevo requiere tocar el motor.

## Decision

Las reglas de clasificacion viven en `reglas.json` con formato documentado
(`asignatura`, `aliases`, `temas[].aliases`). El codigo solo contiene el
*algoritmo* de matching; los *datos* son configuracion externa con tres
niveles:

1. `--reglas ruta.json` — solo ese fichero (para pruebas o juegos alternativos).
2. `~/.config/organizador/reglas.json` (o `$XDG_CONFIG_HOME`) — reglas del
   usuario, con prioridad sobre las del paquete y fusionadas con ellas.
3. `src/organizador/reglas.json` — juego por defecto del paquete.

El JSON se valida al cargar (`reglas.py`) y los errores salen como
`ConfigError` con mensaje humano (regla N de tal fichero: tal problema).

## Consecuencias

- Anadir o corregir una asignatura **no exige tocar codigo**: se edita el
  JSON y la siguiente ejecucion ya lo usa. El usuario nunca instala nada.
- El motor no conoce asignaturas concretas: se le pasa la tupla de `Regla`.
  Esto fue lo que permitio, en el refactor v2.3, separar motor/acciones sin
  tocar una linea de clasificacion.
- Costes: hay que validar el JSON (compensado: la validacion queda en un
  unico punto y es reutilizable por el ADR-002) y existe un error nuevo que
  explicar (`Regla 3 en ...: 'aliases' debe ser una lista no vacia`).
- La cache `lru_cache` de `cargar_reglas` asume que un fichero no cambia
  durante la vida del proceso; es deliberado (el JSON es inmutable durante
  una ejecucion) y esta documentado en el codigo.

## Alternativas descartadas

- **Código Python con un `plugins.py`**: daría más potencia, pero pide
  saber programar y reinstalar para cada alias nuevo: justo lo que se
  quería evitar.
- **TOML/YAML**: ventaja teorica de comentarios; el stdlib no los lee sin
  dependencias, y el JSON se mantiene editable con cualquier editor.
