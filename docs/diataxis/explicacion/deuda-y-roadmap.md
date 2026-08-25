# Deuda Técnica y Hoja de Ruta

> **Respuesta corta**: El proyecto está funcional, con tests en verde y empaquetado `.exe` standalone. Queda deuda técnica conocida (backoff, caché de logos, i18n).

---

## Deuda técnica activa

| ID | Problema | Impacto | Recomendación |
|---|---|---|---|
| DT-01 | Logos sin caché en disco (solo QPixmapCache en RAM) | Recarga innecesaria en cada sesión | Implementar QNetworkDiskCache |
| DT-02 | Reconexión sin backoff exponencial (200ms/1s fijos) | Puede saturar el servidor en fallos persistentes | Backoff: 200ms → 1s → 5s tras 3 fallos |
| DT-03 | Sin i18n (solo castellano) | Barrera para usuarios no hispanohablantes | Preparar `.ts` con `tr()` de PyQt6 |
| DT-04 | Bootstrap de Tor lento (~60s) | Mala UX en primer uso | Barra de progreso o indicador visual |
| DT-05 | ✅ Resuelto (2026-08): 150 tests en verde en `tests/` | — | — |
| DT-06 | `except Exception` amplio en 16 ubicaciones (los `except:` desnudos ya se eliminaron) | Oculta errores inesperados | Capturar excepciones específicas |
| DT-07 | ✅ Parcialmente resuelto (2026-08): mypy y ruff configurados y en verde (`pyproject.toml`); modo strict pendiente | Errores de tipo residuales | Migrar a `strict = true` |
| DT-08 | `src/application/dtos/` y `src/infrastructure/config/` vacíos | Confusión estructural | Poblar o eliminar |
| DT-09 | mpv no sale por Tor: FFmpeg no soporta SOCKS y torpy solo expone SOCKS5 (sin proxy HTTP) | El vídeo por mpv va directo sin Tor | Puente HTTP→SOCKS local (mini-proxy en `127.0.0.1:8118` → SOCKS5 `9050`) o integrar Privoxy |
| DT-10 | Overlay OSD del canal no se pinta sobre el video embebido: VLC/mpv dibujan directamente en el HWND del `video_widget` y tapan a los widgets Qt hijos; solo aparece al interrumpir el render (zap). Probado sin éxito: `QTimer.singleShot(0)` y `WA_NativeWindow` + `WA_TranslucentBackground`. | El OSD de 2 s (modo Video y fullscreen) no se ve al entrar al modo | Implementar el overlay como ventana top-level flotante (QLabel sin parent con `Tool | FramelessWindowHint | WindowStaysOnTopHint` + `WA_TranslucentBackground`), posicionado sobre el `video_widget` vía `mapToGlobal` y reposicionado en `resizeEvent` |

---

## Bugs reportados (2026-08)

| ID | Problema | Severidad | Propuesta |
|---|---|---|---|
| BUG-01 | ✅ Resuelto (2026-08): añadido `PySocks>=1.7.1` a `requirements.txt` y el módulo `socks` a `hiddenimports` del spec PyInstaller | — | — |
| BUG-02 | Cambiar la configuración de EPG no refresca la lista (hay que reiniciar) | Media | Añadir botón "Refrescar lista" |
| BUG-03 | ✅ Resuelto (2026-08): tecla `F` alterna pantalla completa forzando el modo Video (`F` = ALT+3 + fullscreen); `Esc` sale | — | — |
| BUG-04 | Recuadros de nombre de canal y parrilla son editables | Baja | Marcar como solo lectura |

---

## Lo que ya funciona (Fase 1 ✅)

| Funcionalidad | Estado |
|---|---|
| Arquitectura Hexagonal | Implementada |
| Doble motor VLC + MPV | Operativo, intercambiable en caliente |
| Configuración técnica de ambos motores | Panel unificado (`engine_config_dialog.py`) |
| Persistencia en `config.ini` | Completa (SETTINGS, VLC, MPV, PROXY) |
| Autorreconexión ante cortes | Activa en ambos motores |
| Proxy Tor interno (torpy) | Funcional, con monitoreo y renovación de identidad |
| Carga de M3U remoto/local | Funcional |
| EPG con XMLTV | Funcional, con matching por nombre normalizado |
| Tests unitarios | 16 archivos, 150 tests en verde (pytest) |
| Calidad de código | Ruff (linter) + Mypy (tipado) en verde, configurados en `pyproject.toml` |
| Empaquetado PyInstaller | `.exe` standalone onefile (183 MB) vía `build.bat`/`release.bat` |

---

## Tareas pendientes propuestas

### Corto plazo (correcciones)

- [ ] Añadir backoff exponencial a la reconexión (DT-02)
- [ ] Acotar `except Exception` a excepciones específicas (DT-06)
- [ ] Poblar o eliminar directorios vacíos `dtos/` y `config/` (DT-08)

### Medio plazo (mejoras)

- [ ] Caché de logos en disco (DT-01)
- [ ] Grabar streams de vídeo
- [ ] Grupos de favoritos personalizables
- [ ] Múltiples fuentes EPG simultáneas
- [ ] Barra de progreso para bootstrap de Tor (DT-04)
- [ ] Migrar mypy a modo strict (DT-07)
- [ ] Puente HTTP→SOCKS local para que mpv salga por Tor (DT-09): mini-proxy HTTP en `127.0.0.1:8118` que traduzca a SOCKS5 (`127.0.0.1:9050`) vía `create_stream` de torpy; alternativa: integrar Privoxy (como hace Tor Control Panel)

### Largo plazo (evolución)

- [ ] Internacionalización i18n (DT-03)
- [ ] CI/CD con GitHub Actions
- [ ] Soporte para subtítulos

---

## Funcionalidades solicitadas

- [ ] Búsqueda en parrilla: campo de texto + resaltado de resultados
- [ ] Coloreado de parrilla por categoría (películas, series, noticias, deportes)
- [ ] Crear lista importando datos de un m3u/m3u8
- [ ] Exportación / backup de listas y configuración
- [ ] Recordar último canal abierto y reabrir por él al iniciar
- [ ] Modos de visualización: Verbose (ALT-1), Medio (ALT-2), Compacto (ALT-3), con nombres configurables
