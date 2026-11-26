"""Accion `aplicar`: aprende alias de tus correcciones en `_revision`.

Cuando un archivo cae en `_revision`, la CLI no aprende nada: la proxima
vez repetira el fallo. `aplicar` cierra ese ciclo en tres fases, siempre
deterministas y sin proveedor externo:

1. **Proponer** (por defecto): analiza los nombres de `_revision`, deduce
   que token(es) desconocido(s) apuntan a que asignatura (mayoria de
   evidencias entre asignaturas candidatas) y muestra la tabla. No toca el
   disco.
2. **Confirmar** (`--confirmar`): pregunta alias a alias. Los aceptados se
   fusionan en `~/.config/organizador/reglas.json` (la ruta de ADR-001);
   los rechazados y las cancelaciones por EOF no escriben nada.
3. **Reorganizar** (`--reorganizar`, exige `--confirmar`): ademas de
   guardar los alias, mueve lo que ya se puede clasificar con las reglas
   nuevas y deja log en el historial, deshacible con `organizador deshacer`.

La inferencia vive en `sugerir_alias` (funcion pura: nombre + reglas ->
propuesta o None), facil de probar y de auditar. Las coincidencias usan los
mismas funciones publicas del emparejamiento (`coincide_token`/
`coincide_pegado`), asi que una propuesta aceptada se clasifica exactamente
igual que lo haria una regla escrita a mano.
"""

import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from ..escaneo import hijos
from ..excepciones import ErrorDeUso
from ..organizador import mover_archivo
from ..reglas import (
    REVISION,
    Regla,
    cargar_reglas,
    clasificar,
    coincide_pegado,
    coincide_token,
    normalizar,
    ruta_reglas_usuario,
    trocear,
)
from .base import Accion
from .util import ruta_de

# Tokens que solo refuerzan la asignatura (tipo de documento, tema numerico,
# evaluacion...). Nunca deben convertirse en alias: no aportan informacion.
_GENERICOS = {
    "tema",
    "tem",
    "apunts",
    "apuntes",
    "apunts",
    "notes",
    "notas",
    "clase",
    "clases",
    "classes",
    "unitat",
    "unitats",
    "unit",
    "units",
    "unidad",
    "unidades",
    "examen",
    "exam",
    "exams",
    "parcial",
    "mitjana",
    "mitja",
    "recuperacion",
    "evaluacion",
    "avaluacio",
    "repaso",
    "repas",
    "repassar",
    "resume",
    "resum",
    "resumen",
    "repaso",
    "final",
    "definitivo",
    "definitiu",
    "copy",
    "copia",
    "new",
    "nuevo",
    "nou",
    "ok",
    "pdf",
    "doc",
    "docx",
    "jpeg",
    "jpg",
    "png",
    "zip",
    "1",
    "2",
    "3",
    "4",
    "5",
}


@dataclass(frozen=True)
class SugerenciaAplicar:
    """Propuesta de alias para un archivo de `_revision`."""

    nombre: str
    asignatura: str
    alias: tuple
    evidencias: int

    def a_dict(self):
        return {
            "nombre": self.nombre,
            "asignatura": self.asignatura,
            "alias": list(self.alias),
            "evidencias": self.evidencias,
        }


def _aciertos(tokens, alias):
    """Indices de `tokens` que cubre `alias` (la misma logica del motor).

    Aqui se necesita el QUÉ, no solo el SI: los tokens cubiertos por un
    alias conocido no pueden volver a proponerse. La version booleana es
    la publica `coincide_token` de `reglas.py`.
    """
    objetivo = normalizar(alias).split(" ")
    n = len(objetivo)
    cubre: set = set()
    for i in range(len(tokens) - n + 1):
        if tokens[i : i + n] == objetivo:
            cubre.update(range(i, i + n))
    return cubre


