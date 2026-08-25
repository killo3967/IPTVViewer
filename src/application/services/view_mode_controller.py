"""Servicio de modos de vista — controlador puro sin dependencias de Qt.

REQ-1: la máquina de estados de modos de vista es un servicio de aplicación
Qt-free: estado, serialización, resolución de índice de zapping y helpers de
geometría/estado de splitter viven aquí, con tipos tuples/str/bytes únicamente.
"""
from collections.abc import Callable, Sequence
from enum import Enum


class ViewMode(Enum):
    """Modos de layout exclusivos de la ventana principal."""

    NORMAL = "normal"
    COMPACT = "compact"
    VIDEO = "video"

    @classmethod
    def parse(cls, raw: object) -> "ViewMode":
        """Convierte un valor persistido en ViewMode; desconocido/None -> NORMAL.

        Nunca lanza excepción (REQ-1: valores desconocidos caen a NORMAL).
        """
        try:
            return cls(raw)
        except (ValueError, TypeError):
            return cls.NORMAL


class ViewModeController:
    """Máquina de estados del modo de vista (REQ-1)."""

    def __init__(self, initial: ViewMode = ViewMode.NORMAL):
        self._mode = initial
        self._listeners: list[Callable[[ViewMode, ViewMode], None]] = []

    @property
    def mode(self) -> ViewMode:
        return self._mode

    def register_listener(self, listener: Callable[[ViewMode, ViewMode], None]) -> None:
        self._listeners.append(listener)

    def activate(self, mode: ViewMode) -> bool:
        """Activa un modo. Devuelve True solo si el estado cambió.

        Re-activar el modo activo es un no-op: no notifica listeners (REQ-1).
        """
        if mode == self._mode:
            return False
        old = self._mode
        self._mode = mode
        self._notify(old, mode)
        return True

    def _notify(self, old: ViewMode, new: ViewMode) -> None:
        for listener in self._listeners:
            listener(old, new)


def resolve_zap_index(
    channels: Sequence, current_channel, direction: int
) -> int | None:
    """Resuelve el índice destino de zapping con wrap-around (REQ-5).

    - Lista vacía -> ``None`` (el llamador hace no-op).
    - Sin canal actual (o actual no encontrado) -> ``0``.
    - Coincidencia por URL primero y luego por igualdad total del dataclass.
    - ``direction`` se normaliza a +/-1; los bordes envuelven (módulo).
    """
    if not channels:
        return None
    if current_channel is None:
        return 0

    index = None
    for i, channel in enumerate(channels):
        if channel.url == current_channel.url:
            index = i
            break
    if index is None:
        for i, channel in enumerate(channels):
            if channel == current_channel:
                index = i
                break
    if index is None:
        return 0

    step = 1 if direction >= 0 else -1
    return (index + step) % len(channels)


def geometry_to_str(x: int, y: int, w: int, h: int) -> str:
    """Serializa una geometría como ``"x,y,w,h"`` (REQ-8)."""
    return f"{x},{y},{w},{h}"


def str_to_geometry(raw: str) -> tuple[int, int, int, int] | None:
    """Parsea ``"x,y,w,h"`` a tupla; devuelve ``None`` ante cualquier error.

    ``x``/``y`` pueden ser negativos (multi-monitor); ``w``/``h`` deben ser > 0.
    Nunca lanza excepción.
    """
    parts = raw.split(",")
    if len(parts) != 4:
        return None
    try:
        x, y, w, h = (int(part) for part in parts)
    except ValueError:
        return None
    if w <= 0 or h <= 0:
        return None
    return (x, y, w, h)


def encode_splitter_state(state: bytes) -> str:
    """Codifica ``QSplitter.saveState()`` en base64 ASCII (REQ-8)."""
    import base64

    return base64.b64encode(state).decode("ascii")


def decode_splitter_state(encoded: str) -> bytes | None:
    """Decodifica el estado base64 del splitter; ``None`` ante cualquier error.

    Nunca lanza excepción (un ``config.ini`` corrupto no debe romper el arranque).
    """
    import base64

    if not encoded:
        return None
    try:
        return base64.b64decode(encoded)
    except (ValueError, TypeError):
        return None
