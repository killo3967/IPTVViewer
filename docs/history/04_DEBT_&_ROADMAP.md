# Deuda Técnica y Hoja de Ruta (IPTV Viewer)

Este documento detalla las limitaciones conocidas, las decisiones de diseño críticas y las mejoras planificadas para **IPTV Viewer**.

## Deuda Técnica Identificada

### DT-01: Gestión de Logos de Canales
*   **Problema**: Actualmente se cargan los logos de forma asíncrona mediante el `QtLogoLoaderAdapter`, pero no hay un almacenamiento persistente de caché. 
*   **Causa**: Simplificación en la primera fase de implementación.
*   **Decisión**: Usar caché en memoria (`QPixmapCache`). En el futuro, implementar una base de datos local o disco (`QNetworkDiskCache`).

### DT-02: Sistema de Autorreconexión
*   **Problema**: La reconexión es de **200ms**. En errores de red persistentes, esto podría generar un bucle de peticiones infinito.
*   **Causa**: Solicitud urgente del usuario de una reconexión instantánea.
*   **Decisión**: Implementar un **backoff exponencial** (200ms, 1s, 5s) si el fallo persiste más de 3 veces.

### DT-03: Internacionalización (i18n)
*   **Problema**: El proyecto es monolingüe (Castellano). 
*   **Decisión**: Preparar archivos `.ts` y usar `tr()` de PyQt6 en el futuro para soportar múltiples idiomas.

### DT-04: Tiempos de Bootstraping de Tor
*   **Problema**: El inicio de Tor puede tardar hasta 60 segundos, lo que retrasa el primer test de conexión.
*   **Decisión**: Se ha implementado un sistema de espera inteligente y ping de puerto, pero la experiencia de usuario podría mejorar con una barra de progreso.

## Hoja de Ruta (Roadmap)

### Fase 1: Estabilización (Actual) ✅
*   [x] Implementación de **Arquitectura Hexagonal**.
*   [x] Panel de **Configuración Técnica de VLC**.
*   [x] Persistencia de configuraciones en `.ini`.
*   [x] **Autorreconexión resiliente** ante micro-cortes.
*   [x] Integración de **Tor Proxy Interno** con renovación de identidad.

### Fase 2: Mejora de UX (Próximamente)
*   [ ] Caché de logos en disco.
*   [ ] Grabación de streams de vídeo.
*   [ ] Grupos de favoritos personalizables.
*   [ ] Soporte para **múltiples archivos EPG** simultáneos.
