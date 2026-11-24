# Auditoría de pruebas

Resumen ejecutivo de la suite, mapa requisito → prueba → caso feo, sensibilidad a regresiones y límites conocidos. Este documento audita lo que está probado; no promete cobertura total.

## 1. Resumen ejecutivo

| Métrica | Valor |
|---|---|
| Pruebas recopiladas | 221 |
| Resultado | 221 passed, 0 failed, 0 skipped |
| Cobertura global | 93.04 % (1840 sentencias, 128 sin cubrir) |
| Umbral CI | 85 % (`--cov-fail-under=85`) |
| Archivos con cobertura completa | 10 de 25 (los 10 restantes tienen ≥1 línea) |
| Tiempo local | ≈ 2.1 s en Python 3.10.12 |
| Prueba más lenta | `test_cli_instalado_json_de_tres_acciones_es_parseable`, ≈ 0.33 s |
| Lint / tipos | `ruff check .`, `ruff format --check .`, `mypy src` y `mypy tests` limpios |
| Secretos | `scripts/check_secretos.py $(git ls-files)` limpio |
| Matriz CI | Ubuntu 24.04 (3.10–3.13) + Windows (3.12, 3.13) |

Conclusión: la suite cubre los ocho comandos, el punto de entrada real, los errores previsibles, el modo JSON, el deshacer, las reglas personalizadas, la IA con fallback y la higiene de credenciales. Añadida en la fase de higiene: contrato de versionado (`test_version_de_instalacion_igual_a_la_del_paquete`, `test_version_del_pyproject_es_dinamica`), candado del catálogo empaquetado (`test_catalogo_del_paque_no_esta_corrupto`) y doc sin deriva (`tests/test_docs_readme.py`). Añadida en la fase 7 (`aplicar`): 21 pruebas en `tests/test_acciones_aplicar.py` — inferencia pura (`sugerir_alias`), fusión de reglas, EOF, colisión y deshacer — más el candado de banderas fantasma en el README. Añadida en la fase 7B (`verificar`): 26 pruebas en `tests/test_acciones_verificar.py` — cinco detectores, JSON, códigos de salida, papelera y restauración exacta por `deshacer` (una de ellas, la ruta relativa del log de poda, se corrigió durante la auditoría: ver §5). Dos fallos reales aparecieron durante la auditoría original y quedaron corregidos con regresión (ver §5).

## 2. Cómo reproducir

Desde la raíz del repositorio:

```bash
pip install -e ".[dev]"
ruff check .
ruff format --check .
mypy src
pytest --cov=organizador --cov-report=term-missing --cov-fail-under=85
python3 scripts/check_secretos.py $(git ls-files)
```

El workflow usa `git ls-files -z | xargs -0 ...` (portable en las tres
plataformas); el `pre-commit` local mantiene `entry` por separado para
`mypy src` y `mypy tests`.

Para ver la prueba lenta:

```bash
pytest tests -q --durations=5
```

La suite no necesita red, credenciales reales ni servicios externos. `urlopen` se sustituye por un doble en `tests/test_proveedor.py`; la clave de prueba es `clave-de-prueba-no-real`.

## 3. Cobertura por módulo

