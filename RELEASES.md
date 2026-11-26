# Releases

Historial de entregas del CLI `organizador`. La etiqueta `v1.0` marca la
entrega final del proyecto; la etiqueta `v1.1` es la **versión definitiva**;
la etiqueta `v1.2` añade la fase 8 (clasificación opcional por el texto de
los PDF); la etiqueta `v1.3` publica la fase 9 (documentación de extensión
y superficie pública de emparejamiento); la `v1.3.1` audita el sdist; la
`v1.4` añade la fase 11 (DOCX opcional con la misma bandera) y la `v1.4.1`
es el parche de cierre (quickstart, resumen alineado y auditoría lenta
portable). El número interno del paquete conserva la cronología `2.x`
(`organizador --version` muestra `2.7.1`).

El detalle línea a línea de cada versión vive en
[docs/CHANGELOG.md](docs/CHANGELOG.md). Esta página resume las entregas y sus
verificaciones.

## v1.4.1 — parche de cierre: quickstart, resumen alineado y auditoría portable

- **Fecha**: 2026-11-26
- **Tag**: `v1.4.1`
- **Base técnica**: PR #21; el tag apunta al commit de release con esta
  documentación cerrada.
- **Paquete**: `organizador` 2.7.1
- **Python**: 3.8+ (CI verificada en Ubuntu 3.10–3.13 y Windows 3.12/3.13)

Parche sin funciones nuevas. Tres retoques de presentación y una corrección
de la propia auditoría:

- **Quickstart** "Primeros 5 minutos" al principio del README, con la
  salida real de la CLI (simular → ejecutar → deshacer).
- El bloque `Resumen` alinea los valores en columna de 22: la clave más
  larga (`Archivos procesados:`) ya no quedaba pegada al número. Solo
  presentación humana; el JSON no se toca.
- La auditoría lenta del sdist instalaba `pypdf` "vacío" en Python < 3.11:
  la rueda local se reempaquetaba sin `Requires-Dist` y faltaba
  `typing_extensions`. Ahora conserva el metadata y calcula la closure de
  dependencias con marcadores, siempre sin red. Se reproduce en 3.10.

### Verificación (commit de release)

| Comprobación | Resultado |
|---|---|
| `ruff check .` / `ruff format --check .` | limpio |
| `mypy src` / `mypy tests` | limpio |
| `pytest -m "not lento" --cov=organizador --cov-fail-under=85` | 277 passed, 93.18 % |
| `pytest tests/test_paquete.py -m lento` | 1 passed (sdist en venv real, `[pdf]`, Python 3.10) |
| `git ls-files -z \| xargs -0 python scripts/check_secretos.py` | limpio |
| CI en `main` post-fusión | verde (matriz completa) |
| Auditoría detallada | `docs/auditoria-tests.md` |

## v1.4 — fase 11: DOCX opcional (mejora menor)

- **Fecha**: 2026-11-27
- **Tag**: `v1.4`
- **Base técnica**: PR #20 (commit funcional `45291d2`); el tag apunta al
  commit de release con esta documentación cerrada.
- **Paquete**: `organizador` 2.7.0
- **Python**: 3.8+ (CI verificada en Ubuntu 3.10–3.13 y Windows 3.12/3.13)

`--contenido` cubre ahora PDF y DOCX con la misma bandera y la misma
segunda pasada. El nombre sigue mandando; el DOCX solo se abre si el nombre
no clasifica. El extra `organizador[docx]` instala `python-docx>=1.1,<2`;
`organizador[pdf]` sigue siendo suficiente para PDF y `.[pdf,docx]` instala
ambos. El core no gana dependencias: los imports siguen siendo diferidos.

### Contenido

- `src/organizador/contenido.py`: `texto_docx`, `texto_documento`,
  `es_lexible` y `EXTENSIONES_LEXIBLES`; titulo, parrafos y tablas, con el
  techo de 4000 caracteres. `--contenido-max-paginas` queda reservado a PDF.
