import sys
import logging
import configparser
from pathlib import Path
from datetime import datetime
from PyQt6.QtWidgets import QApplication

# Importaciones de la nueva arquitectura
from src.infrastructure.adapters.vlc_player_adapter import VlcPlayerAdapter
from src.infrastructure.adapters.mpv_player_adapter import MpvPlayerAdapter
from src.infrastructure.adapters.file_m3u_repository import FileM3URepository
from src.infrastructure.adapters.xmltv_repository import XMLTVRepository
from src.infrastructure.adapters.qt_logo_loader_adapter import QtLogoLoaderAdapter
from src.application.services.playlist_loader import PlaylistLoader
from src.application.services.playback_manager import PlaybackManager
from src.application.services.epg_manager import EPGManager
from src.infrastructure.ui.main_window import IPTVMainWindow

# Configuración básica de rutas
if getattr(sys, 'frozen', False):
    SCRIPT_DIR = Path(sys.executable).parent.resolve()
else:
    SCRIPT_DIR = Path(__file__).parent.resolve()
CONFIG_FILE = SCRIPT_DIR / 'config.ini'
LOG_DIR = SCRIPT_DIR / 'logs'

def setup_logger():
    """Configura el sistema de logging forzando la salida a archivo y consola."""
    LOG_DIR.mkdir(exist_ok=True)
    log_file = LOG_DIR / 'iptv_viewer.log'
    
    # Creamos los handlers manualmente para mayor control
    handlers = [
        logging.FileHandler(str(log_file), encoding='utf-8', mode='a'),
        logging.StreamHandler(sys.stdout)
    ]
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=handlers,
        force=True  # Importante: fuerza la configuración si ya se inició antes
    )
    logging.info(f"\n{'='*60}\nNUEVA SESIÓN: {datetime.now()}\n{'='*60}")

