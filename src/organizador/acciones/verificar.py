"""Accion `verificar`: audita `Organizado/` y, con `--podar`, desactiva duplicados.

Solo lectura por defecto. Los cinco detectores son independientes:
duplicados (SHA-256), subproductos del navegador (`doc (1).pdf`), carpetas
vacias, carpetas fuera de catalogo, archivos "atrapados" (en la raiz de una
asignatura cuando las reglas los pondrian en un tema) y el estado de
`_revision` (cuantos y cuantos propondrian `aplicar`/`sugerir`).

`--podar` no destruye: mueve las copias sobrantes a una papelera dentro del
historial y deja log. `deshacer` (motor, sin tocar) las devuelve a su
carpeta original.
"""

import hashlib
import re
import shutil
from pathlib import Path

from ..excepciones import CarpetaNoValidaError, ErrorDeUso
from ..organizador import _destino_disponible
from .aplicar import sugerir_alias
from .base import Accion

TAM_BLOQUE = 65536
PAPELERA = ".papelera"


def _hash(archivo):
    try:
        digest = hashlib.sha256()
        with open(archivo, "rb") as handles:
            for bloque in iter(lambda: handles.read(TAM_BLOQUE), b""):
                digest.update(bloque)
        return digest.hexdigest()
    except OSError:
        return None


def _es_ignorable(nombre):
    return nombre.startswith(".") or nombre.startswith("~$")


def _subproducto(nombre):
    """('doc', '.pdf') desde 'doc (1).pdf', o None."""
    base = re.fullmatch(r"(.*) \(\d+\)(\..+)?", nombre)
    if not base:
        return None
    return base.group(1), base.group(2) or ""


