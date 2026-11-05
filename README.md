# organizador

CLI que organiza archivos descargados (apuntes, PDFs, enunciados...) en
carpetas por **asignatura** y **tema**, usando únicamente el nombre del
archivo.

```
Organizado/
├── Matematicas/
│   ├── Derivadas/
│   └── Integrales/
├── Historia/
│   └── EdadModerna/
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
organizador ejecutar [origen] [--salida Organizado] [--seco]
```

- `origen`: carpeta con los archivos a organizar (por defecto `./descargas`).
- `--salida`: carpeta de destino (por defecto `./Organizado`).
- `--seco`: solo muestra el resumen final, sin detalle por archivo.

Ejemplo:

```bash
organizador ejecutar descargas
```

Salida:

```
[OK] Mates_Tema_Derivadas_apuntes.pdf -> Matematicas/Derivadas
[OK] Historia apuntes edad moderna.pdf -> Historia/EdadModerna
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
| `Mates_Tema_Derivadas_apuntes.pdf`      | `Matematicas/Derivadas`       |
| `calcul_integral_ejercicios.pdf`        | `Matematicas/Integrales`      |
| `Historia apuntes edad moderna.pdf`     | `Historia/EdadModerna`        |
| `tema_revolucion_industrial_Historia.pdf` | `Historia/RevolucionIndustrial` |
| `Lengua sintaxis ejercicios.docx`       | `Lengua/Sintaxis`             |
| `english phrasal verbs unit 4.pdf`      | `Ingles/PhrasalVerbs`         |
| `Fisica_Tema_Cinematica.pdf`            | `Fisica/Cinematica`           |
| `apuntes_scan_03.pdf`                   | `_revision`                   |

## Añadir asignaturas o temas

Edita `src/organizador/reglas.py` y añade una entrada a `REGLAS`:

```python
Regla(
    "Quimica",                              # asignatura (nombre de carpeta)
    ("quimica", "molecula"),                # palabras clave de asignatura
    (
        ("Formulacion", ("formulacion",)),  # (tema, (palabras clave...))
    ),
),
```

## Pruebas rápidas

```bash
mkdir -p descargas
touch "descargas/Mates_Tema_Derivadas_apuntes.pdf" \
      "descargas/Historia apuntes edad moderna.pdf" \
      "descargas/apuntes_scan_03.pdf"
PYTHONPATH=src python -m organizador ejecutar descargas
```

## Límites de la v1

- No lee el contenido de los PDF ni usa OCR: solo el nombre.
- No hay interfaz gráfica.
- No mueve subcarpetas (solo archivos del primer nivel).
