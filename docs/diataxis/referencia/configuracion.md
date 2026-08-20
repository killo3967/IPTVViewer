# Referencia de `config.ini`

> Todas las claves de configuración del sistema, organizadas por sección.

---

## `[SETTINGS]` — Configuración general

| Clave | Tipo | Por defecto | Descripción |
|---|---|---|---|
| `active` | int | `0` | Índice de la fuente activa |
| `hw_acceleration` | bool | `False` | Aceleración hardware global |
| `player_engine` | `vlc` \| `mpv` | `mpv` | Motor de reproducción activo |

---

## `[source.N]` — Fuentes M3U

Cada fuente es una sección numerada (`[source.0]`, `[source.1]`, ...).

| Clave | Tipo | Por defecto | Descripción |
|---|---|---|---|
| `name` | string | `Lista N` | Nombre descriptivo de la lista |
| `m3u` | string | (vacío) | URL o ruta del archivo M3U |
| `filter` | string | (vacío) | Grupo de canales a mostrar (vacío = sin filtro) |
| `epg` | string | (vacío) | URL o ruta de la guía XMLTV para esta fuente |

Ejemplo:
```ini
[SETTINGS]
active = 0
hw_acceleration = True
player_engine = mpv

[source.0]
name = TV España
m3u = http://TU_SERVIDOR:34400/m3u/xteve.m3u
filter = SPAIN
epg = http://TU_SERVIDOR:34400/xmltv/xteve.xml

[source.1]
name = IPTV Premium
m3u = http://otro-proveedor.com/lista.m3u
filter =
epg = http://otro-proveedor.com/epg.xml
```

---

## `[VLC]` — Opciones del motor VLC

| Clave | Tipo | Por defecto | Descripción |
|---|---|---|---|
| `reset_plugins_cache` | bool | `False` | Limpiar caché de plugins al iniciar |
| `network_caching` | int (ms) | `1500` | Buffer de red. Subir si hay buffering |
| `clock_jitter` | int (ms) | `1000` | Tolerancia de jitter del reloj |
| `clock_synchro` | int | `0` | 0 = desactivar sincronización de reloj |
| `drop_late_frames` | bool | `True` | Descartar frames tardíos |
| `skip_frames` | bool | `True` | Saltar frames para mantener sincronía |
| `repeat` | bool | `True` | Repetir stream al finalizar |
| `log_verbose` | int (0-3) | `2` | Nivel de detalle del log |
| `file_logging` | bool | `True` | Guardar log a archivo |
| `logfile` | string | `logs/vlc.log` | Ruta del archivo de log |
| `hw_acceleration` | bool | `False` | Aceleración hardware (dxva2 + d3d11) |

---

## `[MPV]` — Opciones del motor MPV

| Clave | Tipo | Por defecto | Descripción |
|---|---|---|---|
| `network_caching` | int (ms) | `5000` | Buffer de red |
| `hw_acceleration` | bool | `False` | Aceleración hardware (`hwdec=auto`) |
| `cache` | bool | `True` | Activar caché de stream |
| `demuxer_readahead_secs` | float | `5.0` | Segundos de read-ahead del demuxer |
| `user_agent` | string | Chrome 122 | User-Agent para peticiones HTTP |
| `log_level` | string | `info` | Nivel de log (no, fatal, error, warn, info, debug, trace) |
| `logfile` | string | `logs/mpv.log` | Ruta del archivo de log |
| `file_logging` | bool | `True` | Guardar log a archivo |

---

## `[PROXY]` — Configuración del proxy

| Clave | Tipo | Por defecto | Descripción |
|---|---|---|---|
| `enabled` | bool | `True` | Activar proxy al iniciar |
| `type` | `tor` \| `http` \| `socks5` | `tor` | Tipo de proxy |
| `server` | string | `127.0.0.1` | Dirección del servidor proxy |
| `port` | int | `9050` | Puerto del proxy |
| `username` | string | (vacío) | Usuario (para HTTP/SOCKS5) |
| `password` | string | (vacío) | Contraseña (para HTTP/SOCKS5) |
| `bypass_local` | bool | `True` | No enrutar direcciones locales por proxy |
| `tor_control_port` | int | `9051` | Puerto de control de Tor |
| `tor_control_password` | string | (vacío) | Contraseña del puerto de control |
