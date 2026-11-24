# ADR 002 — Una accion = una clase con fabrica `desde_config`

- **Estado**: Aceptado
- **Fecha**: 2026-11-17
- **Contexto**: refactor v2.3 (Fase 2)

## Contexto

Hasta la v2.2, `cli.py` acumulaba 900 lineas: parser argparse, logica de
cada comando, E/S de consola, persistencia de logs y manejo de errores todo
junto. Anadir un comando implicaba tocar un fichero que ademas mezclaba
cuatro responsabilidades, lo que hacia los cambios arriesgados y dificiles
de probar (para probar "deshacer" habia que capturar stdout).

El enunciado del proyecto pide ademas que "anadir una accion no exija tocar
el codigo" de las demas capas, y una arquitectura con proveedor IA en la
v2.4: el diseno tenia que dejar sitio para acciones nuevas sin rediseñar.

## Decision

Separacion en capas con una clase por comando:

```
cli.py            parser argparse + despacho (sin logica, sin E/S)
acciones/         AccionEjecutar/Revisar/Deshacer/Reglas + registro Acciones
presentacion/     Consola (humano/JSON) y emitir_json/error_json
registro.py       persistencia de logs (clase Registro)
organizador.py    motor puro (clasifica y mueve; sin consola)
reglas.py         clasificador y validacion del JSON del ADR-001
excepciones.py    errores previsibles con mensajes humanos
```

Patrón clave: cada accion define `desde_config(args, consola)` (metodo de
fabrica) que resuelve sus dependencias (reglas efectivas, `Registro`,
opciones) y rechaza configuraciones imposibles (`ErrorDeUso`,
`ConfigError`) **antes** de ejecutar nada. `Acciones.desde_config` es el
  unico registro {nombre → clase}.

## Consecuencias

- Anadir una accion (p. ej. `sugerir` con IA en la v2.4) = 1 modulo nuevo
  con una clase + 1 entrada en `Acciones._IMPLEMENTACIONES`. El parser, el
  motor y la consola no se tocan: el requisito de "anadir una accion no
  exige tocar el codigo (ajeno)" queda estructuralmente cumplido.
- Las dependencias viajan **inyectadas** (`Accion(consola, registro, ...)`)
  y las fabricas `desde_config` son el unico sitio donde se construyen a
  partir de argparse. Probar una accion es instanciarla con una consola
  falsa: sin capturas de stdout.
- Los errores de configuracion salen al construir: un `--ultimos 0` o una
  fecha con formato imposible abortan sin haber leido un solo archivo.
- Costes: 7 modulos en vez de 1 (compensado: cada uno es pequeño y el
  contrato `Accion` es obligatorio via `abc`); la busqueda del registro usa
  un `type: ignore[attr-defined]` acotado (mypy no sabe que el valor del
  dict es una subclase de `Accion`).

## Enmienda (fase 9B): superficie publica de emparejamiento

Una accion propia (`aplicar`) necesita reutilizar el emparejamiento de
`reglas.py` sin duplicarlo. Para que "una accion nueva = una clase" no
implique importar privados, `reglas.py` expone un contrato estable:

- `trocear(nombre) -> tokens` (normalizados, camelCase roto);
- `coincide_token(tokens, alias)` (secuencia de palabras);
- `coincide_pegado(tokens, alias)` (compacto con las reglas anti-falso-
  positivo historicas: 4+ en cualquier extremo, 3 final tras vocal, 2 nunca).

Lo demas (`_partes`, `_pega`, `_coincide`) es interno: `explicar_match` y
`clasificar` siguen siendo la decision del motor. El contrato de
`coincide_pegado` documenta la diferencia fina con `_pega` (tokens
troceados vs compacto del nombre): la publica JAMAS produce un falso
positivo que el motor no produzca; en la otra direccion puede ver mas
(depurado con `test_publicas_y_privadas_no_se_contradicen`). La guia
`docs/como-anadir-una-accion.md` remite a esta superficie.

## Alternativas descartadas

- **Handlers de funcion sueltos** (`def cmd_ejecutar(args)`): menos
  friccion inicial, pero sin sitio natural donde inyectar dependencias ni
  donde colocar una accion con estado (la IA de v2.4 necesitara cliente +
  contexto).
- **Framework de plugins por entry points**: potencia no requerida aqui;
  con un dict explicito el registro es auditable en una linea.
