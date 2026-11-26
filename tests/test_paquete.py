"""Auditoria del paquete publicado: el sdist se instala y se comporta.

Los demas tests usan el arbol de `src/` (editable o PYTHONPATH). Este audita
lo que un usuario descarga de la release: construye el sdist, lo instala en
un venv aislado y ejerce el contrato del extra `[pdf]` (ADR-006). Marca
`lento`: la suite rapida lo omite (`pytest tests -m "not lento"`); la CI lo
corre explicitamente. Requiere `build` (dev) y capacidad de crear entornos;
si falta algo, `skip` honesto, nunca falso verde.
"""

import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

pytestmark = pytest.mark.lento

RAIZ = Path(__file__).resolve().parents[1]


def _python_del_venv(base: Path) -> Path:
    if sys.platform == "win32":
        return base / "Scripts" / "python.exe"
    return base / "bin" / "python"


def _crear_venv_con_pip(base: Path):
    """Crea un venv con pip si el sistema lo permite; None si no.

    `python -m venv` a secas falla en distros sin `ensurepip` (Debian/Ubuntu
    sin el paquete `python3-venv`); ahi entra `virtualenv` (dev extra), que
    se autoabastece de pip. Sin ninguna de las dos, skip honesto.
    """
    for comando in (
        [sys.executable, "-m", "venv", str(base)],
        [sys.executable, "-m", "virtualenv", str(base)],
    ):
        try:
            resultado = subprocess.run(comando, capture_output=True, text=True)
        except OSError:
            continue
        if resultado.returncode != 0:
            continue
        pip = subprocess.run(
            [str(_python_del_venv(base)), "-m", "pip", "--version"],
            capture_output=True,
            text=True,
        )
        if pip.returncode == 0:
            return base
    return None


def _sin_pypdf(python: Path, env: dict) -> bool:
    """True si `python` NO ve pypdf en modo aislado (`-I -E`: sin PYTHONPATH).

    Es el unico mecanismo portable: `pip uninstall` no puede tocar paquetes
    del site de usuario (fuera del venv), y `-S` no basta porque el
    `sitecustomize` del entorno los mete igual. Auto-verificado en el propio
    venv con `importlib.metadata` del entorno: si `pypdf` vive fuera del site
    del venv, la fase sin extra se ejecutara con `-I -E` delante de cada
    `organizador`; si vive dentro, se puede desinstalar del venv.
    """
    import importlib.metadata as md

    aislado = subprocess.run(
        [str(python), "-I", "-E", "-c", "import pypdf"],
        capture_output=True,
        text=True,
        env=env,
    )
    if aislado.returncode == 0:
        return False
    try:
        ubicacion = str(md.distribution("pypdf").locate_file("pypdf"))
    except md.PackageNotFoundError:
        return True
    if Path(ubicacion).is_dir() and str(ubicacion).startswith(
        str(python.parent.parent)
    ):
        # pypdf esta en el propio venv (extrajo el wheel en la fase 3? no
        # deberia: la desinstalamos ahora, via pip puro, que tampoco lo ve)
        subprocess.run(
            [str(python), "-m", "pip", "uninstall", "-y", "pypdf"],
            capture_output=True,
            text=True,
            env=env,
        )
        aislado = subprocess.run(
            [str(python), "-I", "-E", "-c", "import pypdf"],
            capture_output=True,
            text=True,
            env=env,
        )
        return aislado.returncode != 0
    return True