def _cubre(alias, tokens):
    """El alias encaja en `tokens`: palabra completa o pegado.

    Antes emulaba el nombre uniendo los tokens con espacios y llamando a
    `_pega` (privado del modulo de reglas y con contrato de nombre de
    archivo: funcionaba, pero por accidente). Ahora usa las dos funciones
    publicas del contrato (`coincide_token`/`coincide_pegado`), que
    trabajan directamente sobre tokens.
    """
    return coincide_token(tokens, alias) or coincide_pegado(tokens, alias)


def _raiz(token):
    """Forma canonica: sin sufijos flexivos obvios (-s, -es, -ces)."""
    for sufijo in ("ces", "es", "s"):
        if token.endswith(sufijo) and len(token) - len(sufijo) >= 3:
            token = token[: -len(sufijo)]
            break
    return token


def _con_sufijo_numerado(token):
    """Formas 'tema3', 'x1', 'u4': letra(s) + digitos de un marcador."""
    return bool(re.fullmatch(r"[a-z]+\d+", token))


def _todos_aliases(reglas):
    for regla in reglas:
        for alias in regla.aliases:
            yield alias
        for _, aliases_tema in regla.temas:
            for alias in aliases_tema:
                yield alias


def sugerir_alias(nombre, reglas):
    """SugerenciaAplicar o None si no se puede inferir nada fiable.

    Reglas de decision (deterministas, sin IA):
      - un token desconocido cuenta como evidencia de la asignatura que ya
        encaja por otros tokens; gana la mayoria (empate = nada fiable);
      - se descartan tokens genericos ('tema', 'apuntes', 'examen'...):
        reforzar la asignatura no convierte 'repaso' en alias de nada;
      - un desconocido largo (>= 4 letras) ya propone alias; si solo quedan
        cortos, se necesitan 2+ (evita inventar alias de 3 letras, terreno
        de falsos positivos como 'fol'/'folder');
      - si el alias propuesto ya esta catalogado, no hay nada que proponer.
    """
    tokens = trocear(nombre)
    if not tokens:
        return None
    texto = "".join(tokens)

    candidatas = []  # [(asignatura, indices_desconocidos)]
    for regla in reglas:
        pares = list(regla.aliases)
        for _, aliases_tema in regla.temas:
            pares.extend(aliases_tema)
        cubiertas = set()
        raices_alias = {_raiz(a) for a in normalizar(" ".join(pares)).split(" ")}
        for alias in pares:
            cubiertas.update(_aciertos(tokens, alias))
            compacto = normalizar(alias).replace(" ", "")
            if len(compacto) >= 3 and compacto in texto:
                cubiertas.update(i for i in range(len(tokens)) if tokens[i] in compacto)
        cubiertas.update(
            i
            for i in range(len(tokens))
            if _raiz(tokens[i]) in raices_alias and len(tokens[i]) >= 3
        )
        desconocidos = tuple(i for i in range(len(tokens)) if i not in cubiertas)
        if not cubiertas and not desconocidos:
            continue
        if not cubiertas and any(desconocidos):
            continue
        candidatas.append((regla.asignatura, desconocidos))

    if not candidatas:
        return None

    votos = Counter(asig for asig, _ in candidatas)
    mejor = max(votos.values())
    ganadoras = [asig for asig, n in votos.items() if n == mejor]
    if len(ganadoras) != 1:
        return None
    asignatura = ganadoras[0]
    regla = next(r for r in reglas if r.asignatura == asignatura)
    desconocidos = dict(candidatas)[asignatura]

    compacto = normalizar(nombre).replace(" ", "")
    alias = []
    for i in desconocidos:
        token = tokens[i]
        if token in _GENERICOS or re.fullmatch(r"x\d+|\d+", token):
            continue
        # marcador con numero ('tema3', 'x1', 'u4'): nunca es alias
        if _con_sufijo_numerado(token):
            continue
        # variante flexiva de un alias catalogado: 'nominas'/'nomina',
        # 'exams'/'examen'. La subcadena suelta NO cuenta: 'poo' esta dentro
        # de 'python' y es informacion completamente distinta.
        if any(_raiz(token) == _raiz(a) for a in _todos_aliases(reglas)):
            continue
        # ya contenido en el propio nombre de forma compacta ('x2' suelto
        # tras 'hilos'): no es un token independiente fiable
        for otra in reglas:
            if any(_cubre(a, [token]) for a in otra.aliases) or any(
                _cubre(a, [token]) for _, temas in otra.temas for a in temas
            ):
                break
        else:
            alias.append(token)
    alias = list(dict.fromkeys(alias))

    largos = [a for a in alias if len(a) >= 4]
    if largos:
        propuestos = largos
    elif len(alias) >= 2:
        propuestos = alias
    else:
        return None

    existentes = set()
    for item in regla.aliases:
        existentes.update(normalizar(item).split(" "))
        existentes.add(normalizar(item).replace(" ", ""))
    propuestos = [a for a in propuestos if a not in existentes]
    if not propuestos:
        return None

    return SugerenciaAplicar(
        nombre, regla.asignatura, tuple(propuestos), len(desconocidos)
    )


