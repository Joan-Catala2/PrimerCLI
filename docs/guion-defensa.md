# Guion de defensa (fase 9.5)

Doce respuestas cortas para defender el proyecto en vivo. Cada afirmacion
lleva `archivo:linea` para poder abrir el codigo delante del evaluador.
Orden pensado para una defensa de 15-20 minutos: arquitectura, pruebas
duras, errores, IA, contenido, cierre con las preguntas trampa.

## 1. Como se anade una accion y por que no toca el nucleo

`docs/como-anadir-una-accion.md`: 1 clase en `acciones/`, 1 linea en
`_IMPLEMENTACIONES` (`acciones/__init__.py:30-39`) y 1 subparser en
`cli.py:_construir_parser`. El contrato obligatorio (`abc`) es
`acciones/base.py:22-38`: toda accion implementa `desde_config` y
`ejecutar`. Prueba de que es de verdad: las fases 7/7B/8/9 anadieron
comandos sin tocar el motor, y el candado
`tests/test_acciones.py:70` (recorre el diccionario) revienta si una
accion nueva no esta registrada. El "porque" esta en el ADR-002.

## 2. `desde_config`: valida antes de tocar disco

`ejecutar.py:44-62`: en la fabrica se resuelven reglas, registro y filtros,
y `--contenido-max-paginas 0` lanza `ErrorDeUso` sin haber leido un solo
archivo. Lo congela `tests/test_acciones.py:94`
(`test_fecha_invalida_falla_antes_de_tocar_el_disco`). La razon de ser:
un error de config no puede tener efectos parciales; la fabrica es el unico
lugar donde existen las dependencias y el primero donde pueden fallar.

## 3. Las 5 aserciones duras de la suite (explicar cada una)

- `tests/test_acciones_verificar.py:300`
  (`test_deshacer_poda_json_valido`): poda con `--podar --confirmar --json`
  (el stdout debe ser un unico JSON parseable, no JSON + texto), luego
  `deshacer --log --json`: una copia devuelta (`len(deshechos)==1`) y cero
  errores. Prueba que la poda deja ruta absoluta en el log (el bug real
  que se corrigio en la fase 7B, auditoria §5).
- `tests/test_acciones_sugerir.py:190`
  (`test_sugerir_aplicado_se_puede_deshacer`): IA sugerida + aplicada, y
  `deshacer` devuelve el archivo a `_revision` y lo comprueba
  (`is_file()`). Mata la regresion que borro `_revision` tras mover: si el
  log no sobrevive, el undo es imposible (auditoria §5, mutacion real 1).
- `tests/test_acciones_aplicar.py:188`
  (`test_eof_a_mitad_no_escribe_nada`): confirmacion alias a alias con EOF
  a mitad: codigo 0 y el fichero de reglas del usuario NO existe. Aceptar
  dos alias a medias dejaria reglas corruptas; el contrato es todo o nada
  (no deja el JSON a medias).
- `tests/test_organizador.py:84`
  (`test_ignora_temporales_y_log`): `.part`, `.DS_Store`, `~$docx` y el
  log propio no se mueven y `Organizado/` ni se crea
  (`not salida.exists()`). Si la CLI moviera el historial a `_revision`,
  `deshacer` se comeria su propio rastro.
- `tests/test_reglas.py:40`
  (`test_no_confunde_fol_con_folder`): `folder_apuntes.pdf` no es FOL. El
  compacto (`_pega`) solo vale al principio/final con alias >=4 letras, y
  de 3 solo tras vocal (`trabajosql` si, `digit` no): son las reglas
  historicas de falsos positivos, ahora publicas con contrato en
  (enmienda ADR-002). La superficie publica se llama `coincide_pegado`.

## 4. Excepciones propias y codigos de salida estables

