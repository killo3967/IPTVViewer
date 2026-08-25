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
    ensure_libmpv_dll,
    is_libmpv_available,
)

_logger = logging.getLogger(__name__)


def _download_mpv_dialog(parent=None) -> str | None:
    """Muestra la barra de progreso y descarga libmpv-2.dll.

    Devuelve ``None`` si quedó lista, o un mensaje de error si falló/canceló.
    """
    bin_dir = default_bin_dir()
    _logger.info("MPV: libmpv-2.dll no encontrada. Descargando motor mpv...")
    dialog = QProgressDialog("Descargando motor mpv...", "Cancelar", 0, 100, parent)
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
        ensure_libmpv_dll(bin_dir, progress=_on_progress)
    except Exception as e:
        _logger.error("MPV: fallo al descargar libmpv-2.dll: %s", e)
        error_msg = str(e)
    finally:
        dialog.close()

    if dialog.wasCanceled():
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


def ensure_mpv_engine(engine: str, parent=None) -> str:
    """Garantiza que el motor mpv tenga ``libmpv-2.dll`` antes de usarlo.

    Si el motor no es ``'mpv'``, devuelve el motor sin cambios. Si es mpv y la
    DLL falta, la descarga; si falla o el usuario cancela, devuelve ``'vlc'``
    como fallback (nunca deja la app sin motor de reproducción).
    """
    if engine != "mpv":
        return engine
    return "mpv" if ensure_mpv_available(parent) else "vlc"