class AccionAplicar(Accion):
    """Aprende alias de `_revision` y opcionalmente reorganiza con ellos."""

    nombre = "aplicar"

    def __init__(
        self,
        consola,
        salida,
        reglas,
        registro,
        confirmar=False,
        reorganizar=False,
        seco=False,
        ruta_destino=None,
    ):
        super().__init__(consola)
        self.salida = salida
        self.reglas = reglas
        self.registro = registro
        self.confirmar = confirmar
        self.reorganizar = reorganizar
        self.seco = seco
        self._ruta_destino = Path(ruta_destino) if ruta_destino else None
        self.reglas_especificas = ruta_destino is not None

    @classmethod
    def desde_config(cls, args, consola):
        from ..registro import Registro
        from ..reglas import reglas_efectivas

        if getattr(args, "reorganizar", False) and not getattr(
            args, "confirmar", False
        ):
            raise ErrorDeUso(
                "--reorganizar requiere --confirmar: primero se preguntan los "
                "alias y solo entonces se mueven archivos."
            )
        return cls(
            consola=consola,
            salida=ruta_de(args.salida, "--salida"),
            reglas=reglas_efectivas(args.reglas),
            registro=Registro.desde_config(args),
            confirmar=getattr(args, "confirmar", False),
            reorganizar=getattr(args, "reorganizar", False),
            seco=getattr(args, "seco", False),
            ruta_destino=args.reglas,
        )

    def _ruta_reglas_destino(self):
        """Donde se fusionan los alias: el fichero explicito o el del usuario.

        Con `--reglas` el guardado va a ESE fichero (quien usa un catalogo
        propio quiere la sugerencia dentro); sin el, a la ruta de ADR-001.
        """
        return self._ruta_destino if self.reglas_especificas else ruta_reglas_usuario()

    def ejecutar(self):
        carpeta = self.salida / REVISION
        if not carpeta.is_dir():
            return self._sin_carpeta(carpeta)
        archivos = [
            p
            for p in hijos(carpeta)
            if p.is_file()
            and not p.name.startswith(".")
            and not p.name.startswith("~$")
        ]
        if not archivos:
            return self._vacio(carpeta)

        propuestas = [
            p for p in (sugerir_alias(a.name, self.reglas) for a in archivos) if p
        ]

        aceptadas = []
        rechazadas = []
        cancelado = False
        if propuestas and self.confirmar:
            aceptadas, rechazadas, cancelado = self._preguntar(propuestas)
            if aceptadas and not cancelado:
                # con EOF se aborta TODO: ni alias escritos ni movimientos
                self._escribir_alias(aceptadas)
        elif propuestas and not self.consola.json_mode and not self.seco:
            self._mostrar(propuestas, [], [], False)
            self.consola.linea(
                "Solo propuestas: usa --confirmar para guardar alias y "
                "--reorganizar para mover."
            )

        movidos = []
        errores = []
        if propuestas and self.confirmar and not cancelado:
            movidos, errores = self._reorganizar(carpeta)

        if self.consola.json_mode:
            return self._emitir(
                carpeta, propuestas, aceptadas, rechazadas, cancelado, movidos, errores
            )
        if self.seco:
            self._resumen(
                propuestas, aceptadas, rechazadas, cancelado, movidos, errores
            )
            for fallo in errores:
                self.consola.aviso(
                    "[!] {} -> {}".format(fallo["nombre"], fallo["error"])
                )
        else:
            self._mostrar(
                propuestas, aceptadas, rechazadas, cancelado, movidos, errores
            )
        return 0

    # --- pregunta ----------------------------------------------------------

    def _preguntar(self, propuestas):
        aceptadas = []
        rechazadas = []
        cancelado = False
        for sugerencia in propuestas:
            texto = "Alias {} -> {} [s/N]: ".format(
                " + ".join("'{}'".format(a) for a in sugerencia.alias),
                sugerencia.asignatura,
            )
            try:
                respuesta = self.consola.respuesta_si(texto)
            except EOFError:
                self.consola.linea()
                self.consola.linea("Entrada cancelada; no se escribe nada.")
                cancelado = True
                break
            if respuesta:
                aceptadas.append(sugerencia)
            else:
                rechazadas.append(sugerencia)
        return aceptadas, rechazadas, cancelado

    # --- escritura de reglas -----------------------------------------------

    def _escribir_alias(self, aceptadas):
        """Fusiona los alias aceptados en el fichero de reglas destino."""
        ruta = self._ruta_reglas_destino()
        usuario = []
        if ruta.is_file():
            usuario = [
                {
                    "asignatura": r.asignatura,
                    "aliases": list(r.aliases),
                    "temas": [{"tema": t, "aliases": list(a)} for t, a in r.temas],
                }
                for r in cargar_reglas(ruta)
            ]
        por_asignatura = {r["asignatura"]: r for r in usuario}
        for sugerencia in aceptadas:
            entrada = por_asignatura.get(sugerencia.asignatura)
            if entrada is None:
                regla = next(
                    r for r in self.reglas if r.asignatura == sugerencia.asignatura
                )
                entrada = {
                    "asignatura": regla.asignatura,
                    "aliases": list(regla.aliases),
                    "temas": [{"tema": t, "aliases": list(a)} for t, a in regla.temas],
                }
                usuario.append(entrada)
                por_asignatura[entrada["asignatura"]] = entrada
            for alias in sugerencia.alias:
                if alias not in entrada["aliases"]:
                    entrada["aliases"].append(alias)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        with open(ruta, "w", encoding="utf-8") as archivo:
            json.dump(usuario, archivo, indent=2, ensure_ascii=False)
            archivo.write("\n")

    # --- reorganizacion ------------------------------------------------------

    def _reorganizar(self, carpeta):
        """Mueve lo clasificable con las reglas vigentes (incluidos los alias
        recien guardados). Reutiliza el motor: sufijo anti-colision y log
        en el historial para que `deshacer` pueda revertirlo.

        `cargar_reglas` cachea por ruta y la cache es inmutable (diseño de
        reglas.py), asi que la recarga se hace leyendo el JSON destino a
        mano: son las reglas efectivas + el delta de los alias aceptados.
        """
        reglas = self._reglas_con_delta()

        movidos = []
        errores = []
        for archivo in [p for p in hijos(carpeta) if p.is_file()]:
            if clasificar(archivo.name, self.reglas) is not None:
                continue  # ya era clasificable: no es trabajo de aplicar
            resultado = clasificar(archivo.name, reglas)
            if resultado is None:
                continue
            asignatura, tema = resultado
            destino_dir = self.salida / asignatura
            if tema:
                destino_dir = destino_dir / tema
            try:
                destino = mover_archivo(archivo, destino_dir)
            except OSError as error:
                errores.append({"nombre": archivo.name, "error": str(error)})
                continue
            movidos.append(
                {
                    "nombre": archivo.name,
                    "asignatura": asignatura,
                    "tema": tema,
                    "destino": str(destino),
                }
            )

        if movidos:
            try:
                self.registro.guardar_historial(
                    carpeta,
                    self.salida,
                    {"movimientos": movidos, "errores": errores},
                )
            except OSError as error:
                self.consola.aviso(
                    "Aviso: no se pudo escribir el log: {}".format(error)
                )
        return movidos, errores

    def _reglas_con_delta(self):
        """Reglas efectivas mas los alias recien escritos en el fichero."""
        delta = {}
        ruta = self._ruta_reglas_destino()
        if ruta.is_file():
            try:
                for regla in json.loads(ruta.read_text(encoding="utf-8")):
                    delta[regla.get("asignatura", "")] = list(regla.get("aliases", []))
            except (OSError, ValueError):
                return self.reglas
        if not delta:
            return self.reglas
        nuevas = []
        for regla in self.reglas:
            extra = [
                a for a in delta.get(regla.asignatura, []) if a not in regla.aliases
            ]
            nuevas.append(
                Regla(
                    regla.asignatura,
                    regla.aliases + tuple(extra),
                    regla.temas,
                )
            )
        por_asignatura = {r.asignatura for r in nuevas}
        for asignatura, alias in delta.items():
            if asignatura not in por_asignatura and alias:
                nuevas.append(Regla(asignatura, tuple(alias), ()))
        return tuple(nuevas)

    # --- presentacion ------------------------------------------------------

    def _sin_carpeta(self, carpeta):
        if self.consola.json_mode:
            return self._emitir(carpeta, [], [], [], False, [], [])
        self.consola.linea("No existe la carpeta de revisión: {}".format(carpeta))
        return 0

    def _vacio(self, carpeta):
        if self.consola.json_mode:
            return self._emitir(carpeta, [], [], [], False, [], [])
        self.consola.linea("No hay archivos pendientes en {}".format(carpeta))
        return 0

    def _mostrar(
        self,
        propuestas,
        aceptadas,
        rechazadas,
        cancelado,
        movidos=(),
        errores=(),
    ):
        nombres_aceptadas = {s.nombre for s in aceptadas}
        nombres_rechazadas = {s.nombre for s in rechazadas}
        for sugerencia in propuestas:
            if sugerencia.nombre in nombres_aceptadas:
                marca = "[si]"
            elif sugerencia.nombre in nombres_rechazadas:
                marca = "[no]"
            elif cancelado:
                marca = "[--]"
            else:
                marca = "[?]"
            self.consola.linea(
                "{} {} -> {} (alias: {})".format(
                    marca,
                    sugerencia.nombre,
                    sugerencia.asignatura,
                    ", ".join(sugerencia.alias),
                )
            )
        for movido in movidos:
            destino = movido["asignatura"]
            if movido["tema"]:
                destino = "{}/{}".format(destino, movido["tema"])
            self.consola.linea("[OK] {} -> {}".format(movido["nombre"], destino))
        if errores:
            self.consola.errores({"errores": errores})
        self._resumen(propuestas, aceptadas, rechazadas, cancelado, movidos, errores)

    def _resumen(
        self,
        propuestas,
        aceptadas,
        rechazadas,
        cancelado,
        movidos,
        errores,
    ):
        lineas: list = [("Propuestas", len(propuestas))]
        if self.confirmar:
            lineas.append(("Alias guardados", len(aceptadas)))
            lineas.append(("Rechazados", len(rechazadas)))
        if self.reorganizar:
            lineas.append(("Reorganizados", len(movidos)))
        lineas.append(("Errores", len(errores)))
        if cancelado:
            lineas.append(("Cancelado", "sí"))
        self.consola.resumen(lineas)

    def _emitir(
        self, carpeta, propuestas, aceptadas, rechazadas, cancelado, movidos, errores
    ):
        from ..presentacion import emitir_json

        emitir_json(
            {
                "ok": True,
                "accion": self.nombre,
                "carpeta": str(carpeta),
                "propuestas": [p.a_dict() for p in propuestas],
                "guardados": [p.a_dict() for p in aceptadas],
                "rechazados": [p.a_dict() for p in rechazadas],
                "cancelado": cancelado,
                "movidos": movidos,
                "errores": errores,
                "total": len(propuestas),
            }
        )
        return 0