| Módulo | Stmts | Miss | Cover | Líneas sin cubrir (interpretación) |
|---|---:|---:|---:|---|
| `acciones/aplicar.py` | 285 | 26 | 91 % | Ramas defensivas de lectura/escritura de JSON, aviso de log y variantes de presentación |
| `acciones/deshacer.py` | 173 | 22 | 87 % | Defensas de restauración y ramas de presentación |
| `acciones/ejecutar.py` | 78 | 4 | 95 % | Ramas defensivas de resumen y filtro |
| `acciones/explicar.py` | 45 | 1 | 98 % | Una rama de presentación |
| `acciones/reglas.py` | 20 | 1 | 95 % | Una rama de presentación |
| `acciones/revisar.py` | 135 | 9 | 93 % | EOF/cancelaciones y ramas de interacción |
| `acciones/sugerir.py` | 111 | 4 | 96 % | Aviso IA no configurada y variantes de presentación |
| `acciones/verificar.py` | 218 | 13 | 94 % | Defensas de IO (hash ilegible, papelera ausente) y ramas de aviso |
| `cli.py` | 86 | 2 | 98 % | Línea 323 cubierta por subprocess real; 352 es el `if __name__` del módulo |
| `organizador.py` | 158 | 12 | 92 % | Defensas de MOV/formatos raros y `main` delegado |
| `presentacion/consola.py` | 66 | 4 | 94 % | Ramas de confirmación/aviso en errores extraños |
| `proveedor/api.py` | 97 | 8 | 92 % | Validaciones defensivas de respuestas malformadas |
| `proveedor/base.py` | 38 | 1 | 97 % | Método abstracto nunca instanciado |
| `registro.py` | 75 | 9 | 88 % | Rutas relativas, logs corruptos y sobreescritura defensiva |
| `reglas.py` | 153 | 12 | 92 % | Validaciones defensivas de reglas |
| **TOTAL** | **1840** | **128** | **93.04 %** | — |

Nota: los otros 10 módulos del paquete (`__init__.py`, `__main__.py`,
`excepciones.py`, `acciones/__init__.py`, `acciones/base.py`,
`acciones/util.py`, `presentacion/__init__.py`,
`presentacion/salida_json.py`, `proveedor/__init__.py`,
`proveedor/heuristico.py`) tienen cobertura completa y `coverage` los
oculta del informe (`skip_covered`); por eso el detalle son 15 líneas
y el total 25 módulos. El escudo público (`scripts/badge.py`) lee el
mismo `line-rate` del XML: 93 %, sin divergencias entre informe y
escudo.

Nota sobre `cli.py:323`: la línea aparece como no cubierta en el informe de subprocess porque `coverage.py` no instrumenta el intérprete hijo, pero esa rama se ejecuta en `test_cli_instalado_error_json_tiene_codigo_y_objeto_valido` y `test_cli_instalado_aplicar_sin_confirmar_no_toca_archivos`. `cli.py:352` es el guardián `if __name__ == "__main__"`, ejercitado por `runpy` en `test_punto_de_entrada_python_m_devuelve_version`.

## 4. Mapa requisito → prueba → caso feo

