# Directorio de Sandbox de Pruebas

Este directorio está destinado exclusivamente a la experimentación, depuración y validación de nuevas funcionalidades antes de ser integradas en el núcleo del proyecto (`src/`).

## Reglas de Uso del Sandbox (PEP 20)

1. **Aislamiento**: Los scripts creados aquí deben ser autocontenidos y funcionales por sí solos.
2. **Ejecución**: Deben poder ejecutarse con el entorno virtual del proyecto: `.\.venv\Scripts\python.exe .\pruebas\nombre_del_script.py`.
3. **Mantenimiento**: Solo se deben subir a este directorio scripts que aporten valor en la depuración de problemas específicos encontrados en el motor de VLC o en la lógica de IPTV.
4. **Higiene**: Este directorio debe mantenerse limpio de archivos temporales o logs de gran tamaño.

---
*Referencia: Regla AG-PYTHON-SENIOR-PEP20*