Jerarquia en `excepciones.py`: todo previsible es `OrganizadorError` con
`codigo_salida` (1 error, 2 mal uso — `AccionNoValida/ErrorDeUso:25`, y el
especial 130 por cancelacion en `revisar`). `cli.py:main` (352-373) captura
`OrganizadorError` e imprime solo el mensaje humano: sin traceback, sin
`sys.exit()` salvaje, codigo coherente. Y desde el ultimo corte, `Ctrl+C` en cualquier prompt tiene paraguas en `main`
(`cli.py`, `except KeyboardInterrupt`): mensaje corto, codigo 130, stdout intacto
en modo JSON — las pruebas van de la inyeccion (`test_interrupcion.py`) al SIGINT
real por senal del SO sobre un subproceso. Desde el cierre hay un caso mas de
error previsible con clase propia: `ErrorDeSistema`
(`excepciones.py`), que `escaneo.py` lanza cuando una carpeta no se puede leer
(origen, `_revision`, logs...): antes salia como `PermissionError` con traceback; ahora
es `Error:` humano con codigo 1, y con `--recursivo` una subcarpeta ilegible solo
produce un aviso y la pasada continua (`tests/test_escaneo.py`). Un bug real si saca traceback
(deliberado: eso es un defecto, no un caso de usuario)(`revisar`). Prueba: `test_cli.py` (rc 2 con accio inventada), y el e2e
`test_cli_instalado_error_json_tiene_codigo_y_objeto_valido`: `main` recibe
`argv=None` y `_detectar_json` (340-351) lee `sys.argv[1:]` — la causa del
bug real 2 de la auditoria §5 (errores en modo JSON salian como texto).

## 5. `afirmar` y no `assert`

`excepciones.py:52-69`: un `assert` muere con `python -O`, y una invariante
del motor que desaparece en produccion es peor que no tenerla: el estado
roto pasaria en silencio. `afirmar` lanza `OrganizadorError` SIEMPRE (con
prefixo "Error interno"), y la CLI lo muestra igual que un error humano.
El motor lo usa donde romper silencioso es inaceptable (p. ej. el resumen
debe cuadrar con archivos vistos, `organizador.py:273`), no para
validaciones de usuario (esas son `ErrorDeUso`/`ConfigError`, con codigo
propio).

## 6. Arquitectura: capas y fabricas

`cli.py` (parser + despacho, cero logica), `acciones/` (una clase por
comando, registro explicito), `organizador.py` (motor puro: clasifica y
mueve, sin E/S de consola ni argparse), `presentacion/` (unica capa que
imprime), `registro.py` (historial), `proveedor/` (IA detras de interfaz),
`contenido.py` (lector difera). Visibilidad cuidada: `contenido` usa la
API publica de `reglas.py` (enmienda ADR-002); `aplicar` ya no importa
privados. Las fabricas estaticas (`desde_config` en acciones, consola y
registro; `desde_env` en IA) centralizan "construir con lo que hay".

## 7. IA: 2 acciones, opt-in, sin red se explica y sigue

`sugerir` y `explicar`. Se activa solo con las 3 variables
(`ORGANIZADOR_API_KEY/URL/MODELO`, ADR-003): sin ellas, `desde_env()`
devuelve el heuristico local y el aviso sale por stderr; con red caida o
JSON basura, `IAIndisponible` se captura y se usa la razon local
(`tests/test_acciones_sugerir.py:149` y `tests/test_acciones_explicar.py`).
Claves: nunca en el repo ni en logs ni en `repr` (el `test_proveedor`
busca la clave falsa por stdout/stderr, y `test_secretos.py:64` fuerza
`.env.example` a declarar solo nombres vacios). Las respuestas de IA se
validan (asignatura del catalogo, confianza en rango) y ante duda gana la
heuristica: el proveedor no manda.

## 8. Sin efectos sorpresa: simular, confirmar, deshacer

Nada destructivo sin red de seguridad: `--simular` (plan exacto, sin tocar
disco), `--confirmar` (plan + si/no; EOF = no, `test_eof_a_mitad_no_escribe_nada`
y `revisar --interactivo`), y `deshacer` sobre log JSON — tambien para la
poda de `verificar --podar`, que no borra: papelera con log `restaurar`.
La regla de diseno: si una accion puede destruir, ofrece antes ver o anular
(el log de `ejecutar` se escribe incluso en cancelacion parcial).

