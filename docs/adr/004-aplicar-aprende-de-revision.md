# ADR 004 — `aplicar`: aprender alias de `_revision` en mayoria de evidencias

- **Estado**: Aceptado
- **Fecha**: 2026-11-23
- **Contexto**: Fase 7 (post-release)

## Contexto

Hasta la v1.0 el circulo de clasificacion era abierto: un archivo que caia
en `_revision` solo podia recolocarse a mano (`revisar --interactivo`) o
por IA (`sugerir --aplicar`), y nada ensenaba a la CLI. La proxima tanda de
descargas con el mismo patron de nombre volvia a `_revision`. La IA es
opcional por diseno (ADR-003), asi que el aprendizaje no puede depender de
ella.

## Decision

Nuevo septimo comando, `aplicar`, en una sola clase con fabrica (ADR-002),
con tres fases estrictas y deterministas:

1. **Proponer** (por defecto): `sugerir_alias(nombre, reglas)` — funcion
   pura — tokeniza con la misma normalizacion del motor, detecta los tokens
   desconocidos y cuenta evidencias por asignatura. Gana la mayoria; un
   empate o la ausencia de evidencia no generan propuesta. Descarta tokens
   genericos (`tema`, `apuntes`, `examen`, sufijos `x1`, digitos sueltos...)
   que solo refuerzan la asignatura pero no aportan alias.
2. **Confirmar** (`--confirmar`): pregunta alias a alias con
   `Consola.respuesta_si`. Los aceptados se fusionan en las reglas del
   usuario (`ruta_reglas_usuario()`, ADR-001) conservando tema/aliases
   previos; los rechazados y las cancelaciones EOF **no escriben nada**.
   Con `--reglas` explicitas el guardado se hace en ESE fichero: quien usa
   un catalogo propio quiere que la sugerencia viva ahi.
3. **Reorganizar** (`--reorganizar`, exige `--confirmar` → si no,
   `ErrorDeUso`): mueve con `mover_archivo` (sufijo anti-colision del motor)
   y guarda el log con `Registro.guardar_historial`, compatible con
   `deshacer`.

## Consecuencias

- Positivas: el ciclo se cierra sin red; `deshacer` funciona igual (mismo
  origen registrado: `Salida/_revision`); el contrato README/parametrizaciones
  de `test_docs_readme` obliga a documentar el comando en la misma PR.
- Negativas: el heuristico puede proponer un alias indeseado — mitigado por
  la confirmacion explicita archivo a archivo, la mayoria de evidencias y
  la valla de tokens cortos (>= 2 desconocidos o uno de 4+ letras).
- El alias guardado pasa a tratarse exactamente como una regla escrita a
  mano: misma coincidencia (`_coincide`/`_pega`), mismo orden de reglas.

## Alternativas descartadas

- **Alias magicos por frecuencia** (un token desconocido gana solo): falso
  positivo seguro con `repaso`, `examen`, `x2`.
- **Escribir en `~/.config/organizador/aprendidas.json`**: segundo fichero
  con semantica propia, mas superficie de carga y mas codigo; la fusion en
  el fichero de usuario ya esta resuelta por `reglas_efectivas`.
- **IA obligatoria** (como `sugerir`): contradice ADR-003; ademas aqui no
  se necesita contexto semantico, basta evidencia lexica repetida.
