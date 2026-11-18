# Auditoría de pruebas

Resumen ejecutivo de la suite, mapa requisito → prueba → caso feo, sensibilidad a regresiones y límites conocidos. Este documento audita lo que está probado; no promete cobertura total.

## 1. Resumen ejecutivo

| Métrica | Valor |
|---|---|
| Pruebas recopiladas | 148 |
| Resultado | 148 passed, 0 failed, 0 skipped |
| Cobertura global | 94.22 % (1262 sentencias, 73 sin cubrir) |
| Umbral CI | 85 % (`--cov-fail-under=85`) |
| Archivos con cobertura completa | 10 de 23 |
| Tiempo local | ≈ 2.1 s en Python 3.10.12 |
| Prueba más lenta | `test_cli_instalado_json_de_tres_acciones_es_parseable`, ≈ 0.33 s |
| Lint / tipos | `ruff check .`, `ruff format --check .`, `mypy src` limpios |
| Secretos | `scripts/check_secretos.py $(git ls-files)` limpio |
| Matriz CI | Ubuntu 24.04 × Python 3.10, 3.11, 3.12, 3.13 |

Conclusión: la suite cubre los seis comandos, el punto de entrada real, los errores previsibles, el modo JSON, el deshacer, las reglas personalizadas, la IA con fallback y la higiene de credenciales. Dos fallos reales aparecieron durante esta auditoría y quedaron corregidos con regresión (ver §5).

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

Para ver la prueba lenta:

```bash
pytest tests -q --durations=5
```

La suite no necesita red, credenciales reales ni servicios externos. `urlopen` se sustituye por un doble en `tests/test_proveedor.py`; la clave de prueba es `clave-de-prueba-no-real`.

## 3. Cobertura por módulo

| Módulo | Stmts | Miss | Cover | Líneas sin cubrir (interpretación) |
|---|---:|---:|---:|---|
| `acciones/deshacer.py` | 121 | 7 | 94 % | Defensas de log corrupto/formatos inesperados |
| `acciones/ejecutar.py` | 78 | 4 | 95 % | Ramas defensivas de resumen y filtro |
| `acciones/explicar.py` | 45 | 1 | 98 % | Una rama de presentación |
| `acciones/reglas.py` | 20 | 1 | 95 % | Una rama de presentación |
| `acciones/revisar.py` | 135 | 9 | 93 % | EOF/cancelaciones y ramas de interacción |
| `acciones/sugerir.py` | 111 | 4 | 96 % | Aviso IA no configurada y variantes de presentación |
| `cli.py` | 70 | 2 | 97 % | Línea 242 cubierta por subprocess real; 271 es el `if __name__` del módulo |
| `organizador.py` | 158 | 12 | 92 % | Defensas de MOV/formatos raros y `main` delegado |
| `presentacion/consola.py` | 66 | 4 | 94 % | Ramas de confirmación/aviso en errores extraños |
| `proveedor/api.py` | 97 | 8 | 92 % | Validaciones defensivas de respuestas malformadas |
| `proveedor/base.py` | 38 | 1 | 97 % | Método abstracto nunca instanciado |
| `registro.py` | 74 | 11 | 85 % | Rutas relativas, logs corruptos y sobreescritura defensiva |
| `reglas.py` | 149 | 9 | 94 % | Validaciones defensivas de reglas |
| **TOTAL** | **1262** | **73** | **94.22 %** | — |