| Requisito | Prueba representativa | Caso feo que fallaría si se rompe |
|---|---|---|
| Organizar por asignatura/tema | `tests/test_organizador.py::test_organiza_archivo_en_asignatura_y_tema` | Archivo con nombre ambiguo acaba en otra carpeta |
| No sobrescribir | `tests/test_organizador.py::test_no_sobrescribe_y_anade_sufijo` | Colisión de dos `FOL_*` pierde un archivo |
| Simular sin tocar disco | `tests/test_organizador.py::test_simular_no_mueve_ni_crea_carpetas` | `--simular` crea directorios fantasma |
| Ignorar temporales y logs | `tests/test_organizador.py::test_ignora_temporales_y_log` | `~$docx` o `historial.json` se organisan |
| Salida dentro del origen | `tests/test_cli.py::test_cli_salida_dentro_del_origen_devuelve_error` | Bucle infinito reorganizando su propio historial |
| Origen no existente / archivo | `tests/test_organizador.py::test_origen_inexistente_es_error_previsible`, `test_origen_es_un_archivo_no_una_carpeta` | Traceback en lugar de Error 1 |
| Recursivo y filtros | `tests/test_cli.py::test_cli_recursivo`, `test_cli_extension_filtra`, `test_cli_excluir_patron`, `test_cli_extension_coma` | `--recursivo` baja al historial; `--extension` ignora mayúsculas |
| `--desde` | `tests/test_cli.py::test_cli_desde_fecha`, `test_cli_desde_invalido`, `test_cli_recursivo_no_organiza_el_historial` | Fecha inválida mueve archivos; historial se reprocesa |
| Reglas por defecto | `tests/test_reglas.py::test_clasifica_asignaturas`, `test_no_confunde_fol_con_folder`, `test_matching_compacto_sin_falsos_positivos` | `FOL` coincide con `folder`; falso positivo compacto |
| Reglas personalizadas | `tests/test_reglas.py::test_cargar_reglas_personalizadas`, `test_reglas_efectivas_usuario_sobrescribe`, `test_cli_reglas_usuario_autoload` | Regla del usuario pierde ante la interna |
| Reglas corruptas | `tests/test_reglas.py::test_cargar_reglas_json_invalido`, `test_cargar_reglas_valida_campos`, `test_todo_error_de_reglas_es_organizador_error` | JSON roto se convierte en `TypeError` |
| Revisar interactivo | `tests/test_cli.py::test_cli_revisar`, `test_cli_revisar_interactivo`, `test_cli_revisar_interactivo_eof`, `test_cli_revisar_acepta_sugerencia` | EOF produce traceback; aceptar no mueve |
| Confirmar / rechazar | `tests/test_cli.py::test_cli_confirmar_si`, `test_cli_confirmar_no`, `test_cli_confirmar_json`, `test_cli_confirmar_eof` | Respuesta `n` mueve archivos; modo JSON imprime texto plano |
| Deshacer | `tests/test_organizador.py::test_deshacer_devuelve_archivos_al_origen`, `test_deshacer_no_sobrescribe`, `tests/test_cli.py::test_cli_deshacer_ultimos` | Log inválido borra archivos; `--ultimos` elige el log viejo |
| Logs corruptos | `tests/test_cli.py::test_cli_deshacer_log_invalido`, `test_cli_deshacer_log_invalido_json_es_json_valido`, `test_cli_deshacer_historial_corrupto_no_rompe_el_bucle` | Un mal JSON detiene el bucle de historial |
| Fabrica de acciones | `tests/test_acciones.py::test_desde_config_devuelve_la_accion_de_cada_nombre`, `test_desde_config_con_accion_inventada_falla_al_construir`, `test_desde_config_no_monta_las_demas_acciones` | Acción inventada llega a ejecutar; se construyen las seis acciones |
| Fallos antes de tocar disco | `tests/test_acciones.py::test_fecha_invalida_falla_antes_de_tocar_el_disco`, `test_reglas_corruptas_falla_antes_de_cualquier_effeto` | Config inválida mueve un archivo antes de fallar |
| Modo JSON | `tests/test_cli.py::test_cli_json_ejecutar`, `test_cli_json_revisar`, `test_cli_error_en_modo_json_es_objeto_valido`, `tests/test_cli_end_to_end.py::test_cli_instalado_error_json_tiene_codigo_y_objeto_valido` | `stdout` contiene texto no parseable o `stderr` contamina el JSON |
| Códigos de salida | `tests/test_cli.py::test_cli_accion_desconocida_devuelve_2`, `test_cli_deshacer_ultimos_cero_es_error_de_uso`; e2e de error y de `--aplicar` sin `--confirmar` | Script interpreta éxito donde hubo error de uso |
| Punto de entrada real | `tests/test_cli_end_to_end.py::test_punto_de_entrada_python_m_devuelve_version`, `test_cli_instalado_anuncia_los_ocho_comandos` | `python -m organizador` no imprime o no lista `sugerir`/`explicar` |
| Sugerir sin aplicar | `tests/test_acciones_sugerir.py::test_sugerir_muestra_la_propuesta_sin_mover_nada`, `test_sugerir_json_es_valido_y_no_escribe_en_stdout` | `sugerir` mueve archivos sin `--aplicar` |
| Sugerir con aplicar | `tests/test_acciones_sugerir.py::test_aplicar_confirmado_mueve_y_deja_log`, `test_aplicar_sin_confirmar_falla_antes_de_crear_nada`, `test_aplicar_rechazado_no_mueve_nada`, `test_sugerir_aplicado_se_puede_deshacer` | `--aplicar` mueve sin confirmar o deja un log que `deshacer` no puede leer |
| Sugerir casos feos | `test_sin_propuestas_aplicar_no_mueve_ni_escribe_log`, `test_aplicar_sin_tema_mueve_a_la_raiz_de_la_asignatura`, `test_error_al_mover_se_cuenta_en_json`, `test_error_al_escribir_el_log_avisa_y_no_rompe`, `test_sugerir_sin_carpeta_en_humano_avisa`, `test_sugerir_carpeta_vacia_en_humano_avisa` | Error de movimiento se traga; log fallido aborta; carpeta vacía confunde al usuario |
| Explicar | `tests/test_acciones_explicar.py::test_explicar_con_ia_devuelve_la_frase_y_el_destino`, `test_explicar_json_es_valido`, `test_explicar_nombre_sin_reglas_dice_revision`, `test_explicar_con_ia_caida_usa_la_razon_local` | Sin coincidencia se dice "IA"; IA caída rompe el comando |
| Proveedor opcional | `tests/test_proveedor.py::test_desde_env_sin_configuracion_devuelve_el_fallback`, `test_desde_env_necesita_las_tres_variables` | Falta `ORGANIZADOR_IA_URL` y se intenta llamada HTTP |
| Proveedor API | `test_api_sugiere_con_respuesta_valida`, `test_api_descarta_asignatura_inventada_y_cae_al_fallback`, `test_api_con_json_basura_lanza_ia_indisponible`, `test_api_sin_red_lanza_ia_indisponible`, `test_api_acepta_json_entre_backticks`, `test_api_respuesta_sin_choices_lanza_error`, `test_api_sugerencia_ausente_cae_al_fallback`, `test_api_confianza_imposible_usa_la_local` | Asignatura inventada se aplica; JSON con cerca se acepta; red caída tumba la CLI |
| Fallback local | `test_heuristico_sugiere_y_explica_con_reglas_propias`, `test_api_caida_cae_a_heuristicas_y_sigue`, `test_explicar_con_ia_caida_usa_la_razon_local` | Proveedor caído deja de sugerir/explicar |
| Sin fugas de clave | `tests/test_proveedor.py::test_desde_env_con_configuracion_no_revela_la_clave`, `tests/test_secretos.py::test_detecta_una_clave_con_patron_conocido`, `test_detecta_tokens_de_otros_proveedores`, `test_env_example_solo_contiene_nombres_vacios`, e2e con `CLAVE-FALSA-SIN-FORMATO` | `repr`/`str`, stdout o git contienen la credencial |
| Version con una sola fuente | `tests/test_cli.py::test_version_de_instalacion_igual_a_la_del_paquete`, `test_version_del_pyproject_es_dinamica` | Alguien fija `version` en el TOML y el `--version` instalado diverge del módulo |
| Escudo de cobertura | `tests/test_badge.py::test_porcentaje_y_color_bueno`, `test_por_debajo_del_umbral_en_rojo`, `test_xml_roto_es_error_de_cl` | El badge miente (verde con <85 %) o el workflow revienta con un XML inesperado |
| Catalogo de reglas empaquetado | `tests/test_reglas.py::test_catalogo_del_paque_no_esta_corrupto`, `test_cada_asignatura_del_catalogo_se_detecta_por_su_nombre` | Alias vacio o duplicado en `reglas.json` rompe la clasificacion sin romper tests de logica |
| Doc sin deriva | `tests/test_docs_readme.py::test_readme_documenta_el_comando`, `test_parser_expone_los_comandos_del_readme`, `test_readme_no_promete_variables_de_entorno_inexistentes`, `test_readme_no_documenta_banderas_fantasma` | Comando nuevo sin documentar, env var fantasma o bandera inventada en el README |
| Aplicar (aprender alias) | `tests/test_acciones_aplicar.py::test_propone_alias_largo_tras_asignatura`, `test_token_generico_no_propone_nada`, `test_unico_token_corto_no_propone`, `test_empate_entre_asignaturas_no_propone`, `test_alias_de_tema_cuenta_como_evidencia` | Alias inventado a partir de `tema3`, `x2` o tokens cortos; `poo` propuesto pese a ser variante de `pseudocodigo` |
| Aplicar (confirmar/guardar) | `test_propuesta_sin_confirmar_no_toca_reglas_ni_mueve`, `test_confirmar_guarda_alias_fusionando_con_previas`, `test_rechazar_no_escribe_nada`, `test_eof_a_mitad_no_escribe_nada`, `test_aplicar_con_reglas_propias_guarda_en_el_mismo_fichero` | `aplicar` escribe sin preguntar; el EOF a mitad deja reglas a medias; `--reglas` guarda fuera del fichero del usuario |
| Aplicar (reorganizar) | `test_reorganizar_mueve_con_alias_nuevos_y_deja_log_deshacible`, `test_reorganizar_respeta_el_sufijo_anti_colision`, `test_seco_solo_imprime_resumen`, `test_json_de_aplicar_es_valido`, `test_sin_carpeta_revision_json_valido_y_codigo_cero` | `deshacer` no revierte el `--reorganizar`; colisión de destinos pisa un archivo; JSON roto o stdout sucio |
| Verificar (detectores) | `tests/test_acciones_verificar.py::test_duplicados_detectados_por_hash`, `test_subproducto_de_navegador`, `test_vacias_y_fuera_catalogo`, `test_atrapados_en_raiz_de_asignatura`, `test_revision_reporta_aplicar_y_sugerir` | Un `cp -p` pasa por archivo único; `doc (1).pdf` no se reporta; carpeta inventada se traga el resumen |
| Verificar (códigos y JSON) | `test_salida_limpia_devuelve_cero`, `test_confirmar_sin_podar_es_error_de_uso`, `test_json_valido_y_con_estructura`, `test_podar_json_sin_confirmar_avisa_y_no_mueve`, `test_ignora_papelera_y_logs` | Un script recibe rc=0 con hallazgos; `--confirmar` solo poda; stdout JSON con ruido |
| Verificar (papelera) | `test_podar_conserva_primera_y_va_a_papelera`, `test_podar_sin_confirmar_no_toca_nada`, `test_podar_eof_no_toca_nada`, `test_podar_con_nombre_repetido_usa_sufijo`, `test_deshacer_historial_reviente_poda_y_purga`, `test_papelera_queda_vacia_tras_deshacer`, `test_deshacer_simular_no_toca_papelera_ni_copia` | La poda se come el log o la copia; `deshacer` restaura a la raíz en vez de la carpeta; la simulación destruye |

