# Changelog

Todos los cambios destacados del CLI `organizador`. El formato sigue
[Keep a Changelog](https://keepachangelog.com/es/1.1.0/) y la versión del
paquete sigue [Semantic Versioning](https://semver.org/lang/es/). La etiqueta
git `v1.0` corresponde a la entrega final; el número interno del paquete es
`2.4.0` y es el que muestra `organizador --version`.

## [Sin publicar]

### Añadido

- CI multiplataforma: la matriz cubre Ubuntu (Python 3.10–3.13), macOS 14
  y Windows (3.12/3.13), con el escáner de claves portable
  (`git ls-files -z | xargs -0`).
- Escudo de cobertura self-hosted: el job `test` sube `coverage.xml`, el
  job `badge` genera `data.json` (script `scripts/badge.py`, probado en
  `tests/test_badge.py`) y lo publica en la rama `badges`; el README lo
  pinta con shields.io en modo endpoint. Sin servicios externos.
- `mypy` también sobre `tests` (con `py.typed` en el paquete y ajustes de
  configuración); el pre-commit ejecuta `mypy src` y `mypy tests`.
- Job `build`: `python -m build` de sdist+wheel con `twine check --strict`
  y artefactos; los guiones de desarrollo (`check_secretos.py`, `badge.py`)
  viajan en el sdist vía `data-files`.
- Comando `verificar`: audita `Organizado/` — duplicados (SHA-256),
  subproductos del navegador (`doc (1).pdf`), carpetas vacías, carpetas
  fuera de catálogo y archivos "atrapados" en la raíz de una asignatura;
  informa del estado de `_revision` (cuántos propondrían
  `aplicar`/`sugerir`). Devuelve código 1 si hay hallazgos. `--podar
  --confirmar` mueve las copias sobrantes a una papelera dentro del
  historial con log `restaurar`; `deshacer` devuelve cada copia a su carpeta
  original exacta. Decisiones: `docs/adr/005-verificar-audita-y-poda.md`.
- Comando `aplicar`: aprende alias de los archivos de `_revision`
  (mayoría de evidencias, determinista y sin IA). Por defecto solo
  propone; `--confirmar` pregunta alias a alias y los guarda fusionados
  en las reglas del usuario (o en el fichero de `--reglas` si se usa);
  `--reorganizar` (exige `--confirmar`) mueve lo clasificable con las
  reglas nuevas y deja log deshacible. Decisiones:
  `docs/adr/004-aplicar-aprende-de-revision.md`.
- Documentación: esta línea temporal, enlace desde el README y desde
  `RELEASES.md`.
- La versión del paquete es dinámica: `pyproject.toml` deriva
  `organizador.__version__` en tiempo de empaquetado, así que solo hay una
  fuente de verdad.
- Pruebas de contrato: metadato PEP 621 == `__version__`, `pyproject.toml`
  sin `version` fija, catálogo de reglas empaquetado íntegro y README que
  documenta los seis subcomandos.

## [2.4.0] — 2026-11-18 (etiqueta git `v1.0`, entrega final)

### Añadido

- `sugerir`: propone asignatura y tema para `_revision` usando IA opcional o
  heurística local; `--aplicar` exige `--confirmar` y deja log deshacible.
- `explicar NOMBRE`: justifica el destino de un archivo (alias, tipo de
  coincidencia y frase de IA si está activa).
- Proveedor de IA extraíble (`ProveedorIA.desde_env()`): se activa solo con
  `ORGANIZADOR_API_KEY`, `ORGANIZADOR_IA_URL` y `ORGANIZADOR_IA_MODELO`;
  ante error de red o respuesta inválida cae a las reglas locales con código
  0 y aviso por stderr.
- Auditoría de pruebas en `docs/auditoria-tests.md`: cobertura 94.22 %, mapa
  requisito → prueba → caso feo y mutaciones razonadas.
- ADR-002 (`docs/adr/002-una-accion-una-clase.md`): una acción por clase con
  fábrica `desde_config`.

### Arreglado

- `sugerir --aplicar` ya no limpia `_revision` tras mover: el deshacer
  recuperaba mal los archivos (regresión `test_sugerir_aplicado_se_puede_deshacer`).
- `python -m organizador --json` emitía los errores como texto plano:
  `main(argv=None)` no veía `sys.argv` al detectar el modo JSON (regresión
  `test_cli_instalado_error_json_tiene_codigo_y_objeto_valido`).

## [2.3] — excepciones propias

### Añadido

- Jerarquía `OrganizadorError` (`ConfigError`, `AccionNoValida`,
  `ErrorDeUso`, `CarpetaNoValidaError`, `ErrorDeArchivo`, `ErrorDeSistema`)
  con mensajes humanos y códigos de salida estables (`1` general, `2` uso).
- `afirmar()`: aserción de desarrollo que sobrevive a `python -O`.
- Errores en modo `--json` como objeto JSON válido.
- Calidad en CI: `ruff`, `mypy`, cobertura mínima 85 % y `pre-commit`.

## [2.2] — filtros, JSON y confirmación

### Añadido

- `--recursivo`, `--extension`, `--excluir`, `--desde`, `--confirmar`,
  `--json` y `revisar --interactivo`.

## [2.1] — reglas del usuario e historial

### Añadido

- Reglas personalizadas en `~/.config/organizador/reglas.json` (respeta
  `XDG_CONFIG_HOME`), fusionadas con prioridad sobre las del paquete.
- Historial de logs en `--logs-dir` (por defecto `./organizador-logs`).

## [2.0] — log fuera del origen

### Cambiado

- El log del origen pasa a una carpeta de historial: `--recursivo` ya no
  reorganiza el propio historial.
- Coincidencia compacta sin falsos positivos (`trabajosql` vale, `FOL` no
  casa con `folder`).

### Arreglado

- Varios de CLI y de matching.

## [1.1] — log JSON y `revisar`

### Añadido

- Comando `revisar` y log JSON por ejecución.

## [1.0] — primera versión

### Añadido

- Organización por asignatura y tema a partir del nombre del archivo, con
  `_revision/` para lo no clasificado y sufijos `-1`, `-2`, ... en colisiones.

[sin publicar]: https://github.com/Joan-Catala2/PrimerCLI/compare/v1.0...HEAD
[2.4.0]: https://github.com/Joan-Catala2/PrimerCLI/releases/tag/v1.0