class AccionVerificar(Accion):
    """Audita la carpeta de salida y, con `--podar`, desactiva duplicados."""

    nombre = "verificar"

    def __init__(
        self,
        consola,
        salida,
        reglas,
        proveedor,
        registro,
        podar=False,
        confirmar=False,
        seco=False,
    ):
        super().__init__(consola)
        self.salida = salida
        self.reglas = reglas
        self.proveedor = proveedor
        self.registro = registro
        self.podar = podar
        self.confirmar = confirmar
        self.seco = seco

    @classmethod
    def desde_config(cls, args, consola):
        from ..proveedor import ProveedorIA
        from ..registro import Registro
        from ..reglas import reglas_efectivas

        if getattr(args, "confirmar", False) and not getattr(args, "podar", False):
            raise ErrorDeUso(
                "--confirmar solo acompana a --podar: verificar sin podar "
                "no toca ningun archivo."
            )
        registro = Registro.desde_config(args)
        return cls(
            consola=consola,
            salida=Path(args.salida).resolve(),
            reglas=reglas_efectivas(args.reglas),
            proveedor=ProveedorIA.desde_env(),
            registro=registro,
            podar=getattr(args, "podar", False),
            confirmar=getattr(args, "confirmar", False),
            seco=getattr(args, "seco", False),
        )

    # --- recoleccion ---------------------------------------------------------

    def _archivos(self):
        """Archivos de la salida, omitiendo ocultos, logs y papelera."""
        logs = self.registro.carpeta.resolve()
        archivos = []
        for ruta in sorted(self.salida.rglob("*")):
            if not ruta.is_file() or _es_ignorable(ruta.name):
                continue
            if logs in ruta.parents or PAPELERA in ruta.parts:
                continue
            archivos.append(ruta)
        return archivos

    def _duplicados(self, archivos):
        grupos: dict = {}
        for ruta in archivos:
            clave = _hash(ruta)
            if clave:
                grupos.setdefault(clave, []).append(ruta)
        return [rutas for rutas in grupos.values() if len(rutas) > 1]

    def _subproductos(self, archivos):
        """Copias con sufijo de navegador ('doc (1).pdf' junto a 'doc.pdf').

        `--podar` no los toca (no son byte-identicos); solo se informan.
        """
        found = []
        for ruta in archivos:
            base = _subproducto(ruta.name)
            if not base:
                continue
            candidato = ruta.parent / (base[0] + base[1])
            if candidato.is_file():
                found.append((candidato, ruta))
        return found

    def _carpetas_vacias(self):
        return [
            ruta
            for ruta in sorted(self.salida.rglob("*"))
            if ruta.is_dir() and not any(ruta.iterdir())
        ]

    def _fuera_catalogo(self):
        from ..reglas import REVISION

        asignaturas = {regla.asignatura for regla in self.reglas}
        logs = self.registro.carpeta.resolve()
        fuera = []
        for ruta in sorted(self.salida.iterdir()):
            if not ruta.is_dir() or _es_ignorable(ruta.name):
                continue
            if ruta.name == REVISION or ruta.name in asignaturas:
                continue
            if ruta.resolve() == logs:
                continue
            fuera.append(ruta)
        return fuera

    def _atrapados(self):
        """Archivos en la raiz de una asignatura que pertenecen a un tema."""
        from ..reglas import clasificar

        atrapados = []
        for regla in self.reglas:
            raiz = self.salida / regla.asignatura
            if not raiz.is_dir():
                continue
            for archivo in sorted(p for p in raiz.iterdir() if p.is_file()):
                resultado = clasificar(archivo.name, self.reglas)
                if resultado and resultado[1]:
                    atrapados.append((archivo, resultado))
        return atrapados

    def _revision(self):
        from ..reglas import REVISION

        carpeta = self.salida / REVISION
        if not carpeta.is_dir():
            return {"total": 0, "aplicar": 0, "sugerir": 0}
        nombres = [
            p.name
            for p in sorted(carpeta.iterdir())
            if p.is_file() and not _es_ignorable(p.name)
        ]
        propone_aplicar = sum(1 for n in nombres if sugerir_alias(n, self.reglas))
        try:
            propone_sugerir = len(
                [
                    s
                    for s in self.proveedor.sugerir(nombres, self.reglas)
                    if s.asignatura
                ]
            )
        except Exception:
            propone_sugerir = propone_aplicar
        return {
            "total": len(nombres),
            "aplicar": propone_aplicar,
            "sugerir": propone_sugerir,
        }

    def _hallazgos(
        self, duplicados, subproductos, vacias, fuera, atrapados, revision, errores
    ):
        """`revision` no es un fallo del estado: vaciarlo es trabajo de
        `aplicar`/`sugerir`. Un error si que lo es: impide confiar el informe."""
        return bool(
            duplicados or subproductos or vacias or fuera or atrapados or errores
        ) or bool(revision["total"])

    # --- poda ----------------------------------------------------------------

    def _podar(self, duplicados):
        """Mueve las copias sobrantes a la papelera del historial.

        Nada se destruye: `<logs-dir>/.papelera/` guarda las copias. El log
        usa el formato del motor a la inversa: `destino` = donde esta ahora
        (papelera), `nombre` = nombre original. Al deshacer, `deshacer`
        devuelve cada copia a la carpeta original: como la ruta de destino
        del log apunta a la papelera y el `origen` registrado es la salida,
        el nombre original basta para reconstruir la carpeta (los duplicados
        comparten carpeta con el archivo que se conserva).
        """
        a_podar = [ruta for grupo in duplicados for ruta in sorted(grupo)[1:]]
        if not a_podar:
            return [], []
        if not self.confirmar:
            if self.consola.json_mode:
                self.consola.aviso("--podar requiere --confirmar.")
                return [], []
            try:
                aprobado = self.consola.respuesta_si(
                    "¿Podar {} copias duplicadas? [s/N]: ".format(len(a_podar))
                )
            except EOFError:
                self.consola.linea()
                self.consola.linea("Entrada cancelada; no se ha podado nada.")
                return [], []
            if not aprobado:
                self.consola.cancelar("Cancelado; no se ha podado nada.")
                return [], []

        papelera = self.registro.carpeta / PAPELERA
        papelera.mkdir(parents=True, exist_ok=True)
        podados = []
        errores = []
        movimientos = []
        for ruta in a_podar:
            try:
                destino = _destino_disponible(papelera / ruta.name)
                shutil.move(str(ruta), str(destino))
                # informe: ruta relativa a la salida, coherente con el JSON
                podados.append(
                    str(
                        Path(destino)
                        .resolve()
                        .relative_to(self.registro.carpeta.resolve())
                    )
                )
                # log para deshacer EXACTO: `destino` = ruta original, SIEMPRE
                # absoluta (la del motor); si `--salida` era relativa, la
                # resolvemos ahora o `deshacer` no encontraria la papelera
                restaurar = (
                    str(ruta) if Path(ruta).is_absolute() else str(ruta.resolve())
                )
                movimientos.append(
                    {
                        "nombre": ruta.name,
                        "asignatura": "",
                        "tema": "",
                        "destino": restaurar,
                    }
                )
            except OSError as error:
                errores.append({"nombre": ruta.name, "error": str(error)})

        if movimientos:
            try:
                self._guardar_log_poda(movimientos)
            except OSError as error:
                self.consola.aviso(
                    "Aviso: no se pudo escribir el log: {}".format(error)
                )
        return podados, errores

    # --- ejecucion -------------------------------------------------------------

    def _guardar_log_poda(self, movimientos):
        """Log con marca `restaurar`: `deshacer` lo invierte desde la papelera."""
        import json
        from datetime import datetime

        self.registro.carpeta.mkdir(parents=True, exist_ok=True)
        marca = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        ruta = self.registro.carpeta / "{}.json".format(marca)
        datos = {
            "fecha": datetime.now().isoformat(timespec="seconds"),
            "origen": str(self.registro.carpeta),
            "salida": str(self.salida),
            "restaurar": True,
            "movimientos": movimientos,
            "errores": [],
        }
        with open(ruta, "w", encoding="utf-8") as archivo:
            json.dump(datos, archivo, indent=2, ensure_ascii=False)
        return ruta

    def ejecutar(self):
        if not self.salida.is_dir():
            raise CarpetaNoValidaError(
                "No existe la carpeta de salida: {}".format(self.salida)
            )

        archivos = self._archivos()
        duplicados = self._duplicados(archivos)
        subproductos = self._subproductos(archivos)
        vacias = self._carpetas_vacias()
        fuera = self._fuera_catalogo()
        atrapados = self._atrapados()
        revision = self._revision()

        hallazgos = self._hallazgos(
            duplicados, subproductos, vacias, fuera, atrapados, revision, []
        )
        # el codigo se decide ANTES de podar: verificar no es "exito" porque
        # el usuario haya limpiado; habia duplicados que auditar
        codigo = 1 if hallazgos else 0

        podados = []
        errores = []
        if self.podar and duplicados:
            podados, errores = self._podar(duplicados)
        if podados:
            # re-auditar: el informe refleja el estado final
            archivos = self._archivos()
            duplicados = self._duplicados(archivos)
            subproductos = self._subproductos(archivos)
            vacias = self._carpetas_vacias()
            fuera = self._fuera_catalogo()
            atrapados = self._atrapados()
            revision = self._revision()
            codigo = 1 if errores else codigo

        if self.consola.json_mode:
            return self._emitir(
                codigo,
                archivos,
                duplicados,
                subproductos,
                vacias,
                fuera,
                atrapados,
                revision,
                podados,
                errores,
            )
        self._informar(
            archivos,
            duplicados,
            subproductos,
            vacias,
            fuera,
            atrapados,
            revision,
            podados,
            errores,
        )
        return codigo

    # --- presentacion ----------------------------------------------------------

    def _etiqueta(self, ruta):
        return str(ruta.relative_to(self.salida))

    def _informar(
        self,
        archivos,
        duplicados,
        subproductos,
        vacias,
        fuera,
        atrapados,
        revision,
        podados,
        errores,
    ):
        consola = self.consola
        if not self.seco:
            for grupo in duplicados:
                consola.linea("duplicado: {}".format(self._etiqueta(grupo[0])))
                for ruta in grupo[1:]:
                    consola.linea("  copia: {}".format(self._etiqueta(ruta)))
            for original, copia in subproductos:
                consola.linea(
                    "subproducto: {} (copia de {})".format(
                        self._etiqueta(copia), self._etiqueta(original)
                    )
                )
            for ruta in vacias:
                consola.linea("carpeta vacia: {}".format(self._etiqueta(ruta)))
            for ruta in fuera:
                consola.linea("fuera de catalogo: {}".format(self._etiqueta(ruta)))
            for archivo, (asignatura, tema) in atrapados:
                consola.linea(
                    "atrapado: {} -> {}/{}".format(
                        self._etiqueta(archivo), asignatura, tema
                    )
                )
            consola.linea(
                "revision: {} (aplicar: {}, sugerir: {})".format(
                    revision["total"], revision["aplicar"], revision["sugerir"]
                )
            )
            if podados:
                consola.linea(
                    "podados: {} (papelera del historial)".format(len(podados))
                )
            if errores:
                consola.errores({"errores": errores})
        consola.resumen(
            [
                ("Archivos", len(archivos)),
                ("Duplicados", len(duplicados)),
                ("Subproductos", len(subproductos)),
                ("Carpetas vacias", len(vacias)),
                ("Fuera de catalogo", len(fuera)),
                ("Atrapados", len(atrapados)),
                ("En revision", revision["total"]),
                ("Errores", len(errores)),
            ]
        )

    def _emitir(
        self,
        codigo,
        archivos,
        duplicados,
        subproductos,
        vacias,
        fuera,
        atrapados,
        revision,
        podados,
        errores,
    ):
        from ..presentacion import emitir_json

        emitir_json(
            {
                "ok": codigo == 0,
                "accion": self.nombre,
                "salida": str(self.salida),
                "duplicados": [
                    [self._etiqueta(r) for r in grupo] for grupo in duplicados
                ],
                "subproductos": [
                    {"original": self._etiqueta(o), "copia": self._etiqueta(c)}
                    for o, c in subproductos
                ],
                "vacias": [self._etiqueta(r) for r in vacias],
                "fuera_catalogo": [self._etiqueta(r) for r in fuera],
                "atrapados": [
                    {
                        "archivo": self._etiqueta(archivo),
                        "asignatura": asignatura,
                        "tema": tema,
                    }
                    for archivo, (asignatura, tema) in atrapados
                ],
                "revision": revision,
                "podados": podados,
                "errores": errores,
                "totales": {"archivos": len(archivos)},
            }
        )
        return codigo