Nota sobre `cli.py:242`: la línea aparece como no cubierta en el informe de subprocess porque `coverage.py` no instrumenta el intérprete hijo, pero esa rama se ejecuta en `test_cli_instalado_error_json_tiene_codigo_y_objeto_valido` y `test_cli_instalado_aplicar_sin_confirmar_no_toca_archivos`. `cli.py:271` es el guardián `if __name__ == "__main__"`, ejercitado por `runpy` en `test_punto_de_entrada_python_m_devuelve_version`.

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
| Punto de entrada real | `tests/test_cli_end_to_end.py::test_punto_de_entrada_python_m_devuelve_version`, `test_cli_instalado_anuncia_los_seis_comandos` | `python -m organizador` no imprime o no lista `sugerir`/`explicar` |
| Sugerir sin aplicar | `tests/test_acciones_sugerir.py::test_sugerir_muestra_la_propuesta_sin_mover_nada`, `test_sugerir_json_es_valido_y_no_escribe_en_stdout` | `sugerir` mueve archivos sin `--aplicar` |
| Sugerir con aplicar | `tests/test_acciones_sugerir.py::test_aplicar_confirmado_mueve_y_deja_log`, `test_aplicar_sin_confirmar_falla_antes_de_crear_nada`, `test_aplicar_rechazado_no_mueve_nada`, `test_sugerir_aplicado_se_puede_deshacer` | `--aplicar` mueve sin confirmar o deja un log que `deshacer` no puede leer |
| Sugerir casos feos | `test_sin_propuestas_aplicar_no_mueve_ni_escribe_log`, `test_aplicar_sin_tema_mueve_a_la_raiz_de_la_asignatura`, `test_error_al_mover_se_cuenta_en_json`, `test_error_al_escribir_el_log_avisa_y_no_rompe`, `test_sugerir_sin_carpeta_en_humano_avisa`, `test_sugerir_carpeta_vacia_en_humano_avisa` | Error de movimiento se traga; log fallido aborta; carpeta vacía confunde al usuario |
| Explicar | `tests/test_acciones_explicar.py::test_explicar_con_ia_devuelve_la_frase_y_el_destino`, `test_explicar_json_es_valido`, `test_explicar_nombre_sin_reglas_dice_revision`, `test_explicar_con_ia_caida_usa_la_razon_local` | Sin coincidencia se dice "IA"; IA caída rompe el comando |
| Proveedor opcional | `tests/test_proveedor.py::test_desde_env_sin_configuracion_devuelve_el_fallback`, `test_desde_env_necesita_las_tres_variables` | Falta `ORGANIZADOR_IA_URL` y se intenta llamada HTTP |
| Proveedor API | `test_api_sugiere_con_respuesta_valida`, `test_api_descarta_asignatura_inventada_y_cae_al_fallback`, `test_api_con_json_basura_lanza_ia_indisponible`, `test_api_sin_red_lanza_ia_indisponible`, `test_api_acepta_json_entre_backticks`, `test_api_respuesta_sin_choices_lanza_error`, `test_api_sugerencia_ausente_cae_al_fallback`, `test_api_confianza_imposible_usa_la_local` | Asignatura inventada se aplica; JSON con cerca se acepta; red caída tumba la CLI |
| Fallback local | `test_heuristico_sugiere_y_explica_con_reglas_propias`, `test_api_caida_cae_a_heuristicas_y_sigue`, `test_explicar_con_ia_caida_usa_la_razon_local` | Proveedor caído deja de sugerir/explicar |
| Sin fugas de clave | `tests/test_proveedor.py::test_desde_env_con_configuracion_no_revela_la_clave`, `tests/test_secretos.py::test_detecta_una_clave_con_patron_conocido`, `test_detecta_tokens_de_otros_proveedores`, `test_env_example_solo_contiene_nombres_vacios`, e2e con `CLAVE-FALSA-SIN-FORMATO` | `repr`/`str`, stdout o git contienen la credencial |

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

Durante la auditoría aparecieron dos mutaciones reales, no hipotéticas:

1. `AccionSugerir._aplicar` llamaba a `limpiar_vacias(self.salida)`, borrando `_revision` y dejando al log sin capacidad de deshacer. Se eliminó la llamada y se añadió `test_sugerir_aplicado_se_puede_deshacer`.
2. `main()` recibe `argv=None` desde el entry point real; `_detectar_json(None)` devolvía `False`, por lo que los errores de `python -m organizador --json` salían como texto por `stderr`. Se corrigió leyendo `sys.argv[1:]` y se cubrió con dos pruebas end-to-end.

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

- Cobertura 94.22 %, no 100 %. Quedan ramas mayormente defensivas en `registro.py`, `organizador.py` y `proveedor/api.py`.
- No hay mutation testing automatizado; §5 documenta pruebas sensibles a mutaciones concretas, no una puntuación de mutantes.
- No se prueba contra proveedores de IA reales: sería pago, no determinista y contradictorio con las restricciones del proyecto.
- La matriz CI cubre Linux y cuatro versiones de Python; no se prueba Windows ni macOS.
- Los mensajes exactos en humano están cubiertos por fragmentos (`in`), no por comparación byte a byte; la intención es detectar pérdida de información, no congelar redacción.
- Las subprocess e2e dependen de `python -m organizador`, que es precisamente la forma instalable que se quiere auditar; por eso se aceptan ~0.3 s por prueba.

## 9. Veredicto

La combinación de pruebas unitarias de motor, fábricas y reglas; pruebas de acción con dobles; pruebas e2e del invoked real y pruebas de secretos cubre los requisitos funcionales y no funcionales con margen sobre el umbral del 85 %. Los dos defectos encontrados se corrigieron y quedaron con regresión. La suite es apta como base para el release final.
