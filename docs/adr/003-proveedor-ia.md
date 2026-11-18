# ADR 003 — IA extraíble, con clave en el entorno y fallback sin red

- **Estado**: Aceptado
- **Fecha**: 2026-11-18
- **Contexto**: v2.4 (Fase 3)

## Contexto

El proyecto pide acciones de IA y, al mismo tiempo, "sin sorpresas": la
clave no puede acabar en el historial de git ni en un log, y una pérdida de
red no puede dejar la CLI inservible. Ademas el usuario pide herramientas
gratuitas: no se puede dar por supuesto un proveedor de pago.

## Decision

El proveedor vive en `proveedor/` con el mismo patron de fabrica que las
acciones:

```
ProveedorIA.desde_env() -> ProveedorApi | ProveedorHeuristico
```

- `ProveedorApi` usa `urllib` (stdlib), un endpoint compatible con chat
  completions y un modelo definidos por el usuario. No añade dependencias
  ni decide qué servicio usar: si el usuario elige un proveedor gratuito,
  no paga nada.
- `ProveedorHeuristico` reutiliza `reglas.explicar_match`: sin red, sin
  clave o con una respuesta invalida, las acciones siguen devolviendo
  propuestas y explicaciones utiles (`fuente: heuristica`).
- La configuracion se lee de `ORGANIZADOR_API_KEY`,
  `ORGANIZADOR_IA_URL` y `ORGANIZADOR_IA_MODELO`. Se exigen las tres para
  activar HTTP: nadie hace una llamada de pago por dejar una variable suelta.
- Se exige ademas `--confirmar` para `--aplicar`: la IA solo propone; el
  usuario decide. Las propuestas aplicadas escriben un log y se pueden
  deshacer con el comando de siempre.
- `scripts/check_secretos.py` se ejecuta en pre-commit y en CI y rechaza
  patrones de claves conocidos. `.env` esta ignorado; `.env.example` solo
  contiene nombres de variables vacios.

## Consecuencias

- Anadir otra accion de IA es otra clase en `acciones/` + una linea en
  `Acciones`: el proveedor ya esta inyectado y las acciones no importan
  `urllib`.
- Sin internet se puede demostrar la funcionalidad en directo: `sugerir`
  y `explicar` devuelven código 0, avisan por stderr y dejan el JSON limpio
  en stdout.
- Los tests simulan `urlopen`, asi que CI nunca contacta con un servicio
  externo y no necesita claves.
- Costes: hay que validar el JSON de la respuesta de la IA (una sola
  funcion, `_pedir`) y mantener un patron de secretos simple. A cambio no
  hay dependencias nuevas ni riesgo de subir una clave.

## Alternativas descartadas

- **Guardar la clave en `reglas.json`**: romperia el ADR-001 (datos
  compartidos) y la dejaria visible en el repo y en copias del config.
- **Usar la IA como paso obligatorio de `ejecutar`**: mezclaria red,
  pagos y decisiones de movimiento en el camino feliz; el requisito era
  que la clasificacion normal funcionase siempre sin red.
- **Añadir `requests` o `openai`**: util, pero aumenta la instalacion y
  no aporta nada que `urllib` no resuelva en dos metodos.
