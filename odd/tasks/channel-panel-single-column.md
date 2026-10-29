# ODD Task: channel-panel-single-column

> Documento único de feature (contrato ODD de gentle-pi: `odd/tasks/<feature-name>.md`).
> Espejo de recuperación en Engram: topic `odd/channel-panel-single-column/tasks`.
>
> **Estado: IMPLEMENTADO** (2026-10-21). El mockup de diseño sigue en
> `pruebas/panel_una_columna.py` como referencia visual; el código real vive en
> `src/infrastructure/ui/components/channel_row_delegate.py`.

## Objective

Rediseñar el panel de canales: pasar de la tabla de **3 columnas** (Canal | Logo |
Programación) a **una sola columna** que integra logo, nombre y toda la información
de EPG en la misma celda, con dos variantes que conviven con los modos de vista
existentes (`NORMAL`, `COMPACT`, `VIDEO`).

## Problem

La tabla actual separa la información en tres columnas, lo que obliga a recorrer
la fila con la vista y desperdicia ancho: el logo ocupa una columna fija de 120 px
y el nombre otra con `ResizeToContents`. Con listas de cientos de canales, el
resultado es una rejilla donde cuesta asociar cada logo y cada programa con su
canal.

Además no se muestra qué viene después: el usuario solo ve el programa en curso y
su barra de progreso, así que no puede decidir si espera o cambia de canal.

## Why

Un panel de una sola columna se lee como una lista de tarjetas, de arriba abajo,
que es como se consume una parrilla de TV. Añadir «Próximamente» convierte la
lista en información útil para decidir, no solo en un selector.

## Scope

**Incluye:**
- Variante **normal** (modo `NORMAL`): una columna, logo 96×72, nombre destacado,
  programa en curso, horas + barra de progreso, duración, y bajo la barra la línea
  `→ <siguiente programa>` (flecha, no la palabra «Próximamente»).
- Variante **compacta** (modo `COMPACT`): una columna, logo 44×44, espaciados
  ajustados y **sin** la línea del siguiente programa.
- Estilo de nombre «acento» en la variante normal.
- Cálculo del siguiente programa desde `EPGManager`.

**Excluye:**
- Cambiar los modos de vista existentes (`NORMAL`/`COMPACT`/`VIDEO`) o sus atajos.
- Tocar VLC/mpv, reproducción, proxy o EPG de configuración.
- Persistencia nueva en `config.ini` (los modos ya persisten).

## Constraints

- `QLabel`/widget por celda está descartado: con miles de filas es caro. Se usa un
  `QStyledItemDelegate`, como ya hace `EPGProgramDelegate`.
- El delegado **no** consulta la EPG. Todo lo que pinta llega por roles del item.
- `ProgramInfo` debe seguir siendo un `dataclass` con valores por defecto para no
  romper las llamadas y tests existentes.
- La barra de progreso se recalcula al pintar; no debe consultar la EPG.

## Decisiones de diseño

| ID | Decisión | Rationale |
|----|----------|-----------|
| D1 | Se conservan **las dos** variantes (normal y compacta) | El usuario las aprobó explícitamente: la app ya tenía normal, compacta y solo logos |
| D2 | La línea del siguiente programa va **solo** en la variante normal | La compacta existe para meter más canales; una línea extra le quita su ventaja |
| D3 | Estilo de nombre **«acento»**: +1,5 pt y barrita celeste `#38bdf8` de 3 px a la izquierda del bloque | Destaca sin ensanchar los nombres largos (frente a «grande», +2,5 pt) y se distingue del título (frente a «actual») |
| D4 | La barrita de acento sangra **todo** el bloque de texto, no solo el nombre | Si no, las tres líneas quedan desalineadas |
| D5 | El alto de fila se **deriva** de `QFontMetrics`, no es constante | Medido: normal 90 px, compacta 66 px con Segoe UI 9 pt. Una constante se rompe al cambiar la fuente, el escalado de Windows o añadir líneas |
| D6 | «Próximamente» pasa a ser **`→ `** (flecha) | Medido: la flecha ocupa 12 px frente a 78 de «Próximamente: », 84 de «A continuación: », 55 de «Siguiente: » y 50 de «Después: ». No hay que abreviar ninguna palabra y el símbolo ya se lee como «lo que viene» |
| D7 | Sin siguiente programa, no se pinta la línea | Mejor vacío que una flecha con un guion |
| D8 | `Alt+1` → variante **normal**; `Alt+2` → variante **compacta**. Sustituyen a las vistas actuales de esos mismos atajos | Decisión del usuario: se reemplaza lo que hoy hace cada atajo, no se añaden modos nuevos |
| D9 | `Alt+3` **no se toca**: sigue siendo «solo vídeo» (tabla oculta, menú oculto) | Decisión del usuario |
| D10 | El modo compacto **ya no oculta la barra de menú**; el menú está siempre visible en ventana normal | Decisión del usuario. Solo `VIDEO` y pantalla completa ocultan el menú |
| D11 | Los anchos 340 px (normal) y 252 px (compacta) son **mínimos**, no fijos: el splitter permite ensanchar y se sigue persistiendo `splitter_state` | Decisión del usuario: aprovechar el ancho disponible para el vídeo |

