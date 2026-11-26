# Changelog

Todos los cambios destacados del CLI `organizador`. El formato sigue
[Keep a Changelog](https://keepachangelog.com/es/1.1.0/) y la versión del
paquete sigue [Semantic Versioning](https://semver.org/lang/es/). La etiqueta
git `v1.0` corresponde a la entrega final del proyecto (paquete `2.4.0`);
la etiqueta `v1.1` es la versión definitiva con fase 7 publicada (paquete
`2.5.0`); la etiqueta `v1.2` añade la fase 8 (PDFs por contenido, paquete
`2.6.0`); la etiqueta `v1.3` publica la fase 9 (guía de extensión y
superficie pública de emparejamiento, paquete `2.6.1`); la `v1.3.1` audita
el sdist publicado (`2.6.2`); la `v1.4` añade DOCX opcional (`2.7.0`); la
`v1.4.1` es el parche de cierre (`2.7.1`, el que muestra `organizador
--version`).

## [2.7.1] — 2026-11-26 (etiqueta git `v1.4.1`, cierre del curso)

### Añadido

- Quickstart **"Primeros 5 minutos"** al principio del README: instalación,
  cuatro archivos de ejemplo, `--simular` y el ciclo completo
  ejecutar → deshacer con la **salida real** de la CLI (no un bloque
  inventado). Es lo primero que ve quien evalúa.

### Cambiado

- El bloque `Resumen` de la salida humana alinea los valores en columna de
  22: la clave más larga (`Archivos procesados:`) ya no queda pegada al
  número. Cero cambios de comportamiento: solo presentación, el JSON no se
  toca y `test_despues_de_podar_reaudita_y_deja_cero_duplicados` fija el
  nuevo espaciado.

### Corregido

- La auditoría lenta del sdist (`tests/test_paquete.py`) instalaba `pypdf`
  "vacío": la rueda local mínima se reempaquetaba sin `Requires-Dist` y en
  Python < 3.11 faltaba `typing_extensions` (pypdf 7 lo importa). Ahora la
  rueda conserva el metadata real del proveedor y la closure de
  dependencias de runtime se calcula con marcadores evaluados
  (`packaging.markers`) — mismo contrato sin red: todo viaja como rueda
  local. Se reproduce en Python 3.10 (antes solo pasaba en ≥ 3.11).
- Higiene de CI: el extra `dev` fija `ruff>=0.17.6,<0.18` (sin pin, dos
  ejecuciones pedían órdenes de imports opuestos) y la comprobación de
  disponibilidad `build/wheel` pasa a `importlib.util.find_spec`, sin
  imports con comentarios que isort reordena distinto según la versión.

## [2.7.0] — 2026-11-27 (etiqueta git `v1.4`, fase 11)

### Añadido

- `--contenido` también lee **DOCX** en `ejecutar`, `revisar` y `explicar`.
  El nuevo extra `organizador[docx]` instala `python-docx>=1.1,<2`;
  `organizador[pdf]` sigue bastando para PDF y `.[pdf,docx]` instala ambos.
  La lectura incluye título, párrafos y celdas de tabla, con el mismo
  techo de 4000 caracteres y sin paginación: `--contenido-max-paginas`
  sigue aplicándose solo a PDF. ADR-007.
- `texto_documento(ruta, max_paginas)`, `texto_docx(ruta)`, `es_lexible(nombre)`
  y `EXTENSIONES_LEXIBLES` en `contenido.py`. Las tres fábricas inyectan el
  mismo despachador; el motor solo pregunta por extensiones leibles.
  `texto_pdf` y `clasificar_por_contenido` conservan su firma.
- `tests/documentos.py` (DOCX reales, sin binarios versionados) y 18 pruebas
  en `tests/test_docx.py`: lector, extra ausente, archivo corrupto,
  despacho por extensión mayúscula/minúscula, motor, `--contenido` en los
  tres comandos y error humano que no mueve nada.

### Cambiado

- Documentación: README (instalación por formato, límites y flag),
  guion de defensa (sección 9/10/12), ADR-006 enlazado al 007, auditoría
  de pruebas y `RELEASES.md`.

## [2.6.2] — 2026-11-27 (etiqueta git `v1.3.1`, fase 10)

### Añadido

- Auditoría del **paquete publicado** (`tests/test_paquete.py`, marca
  `lento`): construye el sdist del repo, lo instala en un venv real y
  ejerce el contrato de la release en el artefacto — `--version` igual al
  módulo, `--contenido` sin el extra `[pdf]` devolviendo 2 con el mensaje
  de instalación, y con el extra un PDF real organizado por contenido. La
  matriz de tests la excluye (`-m "not lento"`); el job `lint` la corre.
  Se auto-salta con honestidad si el interprete no puede crear venvs o si
  `pypdf` vive dentro de él.
- Guía de defensa `docs/guion-defensa.md` (fase 9.5, fusionada en la rama
  sin etiqueta): 12 respuestas cortas para sustentar el proyecto en vivo
  (arquitectura, fábrica, 5 aserciones duras, excepciones/códigos, `afirmar`
  vs `assert`, capas, IA, sin sorpresas, `--contenido`, release, ciclo del
  log y preguntas trampa), cada una con su `archivo:linea`. Enlazada desde
  la auditoría del README.

### Cambiado

- La suite rapida es `pytest -m "not lento"` (259 pruebas). La nueva
  auditoria no distorsiona la cobertura (subprocess no instrumentado):
  viaja en `lint`.

## [2.6.1] — 2026-11-27 (etiqueta git `v1.3`, fase 9)

### Añadido

- Guía `docs/como-anadir-una-accion.md`: los tres pasos mecánicos para
  sumar un comando sin tocar el núcleo (clase con fábrica + línea de
  registro + subparser), con ejemplo mínimo completo, los candados de la
  suite que lo verifican (fábrica, README y `--help` e2e) y checklist. El
  README enlaza la guía. Responde al criterio "anadir una accion no exige
  tocar el codigo" haciendo el patron visible, no solo cierto.
- `reglas.py` expone el contrato de emparejamiento (enmienda ADR-002):
  `trocear`, `coincide_token` y `coincide_pegado` como superficie pública
  documentada; `_coincide`/`_pega` pasan a ser adaptadores internos sobre
  ellas (decisión idéntica, el motor no cambia). `aplicar` deja de importar
  privados (`_pega`/`_tokens` y su truco de join) y consume las públicas.
  Nuevas pruebas de contrato en `tests/test_reglas.py` (incluida la no
  contradicción motor/pública recorriendo el catálogo en orden).

## [2.6.0] — 2026-11-27 (etiqueta git `v1.2`)

### Añadido

- Fase 8 (`--contenido`, ADR-006): `ejecutar`, `revisar` y `explicar`
  pueden clasificar por el texto de las primeras páginas de un PDF cuando
  el nombre no clasifica. Opt-in con `--contenido` (y
  `--contenido-max-paginas N`, por defecto 3); sin el flag el
  comportamiento es idéntico a la v1.1. El emparejamiento usa fronteras de
  palabra (nada de `mysql` → `sql`) e ignora alias de 1–2 letras (temas
  `1`, `T1`): texto continuo, menos señales que un nombre de archivo. El
  nombre siempre manda: el contenido solo rescata lo que iría a
  `_revision`. En `revisar --interactivo` la sugerencia por contenido
  aparece marcada como `(contenido)`, y cada movimiento del JSON/log lleva
  el campo `origen` (`nombre` o `contenido`).
- Extra opcional `organizador[pdf]` (`pypdf`, BSD, pure python): el paquete
  base sigue siendo stdlib puro; sin el extra, `--contenido` responde un
  error humano con el comando de instalación. La suite de desarrollo lo
  instala (`.[dev]`) y genera sus propios PDFs de prueba.

## [2.5.0] — 2026-11-27 (etiqueta git `v1.1`, versión definitiva)

### Añadido

- CI multiplataforma: la matriz cubre Ubuntu (Python 3.10–3.13) y Windows
  (3.12/3.13), con el escáner de claves portable (`git ls-files -z |
  xargs -0`). macOS queda fuera: los runners `macos-*` no están
  disponibles en planes gratuitos y no se finge cobertura.
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
- Workflows de CI probados en producción: dos correcciones sobre la marcha
  durante la fusión de la fase 7C (badge sin working tree → checkout de
  `main` antes de generar; checkout de `badges` con `clean: false` para no
  borrar el `data.json` recien generado).

### Arreglado

- El workflow del escudo de cobertura fallaba en `main` porque el job
  `badge` ejecutaba `scripts/badge.py` sin código en el directorio de
  trabajo: ahora hay un `checkout` de `main` explícito antes de generar.

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
