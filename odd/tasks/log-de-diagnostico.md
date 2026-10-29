# ODD Task: log de diagnóstico

## Objective

Que `logs/iptv_viewer.log` cuente por sí solo qué pasó en cada carga de lista y en
cada cambio de canal: si se llegó al servidor, qué respondió, cuántos canales
llegaron, cuántos quedaron en pantalla y si la orden de reproducción salió hacia
el motor. Hoy el usuario está a ciegas cuando una lista no trae canales.

## Problem

El log solo escribía «Cambiando a lista: X» y «Reproduciendo: <canal>». No había
ni una línea sobre la descarga (HTTP, tamaño, tiempo), ni el número de canales, ni
la URL del stream. Con VPN activa y una lista por internet no se podía
distinguir «no llego al servidor» de «llego y la lista viene vacía» de «la lista
está bien y falla el motor».

## Scope

- Descarga de la lista (`FileM3URepository`): resultado HTTP, bytes y duración, tanto
  en éxito como en error; también para fichero local.
- Parseo y filtro (`FileM3URepository.get_channels`, `PlaylistLoader`): canales
  parseados y canales tras el filtro de grupo.
- Carga en ventana (`IPTVViewerMainWindow._load_data`): lista activa con su URL,
  canales puestos en pantalla y duración; caso 0 canales con aviso explícito.
- Reproducción (`PlaybackManager` y adaptadores): orden enviada al motor, fallo del
  motor y motivo, y detención; los adaptadores registran la URL cargada.
- Privacidad: toda URL que va al log pasa por `safe_url`, que quita credenciales y
  query y deja host, puerto y los dos últimos segmentos de la ruta.

## Constraints

- Nada de dependencias nuevas ni cambios de comportamiento: solo trazas `INFO`
  (y `ERROR` donde ya había error).
- La capa de aplicación no importa infraestructura: `safe_url` vive en
  `src/infrastructure/utils/` y solo lo usan adaptadores y UI.
- No se registran contraseñas, tokens ni query strings.

## Acceptance Criteria and Checks

- **AC-1**: Al activar una lista, el log muestra nombre, URL saneada, línea `M3U:
  GET ... -> HTTP <código>, <bytes> B en <s> s`, canales parseados y canales en
  pantalla con la duración total.
- **AC-2**: Si la descarga falla, queda un `ERROR` con la URL saneada, la duración y
  el motivo, seguido de `M3U: 0 canales parseados` y `Lista '<nombre>': 0 canales`.
- **AC-3**: Ninguna línea del log contiene usuario, contraseña, token ni query.
- **AC-4**: Al reproducir, el log muestra `Playback: arrancando '<canal>' con
  <motor>`, `Playback: orden enviada a <motor>` y, en los adaptadores,
  `MPV: cargando <url saneada>` / `VLC: cargando <url saneada>`.
- **AC-5**: Si el motor lanza al arrancar, el `ERROR` nombra canal y motor y la
  excepción sigue propagándose.
- **AC-6**: Con una URL de front-end (`/stream/<hash>`) el log añade
  `Stream: <origen> → <destino>`, donde el destino es el `Location` del 302
  **completo** (host, usuario, contraseña, ruta, token y query), que es lo que se
  pega en VLC o `ffprobe` para comprobar el canal. Con una URL directa del
  proveedor no se hace ninguna petición extra.
- **AC-7**: El origen se apunta saneado (es la URL del front-end, sin secretos) y
  las URLs de lista siguen saneadas. El destino del stream va entero por decisión
  explícita del usuario: `logs/` está en `.gitignore` y el fichero no se publica.
- **AC-8**: La sonda no sigue más de un salto: la segunda dirección ya es del panel
  del proveedor y abrirla gastaría una de sus conexiones mientras el motor
  reproduce. Un 200 del front-end se anota como `sin redirección (HTTP 200)` y un
  fallo como `sin datos (<motivo corto>)`.

## Verification Evidence

- Sesión real del 2026-10-24 20:23 con `PANEL REMOTO` y VPN activa:
  ```
  Lista activa: 'PANEL REMOTO' desde http://panel.example.test:34400/m3u/xteve.m3u
  M3U: GET http://panel.example.test:34400/m3u/xteve.m3u -> HTTP 200, 22148 B en 0.45 s
  M3U: 80 canales parseados de http://panel.example.test:34400/m3u/xteve.m3u (161 líneas)
  Lista: 80 canales en la descarga, sin filtro
  Lista 'PANEL REMOTO': 80 canales en pantalla en 0.45 s
  ```
- `pytest tests/` → 282 passed; `ruff` y `mypy` limpios.
- Tests nuevos: `tests/test_log_safe.py` (6), `test_playlist_loader.py` (+2),
  `test_playback_manager.py` (+4), `test_file_m3u_repository.py` (+2, uno comprueba
  que el token no aparece en el log).

- Sonda del salto contra el xteve real (2026-10-24), función que usa la app, ya
  con la URL completa:
  ```
  Stream: http://panel.example.test:34400/stream/0123456789abcdef0123456789abcdef → http://proveedor.example.test:25461/usuario/clave/3797?h=0123456789abcdef&z=&i=132511
  ```
- `pytest tests/` → 292 passed; `ruff` y `mypy` limpios. Tests nuevos:
  `tests/test_stream_probe.py` (7) y dos en `test_main_window.py` (se resuelve con
  `/stream/`, no se sondea una URL directa).

## Referencias

- `src/infrastructure/utils/log_safe.py`
- `src/infrastructure/adapters/file_m3u_repository.py`
- `src/application/services/playlist_loader.py`, `playback_manager.py`
- `src/infrastructure/adapters/mpv_player_adapter.py`, `vlc_player_adapter.py`
- `src/infrastructure/ui/main_window.py` (`_load_data`, `_on_item_clicked`)