### Qué desaparece

- La **tabla de 3 columnas** (Canal \| Logo \| Programación): era la vista de `Alt+1`.
- La vista de `Alt+2` que **ocultaba solo la columna del logo** y la barra de menú.

Los valores persistidos `view_mode = normal|compact|video` se mantienen, así que un
`config.ini` existente sigue siendo válido y no hace falta migración.

## Implementación pendiente (el detalle que faltaba)

### El dato

`EPGData.get_programs_for_channel()` ya devuelve los programas **ordenados por
`start_time`**. `EPGManager.get_program_schedule(tvg_id, channel_name)` expone esa
lista con el mismo *fallback* que el programa en curso (por `tvg_id`, y si no hay,
por nombre normalizado).

Falta el método:

```python
def get_next_program(self, tvg_id: str, channel_name: str = "") -> Program | None:
    now = datetime.now()
    for program in self.get_program_schedule(tvg_id, channel_name):
        if program.start_time > now:
            return program
    return None
```

### El contrato con el delegado

`_refresh_epg_row()` construye hoy:

```python
epg_item.setData(EPG_PROGRAM_ROLE, ProgramInfo(
    title=program.title, start=program.start_time, end=program.end_time))
```

Hay que añadir el campo al `ProgramInfo` real
(`src/infrastructure/ui/components/epg_program_delegate.py`), **con default** para
no romper llamadas existentes:

```python
next_title: str = ""
```

Y pintar la línea solo si viene relleno.

### El refresco

`_epg_timer` (30 s) ya llama a `_refresh_epg_display` → `_refresh_epg_row`. Basta
con que esa ruta recalcule **actual y siguiente a la vez**: al terminar un programa,
lo que era «siguiente» pasa a ser «actual», y si solo se recalculara uno, la fila
mostraría la barra del programa nuevo con el «Próximamente» del que ya está en
emisión.

### Trampas conocidas

- **Doble consulta por fila.** Llamar a `get_currently_airing()` y a
  `get_next_program()` recorre y ordena dos veces la lista del canal, por fila y cada
  30 s. Mejor pedir el *schedule* una vez y derivar ambos.
- **Duplicados.** El *fallback* por nombre normalizado hace `extend` de programas de
  varios `tvg_id` con el mismo nombre, así que la lista puede traer repetidos:
  deduplicar por `(title, start_time)`.
- **Huecos de EPG.** Puede no haber programa en curso pero sí siguiente. Hay que
  decidir si se pinta solo «Próximamente» o «Guía no disponible».
- **Fin de la guía.** Cuando no hay siguiente, dejar `next_title` vacío.
- **Modo «solo título».** `EPGProgramDelegate.set_title_only(True)` debe seguir
  ocultando horas, barra, duración y también «Próximamente».

## Checklist

| ID | Tarea | Estado |
|----|-------|--------|
| T1 | Mockup validado con datos reales (logos de iptv-org) | ✅ done |
| T2 | Estilo de nombre elegido («acento») e implementado en el mockup | ✅ done |
| T3 | Línea del siguiente programa bajo la barra, solo en la variante normal | ✅ done |
| T4 | Geometría verificada (sin solapes, sin scrollbars) | ✅ done (`--comprobar`) |
| T5 | Prefijo de la línea decidido: flecha `→ ` (sin hora de inicio) | ✅ done |
| T6 | Tests de `EPGManager.get_next_program` (actual+siguiente, hueco, lista vacía, último del día) | ✅ done (5 tests) |
| T7 | `ProgramInfo.next_title` en el delegado real, con default | ✅ done |
| T8 | `_refresh_epg_row` rellena `next_title` pidiendo el schedule una sola vez | ✅ done (`get_current_and_next`) |
| T9 | Delegado de una columna en `src/` (normal + compacta) | ✅ done (`channel_row_delegate.py`, 18 tests) |
| T9b | `_apply_layout`: `NORMAL` y `COMPACT` dejan de tocar columnas; ambos muestran la tabla de una columna. `COMPACT` deja de ocultar el menú | ✅ done |
| T9c | Anchos mínimos 340 / 252 en el splitter (`setMinimumWidth` por modo) | ✅ done (`TABLE_MIN_WIDTH`) |
| T9d | Actualizar `odd/tasks/view-modes.md` (D3, AC-1, AC-2) y los tests del layout antiguo | ✅ done |
| T10 | `_fill_table` a una columna; el `Channel` pasa a la columna 0 | ✅ done |
| T11 | `_on_item_clicked` y `_on_logo_loaded` adaptados al nuevo índice | ✅ done |
| T12 | `main_window` respeta `set_title_only` en la línea nueva | ✅ done |
| T13 | Suite completa en verde | ✅ done (265 passed) |
| T14 | Verificación manual de los tres modos + smoke de EPG | ⬜ pending (requiere abrir la app con la playlist real) |

