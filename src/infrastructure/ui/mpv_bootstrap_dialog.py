"""Diálogo de progreso + descarga de libmpv-2.dll (motor mpv).

Extrae la lógica de UI que garantiza la DLL antes de usar el motor mpv, para
reutilizarla tanto en el arranque (``main.py``) como al cambiar de motor en
runtime (``main_window.py``). El módulo de bootstrap subyacente
(``mpv_dll_bootstrap``) es puro y no importa PyQt.
"""

import logging

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QMessageBox, QProgressDialog

from src.infrastructure.utils.mpv_dll_bootstrap import (
    default_bin_dir,
    default_bin_v3_dir,
    ensure_libmpv_dll,
    ensure_libmpv_v3_dll,
    is_libmpv_available,
    is_libmpv_v3_available,
)

_logger = logging.getLogger(__name__)


def _download_mpv_dialog(parent=None, variant: str = "generic") -> str | None:
    """Muestra la barra de progreso y descarga libmpv-2.dll de ``variant``.

    Devuelve ``None`` si quedó lista, o un mensaje de error si falló/canceló.
    """
    if variant == "v3":
        bin_dir = default_bin_v3_dir()
        label = "Descargando motor mpv (AVX2)..."
    else:
        bin_dir = default_bin_dir()
        label = "Descargando motor mpv..."
    _logger.info("MPV: libmpv-2.dll no encontrada. %s", label)
    dialog = QProgressDialog(label, "Cancelar", 0, 100, parent)
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

    error_msg = None
    try:
        if variant == "v3":
            ensure_libmpv_v3_dll(bin_dir, progress=_on_progress)
        else:
            ensure_libmpv_dll(bin_dir, progress=_on_progress)
    except Exception as e:
        _logger.error("MPV: fallo al descargar libmpv-2.dll: %s", e)
        error_msg = str(e)
    finally:
        canceled = dialog.wasCanceled()
        dialog.close()

    if canceled:
        return "Descarga cancelada."
    return error_msg


def ensure_mpv_available(parent=None) -> bool:
    """Descarga libmpv-2.dll si falta, con barra de progreso.

    Se invoca al arrancar (independientemente del motor activo) para que el
    usuario que luego cambie a mpv ya lo tenga. No bloquea la app si falla:
    solo avisa. Devuelve True si mpv quedó disponible.
    """
    if is_libmpv_available(default_bin_dir()):
        return True

    error = _download_mpv_dialog(parent)
    if error:
        QMessageBox.warning(
            parent,
            "Motor mpv no disponible",
            "No se pudo descargar el motor mpv (libmpv-2.dll).\n\n"
            f"Detalle: {error}\n\n"
            "Podrás reproducir con VLC si está instalado.",
        )
        return False
    return True


def ensure_mpv_v3_available(parent=None) -> bool:
    """Descarga libmpv-2.dll (variante v3/AVX2) si falta, con barra de progreso.

    Análoga a ``ensure_mpv_available`` pero para la variante AVX2 en ``bin-v3/``.
    """
    if is_libmpv_v3_available():
        return True

    error = _download_mpv_dialog(parent, variant="v3")
    if error:
        QMessageBox.warning(
            parent,
            "Motor mpv (AVX2) no disponible",
            "No se pudo descargar el motor mpv con AVX2 (libmpv-2.dll v3).\n\n"
            f"Detalle: {error}\n\n"
            "Podrás reproducir con mpv (sin AVX2) o VLC.",
        )
        return False
    return True


def ensure_mpv_engine(engine: str, parent=None) -> str:
    """Garantiza que el motor mpv (genérico o v3) tenga su ``libmpv-2.dll``.

    Si el motor no es mpv, lo devuelve sin cambios. Para ``'mpv'`` descarga la
    variante genérica y para ``'mpv-v3'`` la variante AVX2. Ante fallo/cancelación
    devuelve un motor alternativo (nunca deja la app sin reproducción).
    """
    if engine == "mpv":
        return "mpv" if ensure_mpv_available(parent) else "vlc"
    if engine == "mpv-v3":
        if ensure_mpv_v3_available(parent):
            return "mpv-v3"
        return "mpv" if ensure_mpv_available(parent) else "vlc"
    return engine