def load_config():
    """Carga configuración .ini con soporte para formato antiguo (migración automática)."""
    parser = configparser.ConfigParser()
    if CONFIG_FILE.exists():
        parser.read(CONFIG_FILE, encoding='utf-8')

    # Asegurar secciones
    if 'SETTINGS' not in parser:
        parser['SETTINGS'] = {}
    if 'VLC' not in parser:
        parser['VLC'] = {}
    if 'MPV' not in parser:
        parser['MPV'] = {}
    if 'PROXY' not in parser:
        parser['PROXY'] = {}

    hw_accel = parser.getboolean('SETTINGS', 'hw_acceleration', fallback=False)
    player_engine = parser.get('SETTINGS', 'player_engine', fallback='vlc')

    # --- Migrar formato antiguo si es necesario ---
    has_new_format = parser.has_section('source.0')

    if not has_new_format and parser.has_option('SETTINGS', 'm3u_source'):
        logging.info("Detectado config.ini antiguo. Migrando a formato de fuentes por nombre...")
        old_m3u = parser.get('SETTINGS', 'm3u_source', fallback='m3u/tv_channel.m3u')
        old_filter = parser.get('SETTINGS', 'filter_group', fallback='SPAIN')
        old_epg = parser.get('SETTINGS', 'epg_url', fallback='')
        old_sources_str = parser.get('SETTINGS', 'sources', fallback=old_m3u)
        old_sources = [s.strip() for s in old_sources_str.split(',') if s.strip()]
        if old_m3u not in old_sources:
            old_sources.append(old_m3u)

        sources = {}
        for i, url in enumerate(old_sources):
            filename = url.split('/')[-1] if '/' in url else url
            # Quitar extensión para nombre más limpio
            name = filename.rsplit('.', 1)[0] if '.' in filename else filename
            sources[i] = {
                'name': name,
                'm3u': url,
                'filter': old_filter,
                'epg': old_epg
            }
        active = 0
        logging.info(f"Migración completada: {len(sources)} fuente(s) convertida(s).")
    else:
        # --- Cargar formato nuevo ---
        sources = {}
        i = 0
        while parser.has_section(f'source.{i}'):
            sec = f'source.{i}'
            sources[i] = {
                'name': parser.get(sec, 'name', fallback=f'Lista {i+1}'),
                'm3u': parser.get(sec, 'm3u', fallback=''),
                'filter': parser.get(sec, 'filter', fallback=''),
                'epg': parser.get(sec, 'epg', fallback='')
            }
            i += 1

        active = parser.getint('SETTINGS', 'active', fallback=0)
        if active not in sources:
            active = 0

        if not sources:
            # Sin fuentes: crear una por defecto
            sources[0] = {
                'name': 'TV España',
                'm3u': 'http://192.168.1.46:34400/m3u/xteve.m3u',
                'filter': 'SPAIN',
                'epg': 'http://192.168.1.46:34400/xmltv/xteve.xml'
            }
            active = 0

    # Configuración VLC
    vlc_config = {
        "reset_plugins_cache": parser.getboolean('VLC', 'reset_plugins_cache', fallback=True),
        "network_caching": parser.getint('VLC', 'network_caching', fallback=5000),
        "clock_jitter": parser.getint('VLC', 'clock_jitter', fallback=500),
        "clock_synchro": parser.getint('VLC', 'clock_synchro', fallback=0),
        "drop_late_frames": parser.getboolean('VLC', 'drop_late_frames', fallback=False),
        "skip_frames": parser.getboolean('VLC', 'skip_frames', fallback=False),
        "repeat": parser.getboolean('VLC', 'repeat', fallback=True),
        "log_verbose": parser.getint('VLC', 'log_verbose', fallback=2),
        "file_logging": parser.getboolean('VLC', 'file_logging', fallback=True),
        "logfile": parser.get('VLC', 'logfile', fallback='logs/vlc.log'),
        "hw_acceleration": hw_accel
    }

    # Configuración MPV
    mpv_config = {
        "network_caching": parser.getint('MPV', 'network_caching', fallback=5000),
        "hw_acceleration": hw_accel,
        "cache": parser.getboolean('MPV', 'cache', fallback=True),
        "demuxer_readahead_secs": parser.getfloat('MPV', 'demuxer_readahead_secs', fallback=5.0),
        "user_agent": parser.get('MPV', 'user_agent', fallback="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"),
        "log_level": parser.get('MPV', 'log_level', fallback='info'),
        "logfile": parser.get('MPV', 'logfile', fallback='logs/mpv.log'),
        "file_logging": parser.getboolean('MPV', 'file_logging', fallback=True)
    }

    # Configuración Proxy
    proxy_config = {
        "enabled": parser.getboolean('PROXY', 'enabled', fallback=False),
        "type": parser.get('PROXY', 'type', fallback='http'),
        "server": parser.get('PROXY', 'server', fallback=''),
        "port": parser.getint('PROXY', 'port', fallback=8080),
        "username": parser.get('PROXY', 'username', fallback=''),
        "password": parser.get('PROXY', 'password', fallback=''),
        "bypass_local": parser.getboolean('PROXY', 'bypass_local', fallback=True),
        "bypass_local_subnet": parser.getboolean('PROXY', 'bypass_local_subnet', fallback=False),
        "custom_bypass": parser.get('PROXY', 'custom_bypass', fallback='')
    }

    return {
        'sources': sources,
        'active': active,
        'hw_acceleration': hw_accel,
        'player_engine': player_engine,
        'vlc_config': vlc_config,
        'mpv_config': mpv_config,
        'proxy_config': proxy_config
    }


def _get_active_source(config_data: dict) -> dict:
    """Retorna la fuente activa."""
    return config_data['sources'].get(config_data['active'], {})


def get_active_m3u(config_data: dict) -> str:
    """Retorna la URL M3U de la fuente activa."""
    return _get_active_source(config_data).get('m3u', '')


