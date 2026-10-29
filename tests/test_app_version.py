"""El recurso de versión del ejecutable debe coincidir con APP_VERSION."""

import re
from pathlib import Path

from src.infrastructure.ui.main_window import APP_VERSION

RAIZ = Path(__file__).resolve().parents[1]
VERSION_INFO = RAIZ / "version_info.txt"


def _numeros(texto: str) -> tuple[int, ...]:
    return tuple(int(parte) for parte in texto.replace(" ", "").split(","))


def test_version_info_matches_app_version():
    """Si se sube la versión en un sitio y no en el otro, Windows miente."""
    contenido = VERSION_INFO.read_text(encoding="utf-8")
    esperado = tuple(int(parte) for parte in APP_VERSION.split(".")) + (0,)

    for clave in ("filevers", "prodvers"):
        encontrado = re.search(rf"{clave}=\(([^)]*)\)", contenido)
        assert encontrado, f"version_info.txt no define {clave}"
        assert _numeros(encontrado.group(1)) == esperado

    for clave in ("FileVersion", "ProductVersion"):
        assert f"StringStruct('{clave}', '{APP_VERSION}')" in contenido
