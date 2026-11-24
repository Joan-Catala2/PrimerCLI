import json

import pytest

from organizador.excepciones import ConfigError, OrganizadorError
from organizador.reglas import (
    REGLAS_DEL_PAQUETE,
    cargar_reglas,
    clasificar,
    reglas_efectivas,
    ruta_reglas_usuario,
)


@pytest.mark.parametrize(
    "nombre, esperado",
    [
        ("Programacion_java_tema1.pdf", ("Programacion", "Java")),
        ("BaseDeDatos_sql_apuntes.pdf", ("BaseDeDatos", "SQL")),
        ("SistemasInformaticos_redes.pdf", ("SistemasInformaticos", "Redes")),
        ("EntornosDeDesarrollo_git.pdf", ("EntornosDeDesarrollo", "Git")),
        ("LlenguatgeDeMarques_html.pdf", ("LlenguatgeDeMarques", "HTML")),
        ("Ingles_phrasal_verbs.pdf", ("Ingles", "PhrasalVerbs")),
        ("FOL_nomina.pdf", ("FOL", "Nomina")),
        ("IPE_curriculo.pdf", ("IPE", "Curriculo")),
    ],
)
def test_clasifica_asignaturas(nombre, esperado):
    assert clasificar(nombre) == esperado


def test_clasifica_asignatura_sin_tema():
    assert clasificar("programacion_apuntes.pdf") == ("Programacion", "")


def test_no_clasifica_desconocido():
    assert clasificar("apuntes_scan_03.pdf") is None


def test_no_confunde_fol_con_folder():
    assert clasificar("folder_apuntes.pdf") is None


@pytest.mark.parametrize(
    "nombre, esperado",
    [
        ("trabajosql.pdf", ("BaseDeDatos", "SQL")),
        ("contrasql.pdf", ("BaseDeDatos", "SQL")),
        ("trabajo_de_sql.pdf", ("BaseDeDatos", "SQL")),
        ("GithubApuntes.pdf", ("EntornosDeDesarrollo", "Git")),
        ("recipe.pdf", None),
        ("digit.pdf", None),
        ("tema4_ip.pdf", None),
        ("hipotesis_tema2.pdf", None),
    ],
)
def test_matching_compacto_sin_falsos_positivos(nombre, esperado):
    assert clasificar(nombre) == esperado


# --- contrato de la superficie publica de emparejamiento (ADR-002, fase 9B) --


def test_coincide_token_secuencia_exacta():
    from organizador.reglas import coincide_token, trocear

    tokens = trocear("trabajo_de_sql_tema.pdf")
    assert coincide_token(tokens, "sql")
    assert coincide_token(tokens, "trabajo de sql")  # multi-palabra, normalizado
    assert not coincide_token(tokens, "mysql")  # subcadena no es secuencia
    assert not coincide_token(tokens, "IP")  # alias corto: solo palabra completa


def test_coincide_pegado_delegado_del_motor():
    from organizador.reglas import coincide_pegado, trocear

    assert coincide_pegado(trocear("trabajosql.pdf"), "sql")
    assert coincide_pegado(trocear("basededatos.pdf"), "Base de Datos")
    # casos feos historicos: el compacto no es subcadena libre
    assert not coincide_pegado(trocear("folder_apuntes.pdf"), "fol")
    assert not coincide_pegado(trocear("recipe.pdf"), "ipe")
    assert not coincide_pegado(trocear("digit.pdf"), "dit")
    assert not coincide_pegado(trocear("ip_apuntes.pdf"), "ip")  # 2 letras: nunca


def test_trocear_normaliza_y_separa_camelcase():
    from organizador.reglas import trocear

    assert trocear("Base_de_datos-Sql_Tema3.pdf") == [
        "base",
        "de",
        "datos",
        "sql",
        "tema3",
    ]
    assert trocear("sin_extension") == ["sin", "extension"]
    # camelCase roto sobre la parte: `basededatos` (todo minusculas) NO se
    # rompe: un compacto todo minusculo no tiene senales de palabras
    assert trocear("basededatos.pdf") == ["basededatos"]


