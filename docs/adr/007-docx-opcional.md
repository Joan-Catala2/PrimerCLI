# ADR 007 — DOCX: misma segunda pasada, otro extra opcional

- **Estado**: Aceptado
- **Fecha**: 2026-11-27
- **Contexto**: Fase 11 (post-v1.3.1)
- **Relación**: extiende el ADR 006 sin derogarlo

## Contexto

La fase 8 ya sabía leer PDF con `--contenido`, pero muchos apuntes llegan
como `.docx` con la asignatura en el título, en un párrafo o en una tabla.
El nombre sigue siendo la primera fuente; cuando calla, el texto del
documento puede salvar lo que caería en `_revision`.

Las restricciones no cambian: motor stdlib, sin red, determinista, errores
humanos sin traceback, `deshacer` como red de seguridad y dependencias
opcionales solo si el usuario las pide.

## Decision

1. **Misma bandera, sin comandos nuevos**: `--contenido` cubre PDF y DOCX en
   `ejecutar`, `revisar` y `explicar`. El JSON sigue diciendo
   `"origen": "contenido"` y `Fuente: contenido`; no hay una segunda marca.
2. **El nombre manda igual**: el DOCX solo se abre si el nombre no clasifica.
   La frontera de palabra y el mínimo de 3 letras del ADR 006 se aplican al
   texto extraído sin cambios.
3. **Extra distinto por formato**: `organizador[docx]` instala
   `python-docx>=1.1,<2` (Apache-2.0). `organizador[pdf]` sigue instalando
   `pypdf`. Instalar uno no obliga a instalar el otro; `.[dev]` incluye ambos.
4. **Import diferido y error humano**: el único `import docx` vive dentro de
   `_leer_docx`. Sin el extra, `ErrorDeUso` dice `pip install
   organizador[docx]`; un DOCX corrupto es `ExtraccionFallida`, aviso y
   `_revision`, nunca un traceback.
5. **Un despachador, tres fabricas**: `texto_documento(ruta, max_paginas)`
   elige el lector por extensión (`.pdf` / `.docx`, sin distinción de
   mayúsculas). Las fábricas de las tres acciones inyectan esa única función;
   no se reparte la decisión por la capa de acciones.
6. **El motor solo pregunta por extensiones leibles**: `_es_leible` usa la
   tupla pública `EXTENSIONES_LEXIBLES` de `contenido.py`. Los `.txt` y los
   temporales siguen sin abrirse.
7. **DOCX sin paginación**: se leen título, párrafos y celdas de tabla, con
   el mismo techo de 4000 caracteres. `--contenido-max-paginas` sigue
   validándose y aplicándose solo a PDF.

## Consecuencias

- `contenido.py` gana `texto_docx`, `texto_documento`, `es_lexible` y
  `EXTENSIONES_LEXIBLES`. `texto_pdf` y `clasificar_por_contenido` conservan
  su firma: la fase 8 no se reescribe.
- El paquete base sigue sin dependencias de terceros: `python-docx` entra
  solo en el extra y se importa en el momento de leer. Python 3.8 no se
  rompe: el extra resolverá la última versión compatible; la base no lo
  importa.
- La auditoría lenta del sdist sigue ejerciendo el contrato `[pdf]`; los
  DOCX se cubren con archivos reales generados en `tests/documentos.py`.
  No se promete auditoría de `[docx]` en un venv aislado porque `lxml`
  (dependencia de `python-docx`) no se puede prestar como rueda local sin
  red de forma fiable. Esa limitación queda escrita en la auditoría.
