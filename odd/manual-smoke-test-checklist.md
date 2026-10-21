# Prueba manual final — Smoke test motor real

> Checklist punto a punto para la verificación manual que pytest no puede cubrir.
> Cubre **dos features pendientes** a la vez:
> - `odd/tasks/view-modes.md` → T16 (REQ-11)
> - `odd/tasks/pip-hides-main-window.md` → T7
>
> **Cómo usarla:** ejecuta TODO el checklist con un motor (VLC), anota el resultado
> de cada punto, y luego repítelo con el otro motor (mpv). Marca ✅/❌/⚠️ en cada
> casilla. Si algo falla, anota el número del punto y qué pasó exactamente.
>
> **Motor probado:** VLC ______ Fecha: ______ / mpv ______ Fecha: ______
>
> Antes de empezar: reproduce un canal real y déjalo sonando. Ten a mano el teclado
> nada más (la prueba es de atajos). Marca el motor al final de cada bloque.

---

## Bloque 1 — Arranque y modos de vista (Alt+1/2/3)

- [ ] **1.1** La app arranca en modo Normal: tabla con 3 columnas, video a la derecha, menú visible.
- [ ] **1.2** `Alt+2` → modo Compact: solo tabla (sin columnas Logo/Programación) y video; el menú desaparece.
- [ ] **1.3** `Alt+3` → modo Video: solo el video, sin tabla y sin menú.
- [ ] **1.4** `Alt+1` → vuelve al Normal: tabla completa y menú restaurados.
- [ ] **1.5** Pulsar `Alt+2` dos veces seguidas sin salir de Compact: no pasa nada raro (no hay "parpadeo" ni reset del layout).
- [ ] **1.6** En cada cambio de modo, **el video NO se congela ni se pone negro** (sigue reproduciéndose).

## Bloque 2 — Fullscreen y cursor

- [ ] **2.1** `F` → fullscreen completo (sin barra de título ni menú).
- [ ] **2.2** Espera 3 segundos sin mover el ratón → el cursor desaparece.
- [ ] **2.3** Mueve el ratón → el cursor reaparece.
- [ ] **2.4** `Esc` en fullscreen → sale al modo anterior.
- [ ] **2.5** `Esc` cuando NO estás en fullscreen → no pasa nada (no cierra la app, no rompe nada).
- [ ] **2.6** Cierra la app con `F` activo → cierra limpio, sin cursor "fantasma" al volver al escritorio.
- [ ] **2.7** Fullscreen + PIP abierto a la vez: la ventanita se ve por encima de todo.

## Bloque 3 — Zapping (↑/↓)

- [ ] **3.1** `↓` → pasa al canal siguiente (y suena/ve el siguiente).
- [ ] **3.2** `↑` → vuelve al canal anterior.
- [ ] **3.3** Sitúate en el **último** canal y pulsa `↓` → da la vuelta al primero (wrap-around).
- [ ] **3.4** Sitúate en el **primer** canal y pulsa `↑` → va al último (wrap-around).
- [ ] **3.5** Haz 3.3 y 3.4 en modo Video (sin tabla visible) → el zapping sigue funcionando.
- [ ] **3.6** Pulsar `↑/↓` con foco en la ventanita PIP → también zapea.

## Bloque 4 — PIP: abrir, mover, redimensionar, cerrar

- [ ] **4.1** `P` (o `Alt+4`) → aparece la ventanita PIP flotante con el video **y la ventana grande desaparece** (ni barra de tareas ni escritorio).
- [ ] **4.2** Mientras el PIP está abierto, el video sigue sonando sin cortes.
- [ ] **4.3** Arrastra la ventanita por el cuerpo → se mueve donde la dejes.
- [ ] **4.4** Redimensiona desde el grip de la esquina inferior-derecha → cambia de tamaño sin deformar el video.
- [ ] **4.5** `Alt+F4` sobre la ventanita → el PIP se cierra **y la ventana grande reaparece** (¡crítico! es el caso de la app "zombi").
- [ ] **4.6** Vuelve a abrir el PIP → recupera la posición y el tamaño que le diste antes (persistencia de geometría).
- [ ] **4.7** Cierra el PIP con `P` → la ventana grande reaparece igualmente.
- [ ] **4.8** Tras cerrar, el video vuelve a la ventana grande **y sigue reproduciéndose** (no congelado, no negro).
- [ ] **4.9** Mueve el PIP a la esquina de la pantalla y redimensiónalo pequeño → todo se ve bien dentro de sus límites.
- [ ] **4.10** Con PIP abierto, abre cualquier diálogo de la app (si queda alguno accesible, p. ej. EPG) → la ventanita sigue por encima.