## 5. Sensibilidad a regresiones

No se añadió una librería de mutation testing: el proyecto se mantiene solo con dependencias de desarrollo ya presentes. En su lugar se verificó sensibilidad con mutaciones razonadas: cambios deliberados que la suite detecta de inmediato.

| Mutación hipotética | Prueba que la mata |
|---|---|
| `_detectar_json(argv)` vuelve a ignorar `sys.argv` | `test_cli_instalado_error_json_tiene_codigo_y_objeto_valido` y `test_cli_instalado_aplicar_sin_confirmar_no_toca_archivos` |
| `AccionSugerir._aplicar` limpia `_revision` tras mover | `test_sugerir_aplicado_se_puede_deshacer` |
| `ProveedorApi.__repr__` muestra la clave | `test_desde_env_con_configuracion_no_revela_la_clave` |
| `mover_archivo` usa `shutil.move` sin control de colisión | `test_no_sobrescribe_y_anade_sufijo` |
| `_primera_coincidencia` busca subcadenas cortas sin límite | `test_no_confunde_fol_con_folder`, `test_matching_compacto_sin_falsos_positivos` |
| `Acciones.desde_config` construye todas las acciones | `test_desde_config_no_monta_las_demas_acciones` |
| `ProveedorApi` acepta `choices=[]` | `test_api_respuesta_sin_choices_lanza_error` |
| El scanner anti-claves pierde un proveedor | `test_detecta_tokens_de_otros_proveedores` |
| `.env.example` incluye un valor de ejemplo no vacío | `test_env_example_solo_contiene_nombres_vacios` |