- Motor y fabricas: una sola decision por extension inyectada en `ejecutar`,
  `revisar` y `explicar`; el motor pregunta por `.pdf`/`.docx` y nunca por
  `.txt`. JSON y humanos conservan `origen=contenido` y `Fuente: contenido`.
- `docs/adr/007-docx-opcional.md` (ADR-006 queda enlazado), README, guion de
  defensa, CHANGELOG y auditoria actualizados.
- `tests/documentos.py` + 18 pruebas en `tests/test_docx.py`: DOCX reales,
  extra ausente, archivo corrupto, despacho por extension, motor y tres
  comandos. Limitacion declarada: la auditoria lenta del sdist sigue
  cubriendo `[pdf]`; `[docx]` se prueba en suite rapida (ADR-007).

### Verificación (commit de release)

| Comprobación | Resultado |
|---|---|
| `ruff check .` / `ruff format --check .` | limpio |
| `mypy src` / `mypy tests` | limpio |
| `pytest -m "not lento" --cov=organizador --cov-fail-under=85` | 277 passed, 93.18 % |
| `pytest tests/test_paquete.py -m lento` | 1 passed (sdist en venv real, `[pdf]`) |
| `git ls-files -z \| xargs -0 python scripts/check_secretos.py` | limpio |
| CI en `main` post-fusión | verde (matriz completa) |
| Auditoría detallada | `docs/auditoria-tests.md` |

## v1.3.1 — fase 10: auditoría del sdist (parche)

- **Fecha**: 2026-11-27
- **Tag**: `v1.3.1`
- **Base técnica**: `2ae0380` (PR #19 + guía de defensa 9.5 fusionada en la
  rama); el tag apunta al commit de release.
- **Paquete**: `organizador` 2.6.2
- **Python**: 3.8+ (CI verificada en Ubuntu 3.10–3.13 y Windows 3.12/3.13)

Parche sin cambios de comportamiento. La promesa "se instala con una orden"
 pasa de fe en el README a prueba ejecutada: `tests/test_paquete.py`
construye el sdist del repo, lo instala en un venv real y ejerce el contrato
del extra `[pdf]` sobre el artefacto (versión, error humano sin el extra,
flujo con él). CI: la matriz excluye la marca `lento`; `lint` la corre.

### Contenido

- `tests/test_paquete.py` (1 prueba `lento`, ~10 s): sin red
  (`--no-isolation`, `--no-index`, `pypdf` copiado como rueda local);
  `skip` honesto si no se puede crear un venv útil.
- `docs/guion-defensa.md` (fase 9.5, fusionada en rama sin etiqueta): 12
  respuestas de defensa con `archivo:linea`.
- Marca `lento` registrada; workflow actualizado.

### Verificación (commit de release)

| Comprobación | Resultado |
|---|---|
| `ruff check .` / `ruff format --check .` | limpio |
| `mypy src` / `mypy tests` | limpio |
| `pytest -m "not lento" --cov=organizador --cov-fail-under=85` | 259 passed, 92.99 % |
| `pytest tests/test_paquete.py -m lento` | 1 passed (venv real, sin red) |
| `git ls-files -z \| xargs -0 python scripts/check_secretos.py` | limpio |
| CI en `main` post-fusión | verde (matriz completa) |
| Auditoría detallada | `docs/auditoria-tests.md` |

## v1.3 — fase 9: extensible y desacoplada (parche)

