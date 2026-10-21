# ODD Task: configurable-shortcuts

> Documento único de feature (contrato ODD de gentle-pi: `odd/tasks/<feature-name>.md`).
> Espejo de recuperación en Engram: topic `odd/configurable-shortcuts/tasks`.
>
> **Estado:** 📋 BACKLOG — propuesta registrada, pendiente de aceptación del usuario.

## Objective

Que el usuario pueda **definir sus propias teclas para los atajos** desde la
configuración de la aplicación (config.ini y/o diálogo de configuración), en lugar
de tener las combinaciones fijas en el código.

## Problem

Todos los atajos están cableados a mano en `_register_shortcuts()` y en
`keyPressEvent()` de `main_window.py`: Alt+1..4, P, ↑/↓, F, Esc, Ctrl+G, Ctrl+S.
Si una combinación choca con otra aplicación (o simplemente no le gusta al
usuario), no hay forma de cambiarla sin editar código.

## Why

El usuario lo pidió como próxima tarea tras verificar la feature de audio
(2026-08-24): quiere poder personalizar las teclas desde la configuración.

## Scope

**Incluye:**
- Nuevas claves en config.ini para cada atajo (o tabla de atajos).
- Diálogo de configuración con captura de tecla (grab de la combinación pulsada).
- Lectura de atajos desde config al construir la ventana.
- Detección y resolución de conflictos (dos acciones con la misma tecla).
- Teclas reenviadas del PIP deben respetar el mismo mapa.

**Excluye:**
- Múltiples perfiles de teclado.
- Atajos de ratón.
- Detección global de teclas fuera de la app.

## Constraints

- Mantener los valores actuales como **defaults** si no hay config (retrocompatibilidad).
- Los atajos de flechas con modificador (Shift+↑/↓ volumen vs ↑/↓ zap) dependen de
  la discriminación por modificador en el handler — la solución debe preservar esa
  mecánica o generalizarla (p. ej. mapa atajo→acción con posibilidad de pares
  "plano/modificado").
- `keyPressEvent` del main (ruta PIP) y `_register_shortcuts` deben salir del MISMO
  mapa; hoy son dos listas paralelas que hay que mantener a mano.
- Nota del gotcha Qt: un atajo plano captura también sus variantes con modificador;
  la configuración por el usuario puede introducir nuevos casos de ambigüedad →
  validación en el diálogo.

## Decisiones de diseño

_(por decidir con el usuario en la fase deciding; candidatas:_

| Opción | Descripción |
|--------|-------------|
| A | Solo config.ini: el usuario edita las teclas a mano en el fichero |
| B | Diálogo gráfico con captura de tecla + guardado en config.ini |
| C | Híbrido: config.ini como fuente, diálogo opcional como editor cómodo |

_)_

## Checklist

| ID | Tarea | Estado |
|----|-------|--------|
| T1 | Diseñar el formato de configuración (claves/valores por atajo) | ⬜ pending |
| T2 | Tabla central atajo→acción (única fuente para shortcuts + keyPressEvent + PIP) | ⬜ pending |
| T3 | Lectura de config + defaults retrocompatibles | ⬜ pending |
| T4 | Diálogo de captura de teclas (si se elige opción B/C) | ⬜ pending |
| T5 | Validación de conflictos/ambigüedades | ⬜ pending |
| T6 | Tests de round-trip config + resolución de atajos + conflictos | ⬜ pending |
| T7 | Verificación manual en todos los modos + PIP | ⬜ pending |

## Acceptance Criteria and Checks

- **AC-1**: Sin claves de atajos en config, el comportamiento es idéntico al actual.
- **AC-2**: Cambiar una tecla en config cambia el atajo activo tras reabrir la app.
- **AC-3**: Todos los atajos configurables funcionan también con foco en el PIP.
- **AC-4**: Dos acciones no pueden quedar mapeadas a la misma tecla (error/aviso claro).
- **AC-5**: Suite completa en verde.

## Verification Evidence

_(pendiente)_

## Next Step

Decidir con el usuario la opción de diseño (A/B/C) y el alcance exacto de teclas
configurables (¿todas o solo algunas?), y luego abrir la fase TDD.