Durante la auditoría aparecieron mutaciones reales, no hipotéticas:

1. `AccionSugerir._aplicar` llamaba a `limpiar_vacias(self.salida)`, borrando `_revision` y dejando al log sin capacidad de deshacer. Se eliminó la llamada y se añadió `test_sugerir_aplicado_se_puede_deshacer`.
2. `main()` recibe `argv=None` desde el entry point real; `_detectar_json(None)` devolvía `False`, por lo que los errores de `python -m organizador --json` salían como texto por `stderr`. Se corrigió leyendo `sys.argv[1:]` y se cubrió con dos pruebas end-to-end.
3. (fase 7B) El log de poda guardaba la ruta original tal cual: con `--salida` relativo el destino quedaba relativo y `deshacer` no encontraba la papelera. Se corrigió resolviendo `--logs-dir` a absoluto en `verificar` (el motor siempre guarda absolutos) y el caso quedó cubierto por `test_podar_conserva_primera_y_va_a_papelera` y `test_deshacer_poda_json_valido`.

## 6. Aislamiento y determinismo

- Cada prueba usa `tmp_path`; no hay archivos compartidos ni estado global persistente.
- `monkeypatch` aísla `os.environ`, `sys.argv`, `Path.cwd`, `urlopen` y funciones de movimiento.
- Las subprocess de `tests/test_cli_end_to_end.py` limpian `ORGANIZADOR_*` del entorno y fuerzan `PYTHONPATH=src`.
- No se usa red, reloj real para decidir asignaturas ni entrada interactiva del usuario: las confirmaciones son dobles.
- Los nombres de clave de prueba no siguen patrones de proveedores reales, para no activar el propio scanner.