## 9. `--contenido`: que hace y por que el nombre manda

ADR-006 y ADR-007: opt-in (`ejecutar/revisar/explicar --contenido`), segunda
pasada solo para lo que iria a `_revision` (un PDF o DOCX cuyo nombre
clasifica no se abre — `test_el_nombre_manda...` lo demuestra con extractor
que petaria). Fronteras de palabra (`mysql` no activa `sql`) y alias de 1-2
letras fuera: en texto continuo son ruido. Cada lector es extra con import
diferido: `.[pdf]` (`pypdf`) o `.[docx]` (`python-docx`); sin el extra, error
humano con su comando de instalacion (`contenido.py:_leer_pdf` y
`_leer_docx`; dobles en `test_contenido.py` y `test_docx.py`). Un documento
corrupto, cifrado o escaneado: aviso por stderr y `_revision`, nunca
traceback. `texto_documento` despacha por extension y las tres fabricas
inyectan esa unica funcion. Y `explicar --contenido` lo dice honesto:
`Fuente: contenido`.

## 10. Instalacion y release

README: `pip install .` (o `.[pdf]`, `.[docx]`, `.[pdf,docx]`), y
`PYTHONPATH=src python -m organizador` sin instalar. Releases etiquetadas
`v1.0`..`v1.4.3` con CHANGELOG, GitHub Releases con sdist+wheel construidos
por CI (no PyPI:
sin servicios externos, artefactos verificables). CI: matriz Ubuntu
3.10-3.13 + Windows 3.12/3.13, ruff, mypy (src+tests), secretos, build
strict, badge self-hosted. `--version` y metadatos del paquete salen del
mismo `__version__` (contrato en `test_cli.py:148`).

## 11. El ciclo del log (de donde sale `deshacer`)

Cada ejecucion real escribe un JSON (`registro.guardar_historial`) con
movimientos + errores + origen de clasificacion; la ruta va en el resumen.
`deshacer` lee el historial (`--ultimos`), restaura con sufijo anti-colision,
purga papelera vacia y no borra el log si algo falla (queda el rastro).
Logs corruptos: ese log se salta con aviso, el resto del historial sigue
(`test_cli_deshacer_log_invalido*`). La poda escribe UN log con marca
`restaurar`: `deshacer` lo entiende espejo (ruta original exacta) — es el
unico destructor reversible de la CLI.

## 12. Preguntas trampa

- "Por que argparse y no Click/Typer?" — Stdlib puro: cero dependencias en
  el core (contrato del proyecto). El parser ya esta testado (candados de
  banderas fantasma) y las acciones aisan la logica: un cambio de framework
  tocari solo `cli.py`.
- "Por que no publicais en PyPI?" — Decision de alcance: artefactos en
  GitHub Releases (instalables con `pip install <whl>`), sin cuentas ni
  servicios. Si algun dia, el job `build` ya esta hecho.
- "Cuantas lineas de test hay y que no cubren?" — 305 rapidas + 1 lenta,
  93.45 %. No cubren: defensas de IO imposibles de disparar sin root, la
  fidelidad de `extract_text` de `pypdf` y la instalacion aislada del extra
  `[docx]` en el sdist (su `lxml` no se puede prestar sin red). Limite
  honesto: auditoria §8 y ADR-007.
- "El proyecto es tuyo?" — Todo el codigo y su justificacion (7 ADRs) en el
  historial con PRs #1-#23; las decisiones importantes estan razonadas en
  docs, no magicas.

## Como ensayar

Lee cada seccion en voz alta 2 veces; despues, sin abrir el doc, responde
las 12 desde el repo (abriendo los `archivo:linea`). Las preguntas 3, 4, 5
y 12 son las que mas se repiten en tribunales: llevatelas memorizadas.
