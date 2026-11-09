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
```

- `origen`: carpeta con los archivos a organizar (por defecto `./descargas`).
- `--salida`: carpeta de destino (por defecto `./Organizado`).
- `--seco`: solo muestra el resumen final, sin detalle por archivo.
- `--simular`: muestra qué haría sin mover ningún archivo.

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
  Destino:             /ruta/al/proyecto/Organizado
```

## Cómo clasifica

1. Normaliza el nombre del archivo (minúsculas, sin tildes, `_`/`-`/`.`
   como separadores).
2. Busca palabras clave de **asignatura** (reglas en
   `src/organizador/reglas.py`).
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

Edita `src/organizador/reglas.py` y añade una entrada a `REGLAS`:

```python
Regla(
    "Digitalizacion",                       # asignatura (nombre de carpeta)
    ("digitalizacion", "digitalitzacio"),   # palabras clave de asignatura
    (
        ("Ofimatica", ("ofimatica",)),      # (tema, (palabras clave...))
    ),
),
```

## Pruebas rápidas

```bash
mkdir -p descargas
touch "descargas/BaseDeDatos_Tema_SQL_apuntes.pdf" \
      "descargas/Programacion java tema 3.pdf" \
      "descargas/apuntes_scan_03.pdf"
PYTHONPATH=src python -m organizador ejecutar descargas --simular
PYTHONPATH=src python -m organizador ejecutar descargas
```

## Límites de la v1

- No lee el contenido de los PDF ni usa OCR: solo el nombre.
- No hay interfaz gráfica.
- No mueve subcarpetas (solo archivos del primer nivel).
