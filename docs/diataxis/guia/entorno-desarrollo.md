# Entorno de Desarrollo

> **Respuesta corta**: Necesitas Python 3.11+, VLC 64-bit, y libmpv.dll en `bin/`. El resto se instala con `pip install -r requirements.txt`.

---

## Requisitos

| Componente | Obligatorio | Notas |
|---|---|---|
| Python 3.11+ | ✅ | Probado en 3.12 |
| VLC Media Player 64-bit | ✅ (motor VLC) | Instalar en ubicación por defecto |
| libmpv.dll | ✅ (motor MPV) | Colocar en `bin/` del proyecto |
| Tor (externo) | ❌ | El proyecto usa torpy (integrado) |

---

## Instalación rápida

```powershell
# 1. Clonar o copiar el proyecto
cd K:\IPTVViewer

# 2. Crear entorno virtual
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Verificar que libmpv.dll está en bin/
ls bin/libmpv-2.dll

# 5. Ejecutar
python main.py
```

---

## Configuración de motores

### VLC

- Requiere VLC instalado en el sistema (el binding `python-vlc` busca la DLL automáticamente)
- Configuración técnica en `config.ini` → sección `[VLC]`

### MPV

- Requiere `libmpv-2.dll` (o `libmpv.dll`) en el directorio `bin/`
- El adaptador carga la DLL automáticamente al inicio
- Configuración técnica en `config.ini` → sección `[MPV]`

---

## Archivos de configuración

| Archivo | Propósito |
|---|---|
| `config.ini` | Fuente M3U, EPG, motor activo, proxy, opciones técnicas |
| `requirements.txt` | Dependencias Python (39 paquetes) |
| `skills-lock.json` | Versiones bloqueadas de skills del agente |

---

## Estructura de directorios relevante

| Directorio | Contenido |
|---|---|
| `src/` | Código fuente (domain, application, infrastructure) |
| `pruebas/` | Scripts de diagnóstico y experimentos |
| `bin/` | DLLs nativas (libmpv) |
| `m3u/` | Archivos M3U locales |
| `logs/` | Salida de logs (iptv_viewer.log, vlc.log, mpv.log) |
| `docs/` | Documentación canónica y auditoría |
| `docs/diataxis/` | Documentación derivada (este conjunto) |