def test_publicas_y_privadas_no_se_contradicen():
    """Lo que el motor detecta, la API publica lo confirma (sin inventar).

    `aplicar` propone alias usando las publicas; si la publica dijera `si`
    donde el motor dice `no`, la propuesta aceptada no clasificaría. El
    motor recorre el catalogo en orden; aqui se recorre TAMBIEN en orden:
    si la publica casa un alias, la asignatura ganadora del motor es esa
    o una anterior en el catalogo (la publica puede ver mas, nunca menos).
    """
    from organizador.reglas import (
        cargar_reglas,
        coincide_pegado,
        coincide_token,
        explicar_match,
        trocear,
    )

    catalogo = cargar_reglas()
    nombres = [
        "trabajosql.pdf",
        "GithubApuntes.pdf",
        "recipe.pdf",
        "digit.pdf",
        "hipotesis_tema2.pdf",
        "tema4_ip.pdf",
        "folder_apuntes.pdf",
    ]
    for nombre in nombres:
        tokens = trocear(nombre)
        detalle = explicar_match(nombre)
        ganadora = detalle["asignatura"] if detalle else None
        orden = [r.asignatura for r in catalogo]
        for regla in catalogo:
            for alias in regla.aliases:
                casa = coincide_token(tokens, alias) or coincide_pegado(tokens, alias)
                if casa:
                    if ganadora is None:
                        raise AssertionError(
                            "{}: publica casa '{}' (de {}) pero el motor no clasifica".format(
                                nombre, alias, regla.asignatura
                            )
                        )
                    # ganadora del motor <= esta regla en el orden del catalogo
                    assert orden.index(ganadora) <= orden.index(regla.asignatura), (
                        "{}: publica casa '{}' pero el motor gana con '{}'".format(
                            nombre, alias, ganadora
                        )
                    )
                    return  # primera coincidencia confirmada: siguiente nombre


def test_cargar_reglas_personalizadas(tmp_path):
    ruta = tmp_path / "reglas.json"
    ruta.write_text(
        json.dumps(
            [
                {
                    "asignatura": "Digitalizacion",
                    "aliases": ["digitalizacion"],
                    "temas": [{"tema": "Ofimatica", "aliases": ["ofimatica"]}],
                }
            ]
        ),
        encoding="utf-8",
    )

    reglas = cargar_reglas(ruta)

    assert reglas[0].asignatura == "Digitalizacion"
    assert reglas[0].temas == (("Ofimatica", ("ofimatica",)),)


def test_cargar_reglas_json_invalido(tmp_path):
    ruta = tmp_path / "reglas.json"
    ruta.write_text("{no es json", encoding="utf-8")

    with pytest.raises(ConfigError, match="JSON invalido"):
        cargar_reglas(ruta)


def test_cargar_reglas_valida_campos(tmp_path):
    ruta = tmp_path / "reglas.json"
    ruta.write_text(json.dumps([{"asignatura": "X", "aliases": []}]), encoding="utf-8")

    with pytest.raises(ConfigError, match="aliases"):
        cargar_reglas(ruta)


def test_cargar_reglas_fichero_inexistente_es_error_previsible(tmp_path):
    """Caso feo: `--reglas` apunta a una ruta que no existe."""
    with pytest.raises(ConfigError, match="No existe el fichero de reglas"):
        cargar_reglas(tmp_path / "no_existe.json")


def test_cargar_reglas_carpeta_es_error_previsible(tmp_path):
    """Caso feo: la ruta de `--reglas` es una carpeta, no un JSON."""
    carpeta = tmp_path / "una_carpeta"
    carpeta.mkdir()

    with pytest.raises(ConfigError, match="es una carpeta"):
        cargar_reglas(carpeta)


def test_todo_error_de_reglas_es_organizador_error(tmp_path):
    """Un error de config nunca debe escapar como excepción no prevista."""
    ruta = tmp_path / "reglas.json"
    ruta.write_text("{no es json", encoding="utf-8")

    with pytest.raises(OrganizadorError):
        cargar_reglas(ruta)


def _regla_digitalizacion(ruta):
    ruta.write_text(
        json.dumps(
            [
                {
                    "asignatura": "Digitalizacion",
                    "aliases": ["digitalizacion"],
                    "temas": [{"tema": "Ofimatica", "aliases": ["ofimatica"]}],
                }
            ]
        ),
        encoding="utf-8",
    )


