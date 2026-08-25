"""Diálogo de resolución de VLC ausente (motor vlc sin libvlc.dll).

Cuando el motor activo es ``vlc`` pero libvlc.dll no está disponible, la app
no puede reproducir. Este módulo ofrece el diálogo modal con las 6 opciones de
resolución (usar mpv, señalar carpeta, instalar completo, instalar portátil,
reintentar, salir) y las acciones que ejecutan: descarga portátil con barra de
progreso, lanzamiento del instalador oficial y selección manual de carpeta.
El módulo de bootstrap subyacente (``vlc_bootstrap``) es puro y no importa PyQt.
"""

import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import requests
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QLabel,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QVBoxLayout,
)

from src.infrastructure.utils.vlc_bootstrap import (
    VLC_EXE_URL,
    VLC_VERSION,
    VlcBootstrapError,
    configure_vlc_env,
    install_vlc_portable,
)

_CHUNK_SIZE = 256 * 1024
_DOWNLOAD_TIMEOUT = 120

_logger = logging.getLogger(__name__)

# (clave interna, etiqueta de botón) — orden y textos fijos de la decisión.
OPTIONS: tuple[tuple[str, str], ...] = (
    ("mpv", "Usar mpv"),
    ("point", "Señalar carpeta de VLC"),
    ("install_full", "Instalar VLC completo"),
    ("install_portable", "Instalar VLC portátil"),
    ("retry", "Reintentar"),
    ("exit", "Salir"),
)


def resolve_vlc(parent=None, mpv_available: bool = True) -> str:
    """Diálogo modal con las 6 opciones para resolver VLC ausente.

    "Usar mpv" solo se habilita si ``mpv_available``. Devuelve una de:
    ``'mpv'``, ``'point'``, ``'install_full'``, ``'install_portable'``,
    ``'retry'``, ``'exit'``. Si se cierra el diálogo sin elegir (X), equivale
    a ``'exit'``.
    """
    dialog = QDialog(parent)
    dialog.setWindowTitle("VLC no está disponible")
    dialog.setWindowModality(Qt.WindowModality.WindowModal)
    dialog.setModal(True)
    chosen: dict[str, str | None] = {"key": None}

    def _choose(key: str) -> None:
        chosen["key"] = key
        dialog.accept()

    layout = QVBoxLayout(dialog)
    message = QLabel(
        "VLC no está disponible en este equipo.\n"
        "Sin VLC no se puede reproducir con el motor VLC.\n"
        "Elige cómo resolverlo:",
        dialog,
    )
    message.setWordWrap(True)
    layout.addWidget(message)
    for key, label in OPTIONS:
        button = QPushButton(label, dialog)
        if key == "mpv":
            button.setEnabled(mpv_available)
        button.clicked.connect(lambda _checked=False, k=key: _choose(k))
        layout.addWidget(button)
    dialog.exec()
    return chosen["key"] if chosen["key"] is not None else "exit"


def run_portable_install(parent=None) -> bool:
    """Descarga y extrae VLC portátil con barra de progreso. True si quedó listo."""
    _logger.info("VLC: instalando VLC %s portátil...", VLC_VERSION)
    dialog = QProgressDialog(
        f"Descargando VLC {VLC_VERSION} portátil (~191 MB)...",
        "Cancelar",
        0,
        100,
        parent,
    )
    dialog.setWindowTitle("IPTVViewer")
    dialog.setWindowModality(Qt.WindowModality.WindowModal)
    dialog.setMinimumDuration(0)
    dialog.setAutoReset(False)
    dialog.setAutoClose(False)
    dialog.show()

    def _on_progress(downloaded: int, total: int) -> None:
        if total > 0:
            dialog.setValue(min(100, int(downloaded * 100 / total)))
        QApplication.processEvents()

    failed = False
    try:
        vlc_dir = install_vlc_portable(progress=_on_progress)
        configure_vlc_env(vlc_dir)
    except VlcBootstrapError as exc:
        _logger.error("VLC: fallo al instalar VLC portátil: %s", exc)
        failed = True
    finally:
        dialog.close()

    if dialog.wasCanceled() or failed:
        _logger.warning("VLC: VLC portátil no quedó disponible.")
        return False
    return True


def run_full_install(parent=None) -> bool:
    """Descarga el instalador oficial de VLC y lo lanza. True si se lanzó.

    El instalador se guarda en el directorio temporal del sistema y se abre
    con ``os.startfile`` (Windows) para que el usuario complete el asistente.
    """
    _logger.info("VLC: descargando instalador oficial %s...", VLC_EXE_URL)
    installer = Path(tempfile.gettempdir()) / f"vlc-{VLC_VERSION}-win64.exe"
    try:
        _download_installer(installer)
    except Exception as exc:
        _logger.error("VLC: fallo al descargar el instalador: %s", exc)
        QMessageBox.critical(
            parent, "VLC", f"No se pudo descargar el instalador de VLC:\n{exc}"
        )
        return False

    try:
        if sys.platform == "win32":
            os.startfile(installer)  # type: ignore[attr-defined]  # solo Windows
        else:
            subprocess.Popen([str(installer)])
    except OSError as exc:
        _logger.error("VLC: no se pudo lanzar el instalador: %s", exc)
        QMessageBox.critical(
            parent, "VLC", f"No se pudo lanzar el instalador de VLC:\n{exc}"
        )
        return False

    QMessageBox.information(
        parent,
        "Instalador de VLC lanzado",
        "Completa el asistente de instalación de VLC y pulsa "
        "'Reintentar' cuando termine.",
    )
    return True


def point_vlc_folder(parent=None) -> Path | None:
    """Deja elegir la carpeta con ``libvlc.dll``, la valida y configura el entorno.

    Devuelve la carpeta elegida si contiene ``libvlc.dll`` (y la deja lista
    para python-vlc); None si se cancela o la carpeta no es válida.
    """
    folder = QFileDialog.getExistingDirectory(
        parent, "Señala la carpeta de VLC que contiene libvlc.dll"
    )
    if not folder:
        return None
    folder_path = Path(folder)
    if not (folder_path / "libvlc.dll").is_file():
        QMessageBox.warning(
            parent,
            "Carpeta no válida",
            f"No se encontró libvlc.dll en:\n{folder_path}\n"
            "Elige la carpeta de VLC que contiene libvlc.dll.",
        )
        return None
    configure_vlc_env(folder_path)
    _logger.info("VLC: usando VLC de %s", folder_path)
    return folder_path


def _download_installer(dest: Path) -> None:
    """Descarga ``VLC_EXE_URL`` a ``dest`` (sin barra de progreso)."""
    with requests.get(VLC_EXE_URL, stream=True, timeout=_DOWNLOAD_TIMEOUT) as resp:
        resp.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=_CHUNK_SIZE):
                if chunk:
                    f.write(chunk)
