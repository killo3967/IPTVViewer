"""Regresión: el ruido de torpy durante el bootstrap no debe registrarse como ERROR.

Al activar el proxy Tor, torpy prueba varios routers para construir el circuito.
Cada fallo (timeout, conexión rechazada) se registraba como ERROR con traceback
completo ('[ignored]' + 'Retry with another router...'), y los cierres de
conexión de clientes del servidor SOCKS como ERROR ('[socks] Some error').
Son comportamientos esperados y controlados por torpy; la app los degrada a
DEBUG (visibles solo con logging de diagnóstico activado).
"""

import logging

from src.infrastructure.utils import proxy as proxy_module  # noqa: F401 (aplica parches)

_NOISE_ARGS = (
    (TimeoutError, TimeoutError("timed out"), None),
    "Retry with another router...",
)


def _no_error_records(caplog):
    return [r for r in caplog.records if r.levelno >= logging.ERROR]


def test_torpy_utils_log_retry_is_downgraded_to_debug(caplog):
    """El reintento de bootstrap registrado por torpy.utils no emite ERROR."""
    from torpy import utils as torpy_utils

    with caplog.at_level(logging.DEBUG, logger="torpy.utils"):
        torpy_utils.log_retry(*_NOISE_ARGS)

    assert _no_error_records(caplog) == []


def test_torpy_consensus_log_retry_reference_is_downgraded_to_debug(caplog):
    """consesus.py importa log_retry por nombre y lo captura en partials;
    esa referencia también debe quedar degradada a DEBUG."""
    from torpy import consesus as torpy_consesus

    with caplog.at_level(logging.DEBUG, logger="torpy.utils"):
        torpy_consesus.log_retry(*_NOISE_ARGS)

    assert _no_error_records(caplog) == []


def test_torpy_socks_error_is_silenced_from_log(caplog):
    """Los ERROR con traceback del servidor SOCKS de torpy ('[socks] Some error',
    resets/cierres de clientes) no deben aparecer en el log."""
    from torpy.cli import socks as torpy_socks_module

    with caplog.at_level(logging.DEBUG):
        torpy_socks_module.logger.exception("[socks] Some error")

    assert _no_error_records(caplog) == []