## Acceptance Criteria and Checks

- **AC-1**: En modo `NORMAL`, cada fila muestra logo, nombre destacado, programa,
  horas, barra, duración y `→ <siguiente programa>`.
- **AC-2**: En modo `COMPACT`, cada fila muestra lo mismo **sin** la línea del
  siguiente programa, con fila más baja que la normal.
- **AC-3**: El texto del siguiente programa cambia solo, sin interacción del
  usuario, cuando un programa termina (≤ 30 s de desfase).
- **AC-4**: Sin siguiente programa en la guía, no se pinta la línea y no aparece
  texto vacío ni guiones.
- **AC-5**: El clic en cualquier punto de la fila sigue reproduciendo el canal.
- **AC-6**: Los logos que llegan de forma asíncrona actualizan su fila.
- **AC-7**: No hay solapes de filas ni scrollbars inesperados en ninguno de los
  modos, con fuente y escalado de Windows por defecto.
- **AC-8**: Sin datos de EPG para una fila, la fila pinta igualmente el logo y el
  nombre del canal, con un aviso tenue en la línea del programa. Ninguna fila
  queda en blanco: una fuente con la guía caída no puede parecer una lista sin
  canales.

## Defecto corregido (2026-10-24)

**Síntoma**: un proveedor cuya EPG falla mostraba el panel con las filas
numeradas pero completamente vacías; se leía como «no carga la lista de canales».

**Causa**: `ChannelRowDelegate.paint` solo pintaba cuando el rol
`EPG_PROGRAM_ROLE` traía un `ProgramInfo`. Sin EPG hacía
`super().paint(...)`, y el item se crea con texto vacío, así que la fila salía
en blanco con el alto del delegado (unos 84 px).

**Arreglo**: el delegado pinta siempre logo, acento y nombre; si no hay
`ProgramInfo` escribe `NO_EPG_TEXT` («Sin programación») en la línea del programa
y no dibuja barra ni siguiente programa. Tests:
`tests/test_channel_row_delegate.py::test_delegate_paints_the_channel_name_without_epg`
y su variante en «solo título».

**Verificación**: `pytest tests/` → 268 passed; `ruff` y `mypy` limpios.
Reproducido antes del arreglo con 0 píxeles de tinta en la fila sin EPG frente a
1358 con EPG.

## Verification Evidence (del mockup)

- `pruebas/panel_una_columna.py --comprobar` → `RESULTADO: todo correcto` en las
  tres tablas (90 / 66 / 90 px, delegado y fila coincidiendo, sin solapes).
- Implementación real: `pytest tests/` → **265 passed**; `ruff` y `mypy` limpios.
  El `rc=139` al terminar la suite es un segfault de cierre de Qt que ya existe en
  `HEAD` (comprobado con un worktree limpio: mismos 80 tests y mismo segfault).
- Ventana real renderizada con fakes: variante normal **84 px** de fila y compacta
  **56 px** (fuente offscreen; con Segoe UI crece porque el alto se deriva), anchos
  mínimos 340 / 252 px aplicados por `_apply_layout`.
- La línea del siguiente programa se pinta solo en la normal: +216 px de tinta con
  `next_title="El tiempo"`; en la compacta la tinta es idéntica con y sin él.
- OCR sobre el render recortado por panel (con el prefijo textual de entonces):
  «Próximamente: El tiempo», «Antena 3 Noticias 2», «La noche temática»,
  «Teledeporte Noticias» en la variante A; ninguna en la B.
- Con la flecha, el peor caso de la línea es 116 px sobre 210 disponibles en la
  variante A estrechada (antes 182 px), así que no elide con ningún título real.
- `ruff` y `mypy` limpios sobre el script del mockup.

## Referencias

- Mockup: `pruebas/panel_una_columna.py` (`--nombres`, `--con-referencia`,
  `--comprobar`, `--shot`).
- Actual: `src/infrastructure/ui/main_window.py` (`_setup_ui`, `_fill_table`,
  `_refresh_epg_row`, `_epg_timer`).
- Delegado actual: `src/infrastructure/ui/components/epg_program_delegate.py`.
- EPG: `src/application/services/epg_manager.py`, `src/domain/entities/epg.py`.
- Modos de vista: `src/application/services/view_mode_controller.py`,
  `odd/tasks/view-modes.md`.
