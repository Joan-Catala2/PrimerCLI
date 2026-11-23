# ADR 005 — `verificar`: auditoria de `Organizado/` y poda reversible

- **Estado**: Aceptado
- **Fecha**: 2026-11-23
- **Contexto**: Fase 7B (post-release)

## Contexto

Con ocho comandos, la CLI organiza, aprende y deshace, pero nadie responde
a "esta carpeta esta bien?". El usuario acumula descargas duplicadas (el
navegador guarda `doc (1).pdf`), carpetas vacias tras un `deshacer`,
nombres fuera de catalogo creados a mano y archivos en la raiz de una
asignatura cuando las reglas los pondrian en un tema. `deshacer` solo
reconoce movimientos propios: un estado degradado no tiene camino de
 vuelta.

## Decision

Octavo comando, `verificar`, una clase con fabrica (ADR-002). Solo lectura
por defecto, con cinco detectores independientes:

1. **Duplicados** por SHA-256 (no tamano+mtime: un `cp` cambia fechas).
2. **Subproductos del navegador** (`doc (1).pdf` junto a `doc.pdf`): se
   informan aunque el contenido difiera; `--podar` NO los toca.
3. **Carpetas vacias** bajo la salida.
4. **Fuera de catalogo**: subcarpetas de primer nivel que no son
   asignatura ni `_revision`.
5. **Atrapados**: archivos en la raiz de una asignatura que `clasificar`
   pondria en un tema (la pasada de `ejecutar` no los bajo: existian antes
   de la regla o llegaron a mano).

El estado de `_revision` es informativo (contadores de cuantos
propondrian `aplicar`/`sugerir`): vaciarlo es trabajo de esos comandos, no
un fallo. Codigo de salida: 0 sin hallazgos, 1 con hallazgos, 2 error de
uso (`--confirmar` sin `--podar`).

`--podar` no destruye: mueve las copias sobrantes a `.papelera/` dentro del
historial y escribe UN log con `restaurar: true`. La accion `deshacer`
reconoce la marca (el motor no se modifica) y devuelve cada copia a su
ruta original exacta (`destino` del log = ruta original, absoluto como en
el motor). Tras una restauracion completa sin errores, la papelera se
purga.

## Consecuencias

- Positivas: `verificar --podar` + `deshacer` forman un par reversible sin
  tocar el motor; el JSON es documento unico (stdout limpio, avisos por
  stderr); los hallazgos determinan el codigo de salida para scripts.
- Negativas: el hash completo de arboles grandes cuesta IO (mitigado con
  lectura por bloques y omision de ocultos/temporales/papelera); un log
  `restaurar` copiado a otro historial pierde la papelera (los movimientos
  son absolutos: restaura donde estaban, o falla humano).
- `--logs-dir` se resuelve a absoluto en esta accion: el log debe registrar
  donde vive la papelera para que `deshacer` la encuentre desde cualquier
  cwd. `verificar` es el unico comando con esta resolucion.

## Alternativas descartadas

- **Borrar duplicados directamente**: irreversible, contradice la regla de
  "todo movimiento se puede deshacer" de la v1.0.
- **Papelera dentro de `Organizado/.papelera`**: contaminaria el area que
  otros comandos auditan/organizan; dentro del historial es invisible para
  `ejecutar`/`revisar`/`verificar`.
- **Mover a un "origen"**: los duplicados no tienen origen comun con la
  pasada; restaurar la RUTA EXACTA es la unica semantica honesta.
- **Deteccion por tamano+mtime**: falsos negativos con `cp -p`/sincroniza-
  dores; el hash es la unica evidencia dura.
