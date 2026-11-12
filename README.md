# organizador

CLI que organiza archivos descargados (apuntes, PDFs, enunciados...) en
carpetas por **asignatura** y **tema**, usando únicamente el nombre del
archivo.

```
Organizado/
├── BaseDeDatos/
│   ├── SQL/
│   └── Normalizacion/
├── Programacion/
│   └── Java/
└── _revision/          # lo que no se pudo clasificar
```

## Requisitos

- Python 3.8+

## Instalación

```bash
pip install .
```

También puedes ejecutarla sin instalar nada:

```bash
PYTHONPATH=src python -m organizador ejecutar descargas
```

## Uso

```bash
organizador ejecutar [origen] [--salida Organizado] [--seco] [--simular]
                     [--recursivo] [--extension EXT] [--excluir PATRON]
                     [--desde YYYY-MM-DD] [--confirmar] [--json]
                     [--log ruta.json | --logs-dir carpeta] [--reglas ruta.json]
organizador revisar [--salida Organizado] [--interactivo] [--json]
                    [--reglas ruta.json]
organizador deshacer [--logs-dir carpeta] [--ultimos N] [--listar]
                     [--simular] [--json] [--log ruta.json]
organizador reglas [--reglas ruta.json]
organizador --version
```

- `origen`: carpeta con los archivos a organizar (por defecto `./descargas`).
- `--salida`: carpeta de destino (por defecto `./Organizado`).
- `--seco`: solo muestra el resumen final, sin detalle por archivo.
- `--simular`: muestra qué haría sin mover ningún archivo.
- `--recursivo`: recorre también las subcarpetas del origen (omite carpetas
  ocultas y el historial de logs).
- `--extension`: solo procesa esas extensiones (`--extension pdf` o
  `--extension pdf,docx`; repetible).
- `--excluir`: no procesa nombres que casen con un patrón glob
  (`--excluir "*borrador*"`; repetible).
- `--desde`: solo procesa archivos modificados desde esa fecha
  (`YYYY-MM-DD`).
- `--confirmar`: muestra el plan y pide confirmación antes de mover.
- `--json`: emite el resultado en JSON (sin salida humana), útil para
  scripts.
- `--reglas`: fichero de reglas a usar (sustituye a las del paquete).
- `--log`: guarda un único log en esa ruta.
- `--logs-dir`: carpeta del historial de logs (por defecto
  `./organizador-logs`). Cada ejecución crea un `<fecha>.json`.
- `revisar`: lista los archivos de `Organizado/_revision`.
- `revisar --interactivo`: sugiere asignatura y tema a partir del nombre;
  Enter acepta la sugerencia, `-` quita el tema y `q` termina. Si el nombre
  no existe en las reglas, pregunta si quieres crearlo. Si se cancela la
  entrada (Ctrl+D/EOF) no se pierde nada.
- `deshacer`: revierte el último log del historial. Con `--ultimos N`
  revierte los N más recientes. `--listar` muestra el historial sin revertir
  y `--simular` previsualiza el deshacer sin mover ni borrar logs. También
  limpia las carpetas vacías y devuelve código de error si algún archivo no
  se puede devolver.
- `reglas`: muestra las asignaturas y temas disponibles.
- `--version`: muestra la versión instalada.

El log solo se escribe cuando la ejecución mueve archivos o registra
errores. El historial vive en una carpeta, así que no se organiza por error.

### Reglas personalizadas

Puedes añadir o sobrescribir asignaturas sin tocar el paquete creando
`~/.config/organizador/reglas.json` (o `$XDG_CONFIG_HOME/organizador/reglas.json`)
con el mismo formato que `src/organizador/reglas.json`. Las reglas del
usuario tienen prioridad y se fusionan con las del paquete.

Con `--reglas ruta.json` se usan **solo** las reglas de ese fichero, lo que
resulta útil para probar configuraciones o usar un juego distinto.

