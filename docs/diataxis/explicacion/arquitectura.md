# Arquitectura del Sistema

> **Respuesta corta**: IPTVViewer usa Arquitectura Hexagonal con 3 capas (Dominio → Aplicación → Infraestructura), doble motor de reproducción (VLC + MPV) intercambiable en caliente, y proxy Tor integrado.

---

## Estructura de capas

```
┌──────────────────────────────────────────────┐
│  UI (Infraestructura)                         │
│  main_window.py · epg_grid.py                 │
│  engine_config_dialog.py · proxy_config_dialog│
├──────────────────────────────────────────────┤
│  Aplicación (Servicios)                       │
│  PlaybackManager · PlaylistLoader · EPGManager│
├──────────────────────────────────────────────┤
│  Dominio (Puertos + Entidades)                │
│  IPlayer · IPlaylistRepository · IEPGRepository│
│  Channel · Playlist · EPGData · Program        │
├──────────────────────────────────────────────┤
│  Infraestructura (Adaptadores)                 │
│  VlcPlayerAdapter · MpvPlayerAdapter           │
│  FileM3URepository · XMLTVRepository           │
│  TorpyProxyManager                             │
└──────────────────────────────────────────────┘
```

### Capa de Dominio (`src/domain/`)

Define **qué** hace el sistema, sin acoplarse a ninguna tecnología.

| Artefacto | Rol |
|---|---|
| `Channel` (dataclass) | Canal IPTV: nombre, URL, grupo, logo, TVG-ID |
| `Playlist` | Colección de canales con filtro por grupo |
| `Program` (dataclass) | Programa individual de EPG con horario |
| `EPGData` | Agregado de programas con búsqueda por canal y matching por nombre |
| `IPlayer` (interfaz) | Contrato del reproductor: `play()`, `stop()`, `set_output_window()`, `release()` |
| `IPlaylistRepository` (interfaz) | Contrato de carga de listas M3U |
| `IEPGRepository` (interfaz) | Contrato de carga de datos EPG/XMLTV |

### Capa de Aplicación (`src/application/`)

Coordina el flujo entre UI y dominio. **No contiene lógica de infraestructura.**

| Servicio | Responsabilidad |
|---|---|
| `PlaybackManager` | Orquestar reproducción, cambio de motor en caliente, aceleración HW |
| `PlaylistLoader` | Cargar y filtrar canales desde fuente M3U |
| `EPGManager` | Obtener y cachear datos de programación |

### Capa de Infraestructura (`src/infrastructure/`)

Implementa **cómo** se conecta el sistema al mundo exterior.

| Adaptador | Implementa | Detalle |
|---|---|---|
| `VlcPlayerAdapter` | `IPlayer` | Motor VLC con autorreconexión, proxy, HW accel |
| `MpvPlayerAdapter` | `IPlayer` | Motor MPV con libmpv-2.dll, reconexión por idle |
| `FileM3URepository` | `IPlaylistRepository` | Carga M3U desde archivo local o URL remota |
| `XMLTVRepository` | `IEPGRepository` | Descarga y parsea XMLTV (comprimido .gz/.zip/.7z) |
| `QtLogoLoaderAdapter` | — | Logos asíncronos con concurrencia acotada (4) y caché con TTL |
| `TorpyProxyManager` | — | Proxy Tor interno (torpy) con renovación de identidad |

> **Bootstrap de motores**: las DLLs no se empaquetan. `mpv_dll_bootstrap.py` y
> `vlc_bootstrap.py` las descargan en runtime (`bin/`, `bin-v3/`, `vlc/`) y
> `sevenzip.py` las extrae con `tar.exe` de Windows o 7-Zip (soportan el filtro
> BCJ2 que `py7zr` no maneja).

> **Logging de Qt**: `qt_logging.py` instala un `qInstallMessageHandler` que
> enruta los mensajes de Qt al `logging` de la app y degrada el ruido de
> red/imagen (logos/CDNs fallidos) a INFO.

---

## Ciclo de reproducción

1. Usuario selecciona canal en `IPTVMainWindow`
2. `PlaybackManager.play_channel(channel)` → `IPlayer.play(url)`
3. Adaptador concreto (VLC o MPV) inicia el stream
4. Si el stream corta → autorreconexión automática (200ms VLC, 1s MPV)
5. Si el usuario cambia de motor → `switch_player_engine()` libera el anterior e inicializa el nuevo

---

## Ciclo del proxy Tor

1. Usuario activa Tor desde `ProxyConfigDialog`
2. `TorpyProxyManager.start()` lanza hilo con circuito de 3 saltos
3. Variables de entorno (`HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY`) se configuran
4. Motores VLC y MPV heredan el proxy vía entorno o configuración directa
5. `_update_tor_info()` consulta IP externa vía `ip-api.com` y confirma la salida Tor con `check.torproject.org/api/ip` (`IsTor`)

---

## Evaluación de la arquitectura

### Lo que funciona bien

- **IPlayer** con 2 implementaciones: la abstracción está plenamente justificada. Cambiar entre VLC y MPV en caliente es una capacidad real que usa el sistema.
- Separación clara entre UI, servicios y adaptadores.

### Oportunidades de simplificación

- **IPlaylistRepository** y **IEPGRepository** tienen una sola implementación cada una. Son abstracciones especulativas (YAGNI). No hay tests que las mockeen ni segundo adaptador previsto.
- **Dominio anémico**: las entidades son dataclasses sin lógica de negocio. `Playlist` es esencialmente un wrapper de lista con un filtro.
- **Directorios vacíos**: `src/application/dtos/` y `src/infrastructure/config/` existen pero nunca se poblaron.