def get_active_filter(config_data: dict) -> str:
    """Retorna el filtro de la fuente activa."""
    return _get_active_source(config_data).get('filter', '')


def get_active_epg(config_data: dict) -> str:
    """Retorna la URL EPG de la fuente activa."""
    return _get_active_source(config_data).get('epg', '')

def save_config(config_data):
    """Guarda los cambios de configuración en config.ini (formato nuevo con fuentes por nombre)."""
    parser = configparser.ConfigParser()

    # Ajustes generales
    parser['SETTINGS'] = {
        'active': str(config_data.get('active', 0)),
        'hw_acceleration': str(config_data.get('hw_acceleration', False)),
        'player_engine': config_data.get('player_engine', 'vlc'),
    }

    # Fuentes M3U (con nombre)
    for idx, src in config_data.get('sources', {}).items():
        parser[f'source.{idx}'] = {
            'name': src.get('name', f'Lista {idx+1}'),
            'm3u': src.get('m3u', ''),
            'filter': src.get('filter', ''),
            'epg': src.get('epg', ''),
        }

    # Ajustes específicos de VLC
    vlc_config = config_data.get('vlc_config', {})
    parser['VLC'] = {k: str(v) for k, v in vlc_config.items()}

    # Ajustes específicos de MPV
    mpv_config = config_data.get('mpv_config', {})
    parser['MPV'] = {k: str(v) for k, v in mpv_config.items()}

    # Ajustes específicos de Proxy
    proxy_config = config_data.get('proxy_config', {})
    parser['PROXY'] = {k: str(v) for k, v in proxy_config.items()}

    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        parser.write(f)
    logging.info("Configuración guardada correctamente.")

from src.infrastructure.utils.proxy import setup_proxy, get_standardized_proxy_config

def main():
    # 1. Setup inicial
    setup_logger()
    config = load_config()
    setup_proxy(config.get('proxy_config'))
    
    # 2. Inicializar Qt
    app = QApplication(sys.argv)
    
    # 3. Instanciar Adaptador según configuración (Normalizando config de proxy)
    engine = config.get('player_engine', 'vlc')
    proxy_cfg = config.get('proxy_config')
    std_proxy_cfg = get_standardized_proxy_config(proxy_cfg)
    
    if engine == 'mpv':
        player_adapter = MpvPlayerAdapter(
            mpv_config=config.get('mpv_config'),
            proxy_config=std_proxy_cfg
        )
        logging.info("Motor de reproducción: mpv")
    else:
        player_adapter = VlcPlayerAdapter(
            vlc_config=config.get('vlc_config'),
            proxy_config=std_proxy_cfg
        )
        logging.info("Motor de reproducción: VLC")

    m3u_repo = FileM3URepository()
    xmltv_repo = XMLTVRepository()
    logo_loader = QtLogoLoaderAdapter()
    
    # 4. Inyectar en Servicios
    playlist_loader = PlaylistLoader(m3u_repo)
    playback_manager = PlaybackManager(player_adapter)
    epg_manager = EPGManager(xmltv_repo)
    
    # Cargar EPG inicial
    epg_url = get_active_epg(config)
    if epg_url:
        epg_manager.update_epg(epg_url)
    
    # 5. Inyectar en la Interfaz (Driver Adapter)
    window = IPTVMainWindow(
        playlist_loader=playlist_loader,
        playback_manager=playback_manager,
        epg_manager=epg_manager,
        logo_loader=logo_loader,
        config=config,
        save_callback=save_config
    )
    
    window.show()
    
    # 6. Ejecución y limpieza
    exit_code = app.exec()

    # Liberar recursos
    player_adapter.release()

    # Detener proxy Tor
    from src.infrastructure.utils.proxy import TorpyProxyManager
    TorpyProxyManager.get_instance().stop()

    logging.info("Aplicación cerrada correctamente.")
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
