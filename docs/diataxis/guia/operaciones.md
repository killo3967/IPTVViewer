# Operaciones y Troubleshooting

> **Respuesta corta**: Los problemas más comunes (pantalla negra, buffering, tirones) se resuelven ajustando el caché de red o la aceleración hardware desde el panel de configuración del motor.

---

## Logs

El sistema produce tres archivos de log independientes:

| Archivo | Motor | Nivel por defecto |
|---|---|---|
| `logs/iptv_viewer.log` | Aplicación general | INFO |
| `logs/vlc.log` | Motor VLC | 2 (errors+warnings) |
| `logs/mpv.log` | Motor MPV | info |

El nivel de detalle de VLC y MPV es configurable desde **Configuración → Motor de reproducción**.

---

## Problemas comunes

### Pantalla negra o buffering constante

| Motor | Solución |
|---|---|
| VLC | Subir `network_caching` a 10000ms en Configuración → VLC |
| MPV | Subir `network_caching` y `demuxer_readahead_secs` a 10.0 en Configuración → MPV |

### Tirones / Desincronización audio-vídeo

| Motor | Solución |
|---|---|
| VLC | Desactivar aceleración HW. Poner `clock_synchro = 0`. Activar `drop_late_frames` y `skip_frames` |
| MPV | Desactivar aceleración HW. `video_sync = audio`. Reducir `vd_lavc_threads` a 1 |

### El stream se corta y no vuelve

Ambos motores tienen autorreconexión automática:
- **VLC**: reconecta en 200ms (EOF) o 500ms (error)
- **MPV**: reconecta en 1s al detectar inactividad

Si el problema persiste, prueba a cambiar de motor (Configuración → Motor activo).

### Tor no arranca o va lento

1. El primer inicio de Tor tarda hasta 60s (negociación de circuito)
2. Verifica que el puerto 9050 está libre
3. Usa el botón **Probar conexión** en Configuración → Proxy para verificar

### Error al cargar libmpv.dll

- Confirma que `bin/libmpv-2.dll` existe
- Si usas otra versión de mpv, renómbrala a `libmpv-2.dll`
- Alternativa: instala mpv desde [mpv.io](https://mpv.io/installation/) y copia la DLL

---

## Flujo de datos

### Carga de EPG

1. `EPGManager.update_epg(url)` → `XMLTVRepository.load_epg(url)`
2. Descarga XML comprimido (.gz) → parseo → entidades `Program`
3. Indexado por `channel_id` y nombre normalizado
4. La UI consulta `get_current_program(channel_id)` para cada canal

### Reproducción con proxy Tor

1. `TorpyProxyManager` inicia circuito de 3 saltos
2. Configura `HTTP_PROXY`/`HTTPS_PROXY`/`ALL_PROXY` en el entorno
3. VLC recibe opciones `--socks` o `--http-proxy` directamente
4. MPV hereda variables de entorno (FFmpeg las detecta)

---

## Scripts de diagnóstico (`pruebas/`)

| Script | Usar cuando... |
|---|---|
| `channel_test.py` | Verificar qué canales responden |
| `test_mpv.py` | Validar que MPV carga correctamente |
| `vlc_check.py` | Confirmar bindings de VLC |
| `check_vlc_log.py` | Revisar salida de log de VLC |
| `vlc_log_test.py` | Probar configuración de log de VLC |
| `test_mpv_log_fix.py` | Diagnosticar logging de MPV |
