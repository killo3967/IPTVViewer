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
| DT-05 | ✅ Resuelto (2026-08): 36 tests en verde en `tests/` | — | — |
| DT-06 | `except Exception` amplio en 16 ubicaciones (los `except:` desnudos ya se eliminaron) | Oculta errores inesperados | Capturar excepciones específicas |
| DT-07 | Sin type hints estrictos (mypy) | Errores de tipo en runtime | Configurar mypy en modo strict |
| DT-08 | `src/application/dtos/` y `src/infrastructure/config/` vacíos | Confusión estructural | Poblar o eliminar |

---

## Bugs reportados (2026-08)

| ID | Problema | Severidad | Propuesta |
|---|---|---|---|
| BUG-01 | Proxy Tor falla con `Missing dependencies for socks` | Alta | Revisar dependencias de torpy/PySocks en el empaquetado |
| BUG-02 | Cambiar la configuración de EPG no refresca la lista (hay que reiniciar) | Media | Añadir botón "Refrescar lista" |
| BUG-03 | Tecla `F` no alterna pantalla completa | Alta | Toggle fullscreen que restaure el estado anterior |
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
| Tests unitarios | 8 archivos, 36 tests en verde (pytest) |
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
- [ ] Configurar mypy strict (DT-07)

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