## 7. Seguridad

- El scanner revisa todo `git ls-files` en pre-commit y en CI: `sk-`, `ghp_`, `github_pat_`, `AIza`.
- `.env` y `.env.*` están ignorados; `.env.example` solo declara tres variables vacías.
- La CLI no lee `.env`: las credenciales llegan solo por entorno explícito.
- `ProveedorApi` guarda la clave como atributo privado y la oculta en `repr`/`str`; las pruebas e2e buscan la clave falsa y cabeceras `Bearer`/`Authorization` en `stdout` y `stderr`.
- Las respuestas de IA se validan antes de aplicar: se descartan asignaturas fuera del catálogo, confianzas fuera de rango y formatos de JSON inesperados; ante duda se usa la heurística local.

## 8. Limitaciones honestas

- Cobertura 93.04 %, no 100 %. Quedan ramas mayormente defensivas en `registro.py`, `organizador.py`, `acciones/aplicar.py` y `proveedor/api.py`.
- No hay mutation testing automatizado; §5 documenta pruebas sensibles a mutaciones concretas, no una puntuación de mutantes.
- No se prueba contra proveedores de IA reales: sería pago, no determinista y contradictorio con las restricciones del proyecto.
- La matriz CI cubre Linux (3.10–3.13) y Windows (3.12/3.13). macOS no se prueba: los runners `macos-*` de GitHub no están disponibles para cuentas gratuitas (los jobs se cancelan sin pasos); se prefiere honestidad a cobertura fingida.
- Los mensajes exactos en humano están cubiertos por fragmentos (`in`), no por comparación byte a byte; la intención es detectar pérdida de información, no congelar redacción.
- Las subprocess e2e dependen de `python -m organizador`, que es precisamente la forma instalable que se quiere auditar; por eso se aceptan ~0.3 s por prueba.
- El README y `RELEASES.md` se auditan con el contrato `tests/test_docs_readme.py`: ocho comandos documentados y sin banderas inventadas. La etiqueta `v1.1` (versión definitiva, paquete 2.5.0) mantiene la cronología: `v1.0` fue la entrega final con seis comandos; los dos nuevos
se publican como mejora menor dentro de la misma línea `2.x` del paquete.

## 9. Veredicto

La combinación de pruebas unitarias de motor, fábricas y reglas; pruebas de acción con dobles; pruebas e2e del invoked real y pruebas de secretos cubre los requisitos funcionales y no funcionales con margen sobre el umbral del 85 %. Los dos defectos encontrados se corrigieron y quedaron con regresión. La suite es apta como base para el release final.