Ejemplo:

```bash
organizador ejecutar descargas
```

Salida:

```
[OK] BaseDeDatos_Tema_SQL_apuntes.pdf -> BaseDeDatos/SQL
[OK] Programacion java tema 3.pdf -> Programacion/Java
[?] apuntes_scan_03.pdf -> _revision/

Resumen
  Archivos procesados: 3
  Organizados:         2
  A revisar:           1
  Errores:             0
  Filtrados:           0
  Destino:             /ruta/al/proyecto/Organizado
```

## Cómo clasifica

1. Normaliza el nombre del archivo (minúsculas, sin tildes, `_`/`-`/`.`
   como separadores) y separa camelCase (`BaseDeDatos`).
2. Busca palabras clave de **asignatura** (reglas en
   `src/organizador/reglas.json`). Las palabras cortas (`ip`, `er`, `bd`)
   deben aparecer completas; las largas también valen pegadas al nombre
   (`trabajosql`, `GithubApuntes`).
3. Si encuentra además palabras clave de **tema**, lo mueve a
   `Organizado/Asignatura/Tema`; si solo detecta la asignatura, a
   `Organizado/Asignatura`.
4. Si no detecta ninguna asignatura, lo mueve a `Organizado/_revision`.
5. Nunca sobreescribe: si el destino ya existe, añade `-1`, `-2`, ...

### Ejemplos de nombres de archivo

| Nombre                                  | Destino                       |
| --------------------------------------- | ----------------------------- |
| `BaseDeDatos_Tema_SQL_apuntes.pdf`      | `BaseDeDatos/SQL`             |
| `base_de_datos_normalizacion.pdf`       | `BaseDeDatos/Normalizacion`   |
| `Programacion_java_tema_3.pdf`          | `Programacion/Java`           |
| `SistemasInformaticos_redes.pdf`        | `SistemasInformaticos/Redes`  |
| `EntornosDeDesarrollo_git.pdf`          | `EntornosDeDesarrollo/Git`    |
| `FOL_nomina.pdf`                        | `FOL/Nomina`                  |
| `english phrasal verbs unit 4.pdf`      | `Ingles/PhrasalVerbs`         |
| `IPE_curriculo.pdf`                     | `IPE/Curriculo`               |
| `LlenguatgeDeMarques_html.pdf`          | `LlenguatgeDeMarques/HTML`    |
| `apuntes_scan_03.pdf`                   | `_revision`                   |

## Añadir asignaturas o temas

Edita `src/organizador/reglas.json` y añade un objeto a la lista:

```json
{
  "asignatura": "Digitalizacion",
  "aliases": ["digitalizacion", "digitalitzacio"],
  "temas": [
    { "tema": "Ofimatica", "aliases": ["ofimatica"] }
  ]
}
```

El orden importa: la primera regla que coincide gana. `reglas.py` valida el
JSON al arrancar y muestra un error claro si falta algún campo o hay
asignaturas duplicadas.

## Pruebas rápidas

```bash
mkdir -p descargas
touch "descargas/BaseDeDatos_Tema_SQL_apuntes.pdf" \
      "descargas/Programacion java tema 3.pdf" \
      "descargas/apuntes_scan_03.pdf"
PYTHONPATH=src python -m organizador ejecutar descargas --simular
PYTHONPATH=src python -m organizador ejecutar descargas
```

## Tests

```bash
pip install -e ".[dev]"
pytest
```

## Calidad

```bash
ruff check .
ruff format --check .
mypy src
pytest --cov=organizador --cov-report=term-missing
pre-commit install
pre-commit run --all-files
```

La CI ejecuta `ruff`, `mypy` y los tests con cobertura mínima del 85% en
Python 3.10–3.13.

## Límites

- No lee el contenido de los PDF ni usa OCR: solo el nombre.
- No hay interfaz gráfica.
- Sin `--recursivo` solo procesa los archivos del primer nivel.
