"""Enruta los mensajes de Qt al logging de la aplicación.

Qt imprime sus avisos (warnings/errores de red, imágenes, etc.) por stderr. Este
módulo instala un ``qInstallMessageHandler`` que los captura y los pasa al
``logging`` de Python, clasificándolos por severidad y categoría para que el
ruido esperado (p. ej. logos rotos de CDNs) no aparezca como error.
"""

import logging

from PyQt6.QtCore import QMessageLogContext, QtMsgType, qInstallMessageHandler

_LOGGER = logging.getLogger("qt")

# Categorías de Qt cuyo ruido es esperado y no indica un problema de la app.
_NOISE_CATEGORY_PREFIXES = ("qt.network", "qt.gui.imageio")

# Mensajes de ruido conocido (conexiones SSL cerradas a medias por CDNs).
_NOISE_MESSAGE_MARKERS = ("QSslSocket", "device not open")

_SEVERITY = {
    QtMsgType.QtDebugMsg: logging.DEBUG,
    QtMsgType.QtInfoMsg: logging.INFO,
    QtMsgType.QtWarningMsg: logging.WARNING,
    QtMsgType.QtCriticalMsg: logging.ERROR,
    QtMsgType.QtFatalMsg: logging.CRITICAL,
}


def classify_qt_message(
    msg_type: QtMsgType, category: str, message: str
) -> int:
    """Devuelve el nivel de logging para un mensaje de Qt.

    Los avisos (warning) de categorías/mensajes de red e imagen se degradan a
    INFO porque son ruido esperado (logos/CDNs fallidos), no fallos de la app.
    Los critical/fatal nunca se degradan.
    """
    level = _SEVERITY.get(msg_type, logging.INFO)
    if level == logging.WARNING and _is_noise(category, message):
        return logging.INFO
    return level


def _is_noise(category: str, message: str) -> bool:
    return category.startswith(_NOISE_CATEGORY_PREFIXES) or any(
        marker in message for marker in _NOISE_MESSAGE_MARKERS
    )


def _handler(msg_type: QtMsgType, context: QMessageLogContext, message: str) -> None:
    category = context.category or "default"
    level = classify_qt_message(msg_type, category, message)
    _LOGGER.log(level, "Qt [%s] %s", category, message)


def install_qt_message_handler() -> None:
    """Instala el handler que redirige los mensajes de Qt al logging."""
    qInstallMessageHandler(_handler)