- **Fecha**: 2026-11-27
- **Tag**: `v1.3`
- **Base técnica**: `d98482e` (PR #15 y #16); el tag apunta al commit de
  fusión de esta release.
- **Paquete**: `organizador` 2.6.1
- **Python**: 3.8+ (CI verificada en Ubuntu 3.10–3.13 y Windows 3.12/3.13)

Fase 9: el patrón "una acción = una clase" deja de ser implícito. Cero
cambios de comportamiento — el motor y los ocho comandos deciden exactamente
igual que en la v1.2 (así lo certifican las 255 pruebas heredadas + 4
nuevas de contrato).

### Contenido

- `docs/como-anadir-una-accion.md`: guía de extensión (3 pasos mecánicos +
  ejemplo mínimo + tabla de candados de la suite + checklist), enlazada
  desde el README.
- `reglas.py` publica su contrato de emparejamiento (enmienda ADR-002):
  `trocear`, `coincide_token`, `coincide_pegado`; `_coincide`/`_pega`
  delegan (decisión idéntica). `aplicar` deja de importar privados.

### Verificación (commit de release)

| Comprobación | Resultado |
|---|---|
| `ruff check .` / `ruff format --check .` | limpio |
| `mypy src` / `mypy tests` | limpio |
| `pytest --cov=organizador --cov-fail-under=85` | 259 passed, 92.99 % |
| `git ls-files -z \| xargs -0 python scripts/check_secretos.py` | limpio |
| `python -m build` + `twine check --strict` | sdist+wheel válidos |
| CI en `main` post-fusión | verde (matriz completa) |
| Smoke (rueda de la release, venv limpio) | `--version` 2.6.1, flujo completo con y sin `--contenido` |
| Auditoría detallada | `docs/auditoria-tests.md` |

## v1.2 — fase 8: PDFs por contenido

- **Fecha**: 2026-11-27
- **Tag**: `v1.2`
- **Base técnica**: `b477527` (PR #13); el tag apunta al commit de fusión de
  esta release.
- **Paquete**: `organizador` 2.6.0
- **Python**: 3.8+ (CI verificada en Ubuntu 3.10–3.13 y Windows 3.12/3.13)

Sobre la v1.1: los PDFs cuyo nombre no clasifica (`Tema4.pdf`,
`examen_resuelto.pdf`) pueden rescatarse de `_revision` leyendo sus
primeras páginas. Opt-in con `--contenido` en `ejecutar`, `revisar` y
`explicar`; sin el flag, la CLI es idéntica a la v1.1.

### Contenido

- `--contenido` (y `--contenido-max-paginas N`, por defecto 3): el nombre
  siempre manda; el contenido solo intenta lo que iría a `_revision`.
  Emparejamiento por fronteras de palabra con el catálogo de siempre
  (nada de `mysql` → `sql`); los alias de 1–2 letras (temas `1`, `T1`)
  no participan. ADR-006.
- Extra `organizador[pdf]` (`pypdf`, BSD, pure python, cero dependencias
  transitivas): el paquete base sigue siendo stdlib puro. Sin el extra,
  `--contenido` responde un error humano con el comando de instalación.
- Movimientos del JSON y del log llevan `origen` (`nombre`/`contenido`);
  `explicar --contenido` responde `Fuente: contenido`; `revisar
  --interactivo` marca `(contenido)` la sugerencia en el prompt.
- Suite ampliada a 255 pruebas; cobertura 92.98 % (margen sobre el 85 %).

### Verificación (commit de release)

| Comprobación | Resultado |
|---|---|
| `ruff check .` / `ruff format --check .` | limpio |
| `mypy src` / `mypy tests` | limpio |
| `pytest --cov=organizador --cov-fail-under=85` | 255 passed, 92.98 % |
| `git ls-files -z \| xargs -0 python scripts/check_secretos.py` | limpio |
| `python -m build` + `twine check --strict` | sdist+wheel válidos (`contenido.py` y `py.typed` dentro) |
| CI en `main` post-fusión | verde (matriz completa) |
| Smoke con `--contenido` (PDFs reales generados) | rescata a `BaseDeDatos/Normalizacion`, `explicar` dice `Fuente: contenido` |
| Auditoría detallada | `docs/auditoria-tests.md` |

## v1.1 — versión definitiva

- **Fecha**: 2026-11-27
- **Tag**: `v1.1`
- **Base técnica**: `f4340ed` (CI de la fase 7C ya probada en `main`); el
  tag `v1.1` apunta al commit de fusión de esta release.
- **Paquete**: `organizador` 2.5.0
- **Python**: 3.8+ (CI verificada en Ubuntu 3.10–3.13 y Windows 3.12/3.13)

Versión definitiva de la CLI: a la base de la v1.0 se suman el séptimo y
octavo comando (`aplicar`, `verificar`) y la fase de distribución (matriz
multi-SO, escudo de cobertura self-hosted, `mypy` sobre tests y job de
construcción sdist+wheel). Ocho comandos documentados, con logs deshacibles,
reglas externas, IA opcional con fallback y control de secretos.

### Contenido

- Séptimo comando `aplicar`: aprende alias de `_revision` (mayoría de
  evidencias, sin IA), `--confirmar` los guarda fusionados en las reglas
  del usuario y `--reorganizar` (exige `--confirmar`) mueve lo
  clasificable con log deshacible. ADR-004.
- Octavo comando `verificar`: audita la salida (duplicados por hash,
  subproductos, vacíos, fuera de catálogo, atrapados) y `--podar
  --confirmar` desactiva duplicados a la papelera del historial con log
  `restaurar`; `deshacer` devuelve cada copia a su ruta original. ADR-005.
- Fase 7C: matriz CI Ubuntu (3.10–3.13) + Windows (3.12/3.13), escudo de
  cobertura self-hosted (rama `badges`, `scripts/badge.py` probado),
  `mypy` sobre tests con `py.typed`, job `build` de sdist+wheel con
  `twine check --strict`. macOS fuera de la matriz: runners no
  disponibles en plan gratuito (decisión documentada, no cobertura
  fingida).
- Suite: 221 pruebas, cobertura 93.04 % (margen +8 pp sobre el umbral 85).

### Verificación (commit de release)

| Comprobación | Resultado |
|---|---|
| `ruff check .` / `ruff format --check .` | limpio |
| `mypy src` / `mypy tests` | limpio |
| `pytest --cov=organizador --cov-fail-under=85` | 221 passed, 93.04 % |
| `git ls-files -z \| xargs -0 python scripts/check_secretos.py` | limpio |
| `python -m build` + `twine check --strict` | sdist+wheel válidos |
| CI en `main` post-fusión | verde (matriz completa) |
| Escudo de cobertura | `data.json` en `badges`, endpoint servido |
| GitHub Release `v1.1` | artefactos CI adjuntados (sin PyPI) |
| Prueba de humo (rueda de la release, venv limpio) | `--version` 2.5.0, `ejecutar`+`deshacer`+`--json`+`verificar` correctos |
| Auditoría detallada | `docs/auditoria-tests.md` |

## v1.0 — entrega final

- **Fecha**: 2026-11-18
- **Tag**: `v1.0`
- **Base técnica**: `f0b9305` (código y auditoría previos a esta nota); el tag
  `v1.0` apunta al commit de fusión de esta release.
- **Paquete**: `organizador` 2.4.0
- **Python**: 3.8+ (CI verificada en 3.10, 3.11, 3.12 y 3.13)

Release final de la CLI para organizar descargas por asignatura y tema usando
solo el nombre del archivo. Incluye el motor determinista, los seis comandos,
reglas externas, logs deshacibles, IA opcional con fallback local, control de
secretos y la auditoría de pruebas.

### Contenido

- `ejecutar`, `revisar`, `deshacer`, `reglas`, `sugerir` y `explicar`.
- Organización por asignatura/tema con `_revision/` para lo no clasificado.
- Simulación, recursión, filtros por extensión y patrón, `--desde`, resumen
  `--seco`, modo `--json` y códigos de salida estables.
- Confirmación interactiva o explícita antes de mover archivos en `revisar` y
  en `sugerir --aplicar`.
- Reglas por defecto para 1º DAM, reglas del usuario en
  `$XDG_CONFIG_HOME/organizador/reglas.json` (o `~/.config/organizador/`) y
  validación de JSON con errores previsibles.
- Historial de logs fuera del origen, `--ultimos`, `--listar` y `deshacer`
  incluso tras aplicar sugerencias de IA.
- Proveedor de IA extraíble: se activa solo con `ORGANIZADOR_API_KEY`,
  `ORGANIZADOR_IA_URL` y `ORGANIZADOR_IA_MODELO`; ante error o respuesta
  inválida cae a las reglas locales. Nunca se registra ni imprime la clave.
- Sin dependencias de red para el funcionamiento básico: solo `stdlib` en el
  motor y dependencias de desarrollo ya conocidas (`pytest`, `pytest-cov`,
  `ruff`, `mypy`, `pre-commit`).

### Verificación

| Comprobación | Resultado |
|---|---|
| `ruff check .` | limpio |
| `ruff format --check .` | limpio |
| `mypy src` | limpio |
| `pytest --cov=organizador --cov-fail-under=85` | 148 passed, 94.22 % |
| `python3 scripts/check_secretos.py $(git ls-files)` | limpio |
| CI en Python 3.10–3.13 | verde |
| Auditoría detallada | `docs/auditoria-tests.md` |

### Decisiones y documentación

- `docs/adr/001-configuracion-externa.md`: salida, reglas y logs configurables.
- `docs/adr/002-una-accion-una-clase.md`: una acción por clase con fábrica
  `desde_config`; interfaz, motor, acciones y presentación separados.
- `docs/adr/003-proveedor-ia.md`: proveedor opcional, entorno y fallback.
- `docs/adr/005-verificar-audita-y-poda.md`: auditoría de la salida y poda reversible.
- `docs/adr/006-contenido-pdf-opcional.md`: clasificación opcional por el
  texto de los PDF (extra `organizador[pdf]`, opt-in, el nombre manda).
- `docs/auditoria-tests.md`: cobertura, casos feos, regresiones y límites.
- `.env.example`: plantilla sin valores reales; `.env` nunca se versiona.

### Límites conocidos

- No lee contenido de PDF ni usa OCR: solo el nombre del archivo.
- Sin interfaz gráfica.
- La IA es opcional y no se prueba contra proveedores reales.
- CI cubre Linux; no hay matriz Windows/macOS.

## Historial del paquete

| Versión | Hito | Commits/PRs relevantes |
|---|---|---|
| 2.7.1 | Parche de cierre: quickstart, resumen alineado y auditoría lenta portable | tag `v1.4.1` |
| 2.7.0 | Fase 11: DOCX opcional con `--contenido` | `45291d2`, PR #20, tag `v1.4` |
| 2.6.2 | Fase 10: auditoría del sdist publicado (venv real, sin red) | PR #19, tag `v1.3.1` |
| 2.6.1 | Fase 9: guía de extensión y superficie pública de emparejamiento | `d98482e`, PR #15, PR #16, tag `v1.3` |
| 2.6.0 | Fase 8: clasificación opcional por el texto de los PDF (`--contenido`) | `b477527`, PR #13, tag `v1.2` |
| 2.5.0 | Versión definitiva: `aplicar` + `verificar` + CI multi-SO, badge y build | PR #8, PR #9, PR #10, tag `v1.1` |
| 2.4.0 | Sugerir/explicar con proveedor opcional y fallback; auditoría final | `415f3e2`, `1984985`, PR #4, PR #5 |
| 2.3 | Excepciones propias, mensajes humanos y CI de calidad | `22533c5`, `2ee66a4`, PR #1 |
| 2.2 | Recursivo, filtros, JSON, `confirmar` y `revisar` interactivo | `7a59937` |
| 2.1 | Reglas personalizadas e historial de logs | `f5d770d` |
| 2.0 | Log fuera del origen, matching compacto y correcciones de CLI | `ecdf174` |
| 1.1 | Log JSON y comando `revisar` | `6e51c8a` |
| 1.0 | Primera versión: organización por asignatura y tema | `f8a587c` |

## Instalación rápida

```bash
pip install .
organizador --version
organizador ejecutar descargas --simular
```

Para ejecutar sin instalar:

```bash
PYTHONPATH=src python -m organizador --help
```