def _find_links_pypdf(tmp_path: Path):
    """Ruedas locales de `pypdf` y sus dependencias para instalar sin red.

    El venv se instala con `--no-index`: la unica fuente de `pypdf` es el
    `PYTHONPATH` que le presta el entorno de tests. `importlib.metadata`
    localiza la distribucion; se reempaqueta como wheel minima (con sus
    `Requires-Dist` originales: sin metadata, pip instalaria pypdf hueco y
    `typing_extensions` faltararia en Python < 3.11) y lo mismo se hace con
    las dependencias de runtime que el marcador pida, en closure. Sin tocar
    el site real del usuario y sin red.
    """
    import importlib.metadata as md
    import zipfile

    from packaging.markers import Marker

    destino = tmp_path / "find-links"
    destino.mkdir()
    pendientes, vistas = ["pypdf"], set()
    while pendientes:
        nombre = pendientes.pop()
        if nombre.lower() in vistas:
            continue
        vistas.add(nombre.lower())
        try:
            distribucion = md.distribution(nombre)
        except md.PackageNotFoundError:
            return None
        raiz = Path(str(distribucion.locate_file(nombre.replace("-", "_"))))
        version = distribucion.version
        rueda = destino / "{}-{}-py3-none-any.whl".format(nombre, version)
        # copiamos al staging: el wheel se arma desde ahi (los archivos
        # originales pueden estar en un site no escribible); los paquetes de
        # un solo modulo (typing_extensions) van sueltos en la raiz del zip
        staged = tmp_path / "staging" / nombre
        if raiz.is_dir():
            shutil.copytree(raiz, staged)
            contenido = [
                (ruta, str(ruta.relative_to(staged.parent)))
                for ruta in staged.rglob("*")
                if ruta.is_file()
            ]
        elif raiz.with_suffix(".py").is_file():
            modulo = raiz.with_suffix(".py")
            contenido = [(modulo, modulo.name)]
        else:
            return None
        lineas = [
            "Metadata-Version: 2.1",
            "Name: {}".format(nombre),
            "Version: {}".format(version),
        ]
        with zipfile.ZipFile(rueda, "w") as archivo:
            for ruta, nombre_zip in contenido:
                archivo.write(ruta, nombre_zip)
            info = "{}-{}.dist-info".format(nombre, version)
            requires = distribucion.metadata.get_all("Requires-Dist") or []
            for requiere in requires:
                linea, _, marcador = requiere.partition(";")
                if "extra ==" in marcador:
                    continue
                lineas.append("Requires-Dist: {}".format(requiere))
                dependencia = linea.strip().split(" ")[0].split("<")[0].split(">")[0]
                if dependencia and (not marcador or Marker(marcador).evaluate()):
                    pendientes.append(dependencia)
            archivo.writestr(info + "/METADATA", "\n".join(lineas) + "\n")
            archivo.writestr(info + "/WHEEL", "Wheel-Version: 1.0\nGenerator: tests\n")
            archivo.writestr(info + "/RECORD", "")
    return destino


def _pip(python: Path, env: dict, *objetos: str) -> subprocess.CompletedProcess:
    """`pip install` dentro del venv, sin red (--no-index).

    El `PYTHONPATH` con el `purelib` del interprete de tests permite dos
    cosas sin red: que el venv (sobre todo `virtualenv`) encuentre `pip`, y
    que `pypdf` quede visible al ejecutar la CLI instalada — el mismo
    mecanismo que usa la suite base con `src/`.
    """
    return subprocess.run(
        [str(python), "-m", "pip", "install", "--quiet", "--no-index", *objetos],
        capture_output=True,
        text=True,
        env=env,
    )


def _env_venv(base: Path, tmp: Path) -> dict:
    """Entorno minimo para ejecutar dentro del venv sin tocar el proceso."""
    return {
        "PATH": str(_python_del_venv(base).parent)
        + os.pathsep
        + os.environ.get("PATH", ""),
        "HOME": str(tmp),
        "XDG_CONFIG_HOME": str(tmp / "config"),
        "PYTHONPATH": _pip_entorno(),
    }


def _pip_entorno() -> str:
    """Site del interprete de tests, sin el user-site (pip para el venv).

    En Debian/Ubuntu el sitio de usuario (~/.local) convive con el del
    sistema: si se presta entero, el venv hereda pypdf y la fase sin extra
    es imposible. Se recorre `sys.path` eligiendo el primero que tiene `pip`
    y NO tiene `pypdf`: en CI es el site del runner (pip y pypdf conviven,
    pero ahi el venv no los pilla y el aislamiento `-I -E` basta); en
    maquinas con user-site, es el site del sistema.
    """
    candidatos = [e for e in sys.path if e and (Path(e) / "pip").exists()]
    for entrada in candidatos:
        if not (Path(entrada) / "pypdf").exists():
            return str(entrada)
    return candidatos[0] if candidatos else ""


@pytest.fixture(scope="module")
def rueda(tmp_path_factory) -> Path:
    """sdist construido desde el arbol y su rueda, sin tocar el repo.

    `--no-isolation`: el build usa los paquetes YA instalados en el entorno
    de tests (build + wheel + setuptools del dev extra), sin red.
    """
    import importlib.util

    if not (importlib.util.find_spec("build") and importlib.util.find_spec("wheel")):
        pytest.skip("build/wheel no disponibles")
    salida = tmp_path_factory.mktemp("dist")
    construido = subprocess.run(
        [
            sys.executable,
            "-m",
            "build",
            "--sdist",
            "--no-isolation",
            "--outdir",
            str(salida),
        ],
        cwd=str(RAIZ),
        capture_output=True,
        text=True,
    )
    if construido.returncode != 0:
        pytest.skip(
            "el sdist no se pudo construir: {}".format(construido.stderr[-400:])
        )
    sdists = list(salida.glob("organizador-*.tar.gz"))
    assert len(sdists) == 1
    extraido = tmp_path_factory.mktemp("sdist")
    with tarfile.open(sdists[0]) as tar:
        tar.extractall(extraido)
    raiz_sdist = next(extraido.glob("organizador-*"))
    rueda_build = subprocess.run(
        [
            sys.executable,
            "-m",
            "build",
            "--wheel",
            "--no-isolation",
            "--outdir",
            str(salida),
            str(raiz_sdist),
        ],
        cwd=str(RAIZ),
        capture_output=True,
        text=True,
    )
    if rueda_build.returncode != 0:
        pytest.skip(
            "la rueda no se pudo construir: {}".format(rueda_build.stderr[-400:])
        )
    ruedas = list(salida.glob("organizador-*.whl"))
    assert len(ruedas) == 1
    return ruedas[0]


