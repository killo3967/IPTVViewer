"""Fábrica de adaptadores de reproducción con proxy normalizado."""

from src.infrastructure.utils.proxy import get_standardized_proxy_config


def build_player_adapter(engine, vlc_config, mpv_config, proxy_config, vlc_cls, mpv_cls):
    """Construye el adaptador del motor seleccionado.

    ``proxy_config`` se normaliza (tor -> socks5 local) antes de pasarlo al
    adaptador, de modo que VLC reciba ``--socks=127.0.0.1:<port>`` y mpv reciba
    la config normalizada (aunque FFmpeg no soporte SOCKS).

    ``vlc_cls`` y ``mpv_cls`` se inyectan para poder testear sin las DLLs reales.

    ``'mpv'`` carga la variante genérica (sin AVX2) y ``'mpv-v3'`` la variante
    AVX2; ambos pasan ``variant`` al adaptador mpv.
    """
    std_proxy = get_standardized_proxy_config(proxy_config)
    if engine == 'mpv':
        return mpv_cls(mpv_config=mpv_config, proxy_config=std_proxy, variant='generic')
    if engine == 'mpv-v3':
        return mpv_cls(mpv_config=mpv_config, proxy_config=std_proxy, variant='v3')
    return vlc_cls(vlc_config=vlc_config, proxy_config=std_proxy)