def test_clasificar_con_reglas_personalizadas(tmp_path):
    ruta = tmp_path / "reglas.json"
    _regla_digitalizacion(ruta)
    reglas = cargar_reglas(ruta)

    assert clasificar("Digitalizacion_ofimatica.pdf", reglas) == (
        "Digitalizacion",
        "Ofimatica",
    )
    assert clasificar("FOL_nomina.pdf", reglas) is None


def test_reglas_efectivas_explicitas(tmp_path):
    ruta = tmp_path / "reglas.json"
    _regla_digitalizacion(ruta)

    reglas = reglas_efectivas(ruta)

    assert [r.asignatura for r in reglas] == ["Digitalizacion"]


def test_reglas_efectivas_fusiona_usuario(tmp_path, monkeypatch):
    usuario = ruta_reglas_usuario()
    usuario.parent.mkdir(parents=True, exist_ok=True)
    _regla_digitalizacion(usuario)

    reglas = reglas_efectivas()
    nombres = [r.asignatura for r in reglas]

    assert nombres[0] == "Digitalizacion"
    assert "Programacion" in nombres
    assert "FOL" in nombres


def test_reglas_efectivas_usuario_sobrescribe(tmp_path, monkeypatch):
    usuario = ruta_reglas_usuario()
    usuario.parent.mkdir(parents=True, exist_ok=True)
    usuario.write_text(
        json.dumps(
            [
                {
                    "asignatura": "FOL",
                    "aliases": ["fol"],
                    "temas": [{"tema": "Custom", "aliases": ["custom"]}],
                }
            ]
        ),
        encoding="utf-8",
    )

    reglas = reglas_efectivas()
    fol = [r for r in reglas if r.asignatura == "FOL"]

    assert len(fol) == 1
    assert fol[0].temas == (("Custom", ("custom",)),)


# --- Catalogo empaquetado: el JSON del paquete es parte de la CLI ----------
# Si `reglas.json` se corrompe (alias vacio, asignatura duplicada, campo que
# falta), la CLI instalada deja de clasificar sin dejar de pasar las pruebas
# de logica. Estas pruebas son el candado del artefacto.

ESPERANZA_CATALOGO = {
    "Programacion": ["Java", "Python", "Algoritmos", "EstructurasDeDatos"],
    "BaseDeDatos": ["SQL", "ModeloEntidadRelacion", "Normalizacion"],
    "SistemasInformaticos": ["Hardware", "Redes", "SistemasOperativos"],
    "EntornosDeDesarrollo": ["Git", "Testing", "Refactorizacion"],
    "LlenguatgeDeMarques": ["HTML", "CSS", "XML"],
    "Ingles": ["PhrasalVerbs", "Vocabulario", "Gramatica"],
    "FOL": ["PrevencionRiesgos", "DerechoLaboral", "Nomina"],
    "IPE": ["Curriculo", "Entrevista", "Empleabilidad"],
}


def test_catalogo_del_paque_no_esta_corrupto():
    assert len(REGLAS_DEL_PAQUETE) == len(ESPERANZA_CATALOGO)
    nombres = [r.asignatura for r in REGLAS_DEL_PAQUETE]
    assert len(set(nombres)) == len(nombres), "asignaturas duplicadas"
    assert set(nombres) == set(ESPERANZA_CATALOGO)
    for regla in REGLAS_DEL_PAQUETE:
        assert regla.aliases, f"{regla.asignatura} sin aliases"
        assert all(a.strip().lower() == a for a in regla.aliases), (
            f"alias sin normalizar en {regla.asignatura}"
        )
        temas = {t[0] for t in regla.temas}
        assert temas == set(ESPERANZA_CATALOGO[regla.asignatura])


@pytest.mark.parametrize("asignatura", sorted(ESPERANZA_CATALOGO))
def test_cada_asignatura_del_catalogo_se_detecta_por_su_nombre(asignatura):
    assert clasificar(f"{asignatura}_tema1.pdf") == (asignatura, "")