@pytest.fixture()
def venv_con_pip(tmp_path):
    base = tmp_path / "venv"
    if _crear_venv_con_pip(base) is None:
        pytest.skip("este entorno no puede crear un venv utilizable")
    return base


def test_sdist_instalado_sin_extra_y_con_extra(rueda, venv_con_pip, tmp_path):
    """El paquete publicado: version, error humano sin `[pdf]`, flujo con `[pdf]`.

    Contrato de la release en el artefacto real (no en `src/`): 1) `--version`
    responde y coincide con `organizador.__version__`; 2) `--contenido` sin el
    extra sale 2 con el mensaje de instalacion (el mismo error humano que los
    unitarios simulan con un doble de import); 3) con el extra instalado, un
    PDF real generado aqui mismo se organiza por contenido.

    Aislamiento del extra: el PYTHONPATH que presta pip al venv arrastra a
    veces pypdf del usuario; la fase sin extra se ejecuta con `python -I -E`
    (sin PYTHONPATH ni site de usuario) delante de la CLI, y solo si pypdf no
    existe en modo aislado (ver `_sin_pypdf`).
    """
    from organizador import __version__

    python = _python_del_venv(venv_con_pip)
    env = _env_venv(venv_con_pip, tmp_path)
    sin_extra_env = dict(env)
    sin_extra_env.pop("PYTHONPATH", None)
    if not _sin_pypdf(python, sin_extra_env):
        pytest.skip("pypdf esta en el interprete base: no se puede simular su ausencia")

    instalado = _pip(python, env, str(rueda))
    assert instalado.returncode == 0, instalado.stderr[-400:]

    version = subprocess.run(
        [str(python), "-I", "-E", "-m", "organizador", "--version"],
        env=sin_extra_env,
        capture_output=True,
        text=True,
    )
    assert version.returncode == 0, version.stderr[-200:]
    assert __version__ in version.stdout

    origen = tmp_path / "descargas"
    origen.mkdir()
    # PDF de verdad (bytes magicos + nada mas): con el extra, pypdf lo intenta
    # y falla (aviso, rc 0); sin el extra, el fallo es el error humano (rc 2).
    (origen / "examen_final_resuelto.pdf").write_bytes(b"%PDF-1.4\ntrailing")
    sin_extra = subprocess.run(
        [
            str(python),
            "-I",
            "-E",
            "-m",
            "organizador",
            "ejecutar",
            str(origen),
            "--contenido",
            "--simular",
        ],
        env=sin_extra_env,
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
    )
    assert sin_extra.returncode == 2, sin_extra.stderr[-200:]
    assert "organizador[pdf]" in sin_extra.stderr

    # con el extra: mismo contrato que los tests de src/, pero con la rueda
    # real. Sin red: el pypdf del entorno viaja copiado como rueda local.
    enlaces = _find_links_pypdf(tmp_path)
    if enlaces is None:
        pytest.skip("pypdf no esta disponible para copiarlo al venv")
    con_extra = _pip(python, env, "--find-links", str(enlaces), str(rueda) + "[pdf]")
    assert con_extra.returncode == 0, con_extra.stderr[-400:]

    sys.path.insert(0, str(RAIZ / "tests"))
    from pdfs import escribir_pdf  # noqa: E402  (fabrica compartida de PDFs)

    (origen / "examen_final_resuelto.pdf").unlink()
    escribir_pdf(origen / "sin_nombre.pdf", ["Apuntes de Programacion java"])
    r = subprocess.run(
        [
            "organizador",
            "ejecutar",
            str(origen),
            "--salida",
            str(tmp_path / "Organizado"),
            "--contenido",
            "--logs-dir",
            str(tmp_path / "logs"),
        ],
        env=env,
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr[-300:]
    assert (
        tmp_path / "Organizado" / "Programacion" / "Java" / "sin_nombre.pdf"
    ).exists()
