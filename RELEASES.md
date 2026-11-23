# Releases

Historial de entregas del CLI `organizador`. La etiqueta `v1.0` marca la
entrega final del proyecto; el número interno del paquete conserva la
cronología `2.x` ya documentada (`organizador --version` muestra `2.4.0`).

El detalle línea a línea de cada versión vive en
[docs/CHANGELOG.md](docs/CHANGELOG.md). Esta página resume las entregas y sus
verificaciones.

## Sin publicar — fase 7 (aplicar)

En la rama `feat/comando-aplicar`, pendiente de fusión:

- Séptimo comando `aplicar`: aprende alias de `_revision` (mayoría de
  evidencias, sin IA), `--confirmar` los guarda fusionados en las reglas
  del usuario y `--reorganizar` (exige `--confirmar`) mueve lo
  clasificable con log deshacible. ADR-004.
- Suite ampliada a 190 pruebas; cobertura 93.64 % (margen sobre el 85 %).

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
