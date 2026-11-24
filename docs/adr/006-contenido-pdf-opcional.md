# ADR 006 — Contenido de PDF: clasificacion opcional por texto, extranjeria y orden

- **Estado**: Aceptado
- **Fecha**: 2026-11-24
- **Contexto**: Fase 8 (post-v1.1)

## Contexto

La v1.x clasifica usando solo el nombre del archivo, y asi queda documentado.
Muchos apuntes llegan como `Tema4.pdf` o `examen_resuelto.pdf`: el nombre no
dice la asignatura y el archivo cae en `_revision`, cuando el PDF lleva la
asignatura y el tema escritos en la propia portada. Leer las primeras paginas
recupera informacion que el nombre perdio.

Restricciones del proyecto: el motor es stdlib puro, sin red ni servicios,
determinista, con errores humanos sin traceback y con `deshacer` como garantia.
Anadir lectura de PDF no puede romper nada de eso.

## Decision

1. **Lectura opt-in, nunca por defecto**: sin flag, la CLI se comporta como
   en la v1.1 (mismo flujo, mismo JSON, mismo exit code). Se activa con
   `--contenido` en `ejecutar` y `revisar`, y con `--contenido-max-paginas N`
   (por defecto 3) se acota el trabajo.
2. **El nombre siempre manda**: el contenido se usa como *segundo intento*,
   solo para archivos que por nombre caerian en `_revision`. Un PDF que dice
   otra cosa que su nombre se organiza por el nombre.
3. **Dependencia optativa**: `pypdf` (BSD, pure python, cero dependencias
   transitivas, 3.8+) se instala solo con el extra `organizador[pdf]`. El
   paquete base sigue siendo stdlib puro.
4. **Import diferido**: el unico `import pypdf` vive dentro de `texto_pdf()`.
   Sin el extra la CLI responde `ErrorDeUso` con el comando de instalacion,
   sin traceback, y no toca ningun archivo.
5. **Solo `.pdf`** (la extension tal cual, no el stem: `apuntes.pdf` no es
   un txt disfrazado). Cualquier otro archivo pasa igual que antes.
6. **Frontera de palabra, no subcadena**: el texto del PDF es continuo y no
   tiene los separadores de un nombre de archivo; `SQL` dentro de `mysql`
   es un falso positivo tipico. Los alias de tema del catalogo (`1`, `2`,
   `T1`...) son demasiado cortos para el texto: en contenido solo valen
   alias de asignatura y de tema con 3+ letras, casados con regex de
   frontera `\w` (los digitos cuentan como ` \w`, asi que "tema4" no vale;
   "tema 4", si).
7. **Determinista y sin red**: ninguna llamada externa, ningun reloj, nada
   de aleatoriedad. El mismo PDF, con las mismas reglas, produce el mismo
   resultado.

## Consecuencias

- Nuevo modulo `contenido.py` (`texto_pdf`, `clasificar_por_contenido`) y
  un par de parametros opcionales en el motor `organizar()`: `extractor`
  (inyectable, `None` por defecto) y `max_paginas`. El motor no importa
  `contenido.py`: quien decide es la capa de accion.
- `explicar_match` gana `origen` (`"nombre" | "contenido"`) en su
  diccionario y cada movimiento del resumen/JSON/log lleva el suyo;
  `explicar --contenido` puede explicar por texto (`Fuente: contenido`).
  `aplicar` sigue aprendiendo solo de nombres.
- La confianza del detector por contenido es menor: no abre carpetas donde
  el nombre ya manda, y un PDF escaneado (sin capa de texto) no es un
  error, es un caso previsto que sigue a `_revision`.
- La suite genera sus propios PDFs con `pypdf` en `tmp_path` y se marca
  `skipif` sin el extra: `pip install -e ".[dev]"` incluye `pdf`, la suite
  de CI lo instala y sigue cubriendolo todo.
