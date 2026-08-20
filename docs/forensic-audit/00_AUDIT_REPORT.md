# Auditoría Forense — IPTVViewer

**Fecha**: 2026-07-04
**Modo**: Forensic (completo)
**Herramienta**: codebase-memory-mcp v0.8.1
**Proyecto indexado**: K-IPTVViewer (1304 nodos, 1983 aristas)

---

## 1. Propósito y Stack

Aplicación de escritorio para reproducción de canales IPTV con GUI en PyQt6.
Arquitectura Hexagonal (Puertos y Adaptadores), Python 3.11+, Windows 11.

| Componente | Tecnología |
|---|---|
| Lenguaje | Python |
| GUI | PyQt6 6.8.1 |
| Motores de reproducción | VLC (python-vlc), MPV (libmpv.dll) |
| Proxy | Tor (torpy 1.1.6) |
| EPG | XMLTV (parseo manual) |
| Configuración | INI (configparser) |
| Testing | pytest (configurado, apenas usado en src) |

---

## 2. Estructura del Código

```
src/
├── domain/
│   ├── entities/    channel.py (17L), epg.py (86L), playlist.py (26L)
│   └── ports/       i_player.py (34L), i_playlist_repo.py (11L), i_epg_repo.py (10L)
├── application/
│   └── services/    playback_manager.py (47L), playlist_loader.py (14L), epg_manager.py (54L)
├── infrastructure/
│   ├── adapters/    vlc_player_adapter.py (215L), mpv_player_adapter.py (204L),
│   │                file_m3u_repository.py (81L), xmltv_repository.py (105L),
│   │                qt_logo_loader_adapter.py (71L)
│   ├── ui/          main_window.py (428L)
│   │   └── components/  engine_config_dialog.py (200L), epg_grid.py (75L),
│   │                    proxy_config_dialog.py (339L)
│   └── utils/       proxy.py (288L)
main.py (212L)
pruebas/ (8 scripts, 1236L)
```

**Total**: ~3753 líneas de Python (src + main + pruebas)

---

## 3. Hallazgos por Categoría

### 3.1 Arquitectura

| Hallazgo | Detalle |
|---|---|
| **Hexagonal aplicada** | 3 puertos (IPlayer, IPlaylistRepository, IEPGRepository), 4 adaptadores |
| **IPlayer justificado** | 2 implementaciones reales (VLC + MPV), polimorfismo en caliente con switch_player_engine() |
| **Puertos especulativos** | IPlaylistRepository (1 impl), IEPGRepository (1 impl). Sin tests que los mockeen. YAGNI |
| **Directorios vacíos** | `src/application/dtos/` (creado pero sin DTOs), `src/infrastructure/config/` (sin uso) |
| **Domain anémico** | Entidades son dataclasses sin lógica de negocio real. Playlist es un wrapper de lista |

### 3.2 Deuda Técnica y Código

| Hallazgo | Severidad | Detalle |
|---|---|---|
| **Bare except: (9 instancias)** | Media | Todos tienen logging, pero capturan excepciones genéricas. En proxy.py y adapters |
| **Sin tests unitarios en src/** | Alta | pytest configurado pero 0 tests en src/. Solo scripts exploratorios en pruebas/ |
| **Sin type hints estrictos** | Baja | mypy no configurado, sin py.typed |
| **Sin CI/CD** | Baja | Sin GitHub Actions, sin pre-commit hooks |
| **Autorreconexión sin backoff** | Media | Reconexión a 200ms/500ms fijos, sin backoff exponencial (documentado en DT-02) |
| **Sin caché de logos en disco** | Baja | Solo QPixmapCache en memoria (documentado en DT-01) |

### 3.3 Documentación vs Código Real

| Documento | Deriva | Detalle |
|---|---|---|
| `01_ARCHITECTURE.md` | **Sí** | Menciona `vlc_config_dialog.py` → archivo real es `engine_config_dialog.py` (soporta VLC+MPV) |
| `01_ARCHITECTURE.md` | **Sí** | No menciona MPV como motor alternativo, solo VLC |
| `01_ARCHITECTURE.md` | **Sí** | No incluye `proxy_config_dialog.py` en el diagrama |
| `02_ENVIRONMENT_&_BUILD.md` | **Sí** | Solo menciona VLC como dependencia, omite MPV y libmpv.dll |
| `02_ENVIRONMENT_&_BUILD.md` | **Sí** | No documenta la sección [MPV] ni [PROXY] de config.ini |
| `03_OPERATIONS_&_MAINTENANCE.md` | Parcial | Menciona logs de MPV pero el troubleshooting solo cubre VLC |
| `04_DEBT_&_ROADMAP.md` | **Sí** | Fase 1 marcada como completa pero faltan tareas listadas (ej. grabación, favoritos) |
| `04_DEBT_&_ROADMAP.md` | OK | DT-01 a DT-04 reflejan problemas reales aún vigentes |

### 3.4 Hotspots (mayor fan-in)

| Componente | Fan-in | Rol |
|---|---|---|
| `TorpyProxyManager.start()` | 13 | Inicio del proxy Tor |
| `TorpyProxyManager.stop()` | 8 | Parada del proxy |
| `IPlayer.stop()` (interfaz) | 6 | Parada del reproductor |
| `IPlayer.play()` (interfaz) | 4 | Reproducción |
| `setup_proxy()` | 4 | Configuración de proxy |

---

## 4. Validación Ejecutada

| Verificación | Resultado |
|---|---|
| `codebase-memory-mcp index` | 84 archivos, 1304 nodos, 1983 aristas |
| `get_architecture` | Estructura confirmada, 32 archivos Python |
| `search_code TODO/FIXME` | 0 resultados |
| `search_code NotImplementedError` | 0 en código fuente |
| `search_code "pass$"` | 26 resultados (10 en interfaces ABC, resto en bloques except) |
| `search_code "except:"` | 9 instancias (con logging) |
| Directorios vacíos | 2 encontrados (dtos/, config/) |
| Git log | 20 commits, último: feat Tor Proxy |

---

## 5. Brechas de Documentación

1. **MPV no documentado** en arquitectura ni guía de entorno
2. **Proxy/Tor no reflejado** en el diagrama de arquitectura
3. **EngineConfigDialog** referenciado con nombre antiguo (vlc_config_dialog)
4. **Sin guía de troubleshooting para MPV**
5. **`config.ini`**: secciones [MPV] y [PROXY] no documentadas en la guía de entorno
6. **Sin documentación de la API interna** (puertos, servicios)
7. **`pruebas/` documentado en README pero no en los docs principales**

---

## 6. Recomendación

Se recomienda handoff a `diataxis-v2` para:
- Crear documentación Diataxis bajo `docs/diataxis/`
- Corregir derivas entre docs y código
- Añadir secciones faltantes (MPV, Proxy, Troubleshooting MPV)
- Clasificar contenido existente por tipo Diataxis