## Bloque 5 — Atajos con foco en la ventanita PIP

Con el PIP abierto y el foco en él (acabas de arrastrarlo), verifica:

- [ ] **5.1** `P` o `Alt+4` → cierra el PIP (no se abre otro ni hay doble disparo).
- [ ] **5.2** `↑/↓` → zapea canales.
- [ ] **5.3** `Alt+1/2/3` → cambian el modo de la ventana grande (esta reaparecerá en ese modo).
- [ ] **5.4** `F` → la ventana grande pasa a fullscreen (el PIP sigue encima).
- [ ] **5.5** `Ctrl+G` → se abre la guía EPG.
- [ ] **5.6** Ninguna tecla hace la acción **dos veces** (p. ej. zapear 2 canales de golpe).

## Bloque 6 — Atajos de menú en modos Compact/Video

- [ ] **6.1** En Compact: `Ctrl+G` → abre la EPG.
- [ ] **6.2** En Video: `Ctrl+G` → abre la EPG (¡el menú está oculto pero el atajo vivo!).
- [ ] **6.3** En Video: comprueba que los atajos `Alt+1..4` llegan bien (no se los "traga" el menú nativo de Windows): prueba `Alt+1` desde Video.
- [ ] **6.4** Vuelve a Normal tras estar en Video → el layout es el que dejaste (tamaños de columnas conservados).

## Bloque 7 — Persistencia entre sesiones

- [ ] **7.1** Cambia a Compact, ajusta la tabla (mueve el separador), cierra la app → reabre → arranca en Compact con el separador como lo dejaste.
- [ ] **7.2** Cierra la app con PIP abierto → reabre → el PIP **NO** se abre solo (nunca auto-abre al arrancar).
- [ ] **7.3** Cierra en fullscreen → reabre → arranca en modo ventana (fullscreen no persiste).

## Bloque 8 — Robustez (si te apetece ir más allá)

- [ ] **8.1** Cambia la geometría del PIP a algo ridículo (muy pequeño) → al reabrir respeta el mínimo razonable.
- [ ] **8.2** En modo Video, cierra el PIP → el área principal queda vacía (sin tabla) pero la app sigue viva y el video vuelve al hueco.
- [ ] **8.3** Zapea rápido varias veces seguidas (spam de `↓`) → no se cuelga, no se lanza nada raro.

## Bloque 9 — Audio (Ctrl+S mute, Shift+↑/↓ volumen)

- [ ] **9.1** `Ctrl+S` → el sonido se corta; pulsar de nuevo → vuelve (mute toggle).
- [ ] **9.2** `Shift+↑` / `Shift+↓` → el volumen sube/baja de forma apreciable (pasos de 5).
- [ ] **9.3** `Shift+↓` hasta el fondo → silencio total; `↑/↓` planos siguen zapeando canales (el volumen no interfiere con el zapping).
- [ ] **9.4** Con el foco en la ventanita PIP: `Ctrl+S` y `Shift+↑/↓` hacen lo mismo que en la ventana grande.
- [ ] **9.5** Si cambias de motor (VLC ↔ mpv) desde la config, el estado de audio se mantiene (lo que oyes no cambia de golpe).

---

## Bloque 10 — Columna Programación (EPG)

- [ ] **10.1** Con la lista de weteve, la columna Programación no muestra el prefijo `NOW:`.
- [ ] **10.2** Por defecto (*Configuración → Configuración de EPG*, casilla marcada) cada fila muestra solo el título del programa.
- [ ] **10.3** Al desmarcar la casilla: título arriba, hora de inicio + barra azul-celeste + hora de fin, y la duración debajo (`30 min`, `1 h 30 min`, `2 h`).
- [ ] **10.4** La barra está rellena según el tiempo transcurrido y avanza sola cada ~30 s.
- [ ] **10.5** Al hacer scroll, las filas que entran en pantalla muestran la barra con su porcentaje (no se quedan a 0 %).
- [ ] **10.6** Un canal sin EPG muestra `Guía no disponible`.
- [ ] **10.7** El ajuste persiste al cerrar y reabrir la app (`epg_show_title_only` en `config.ini`).

---

## Registro de resultados

| Motor | Bloques fallidos | Notas |
|-------|------------------|-------|
| VLC   |                  |       |
| mpv   |                  |       |

**Resultado global:** ☐ TODO OK — ambas features verificadas · ☐ Fallos encontrados (anotar en la tabla y reportarlos)

> Al terminar: actualizar T7 de `odd/tasks/pip-hides-main-window.md` y T16 de
> `odd/tasks/view-modes.md` con la fecha y el resultado, y mover los puntos ❌ a
> bugs/nueva feature ODD si procede.
