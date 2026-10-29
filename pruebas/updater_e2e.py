"""Prueba de punta a punta del auto-update contra la release real.

Usa exactamente el mismo código que la app: consulta la release, elige el
instalador, lo descarga verificando el SHA-256 y lo lanza con las banderas
silenciosas. Sirve para validar el camino completo sin esperar a que la
interfaz lo dispare.
"""

import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, r"K:\IPTVViewer")

import requests

from src.infrastructure.utils.updater import (
    RELEASES_API,
    download,
    parse_release,
    setup_arguments,
)

VERSION_INSTALADA = "1.9.0"

respuesta = requests.get(
    RELEASES_API, timeout=10, headers={"User-Agent": f"IPTVViewer/{VERSION_INSTALADA}"}
)
respuesta.raise_for_status()
info = parse_release(respuesta.json(), VERSION_INSTALADA)
if info is None:
    print("No hay actualización disponible")
    sys.exit(0)

print(f"Actualización disponible: {info.version}")
print(f"Asset: {info.asset_name}")
print(f"Digest: {info.digest}")

destino = Path(tempfile.gettempdir()) / info.asset_name


def progreso(hechos: int, total: int) -> None:
    if total:
        print(f"  descargando {hechos * 100 // total}% ({hechos // 1048576}/{total // 1048576} MB)")


ruta = download(info.asset_url, destino, info.digest, progress=progreso)
print(f"Descarga verificada: {ruta}")

print("Lanzando el instalador silencioso...")
resultado = subprocess.run([str(ruta), *setup_arguments()], check=False)
print(f"Instalador terminado con código {resultado.returncode}")
