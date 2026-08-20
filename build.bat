@echo off
setlocal
REM ============================================================
REM  build.bat - Genera dist\IPTVViewer.exe con PyInstaller
REM  Uso:  build.bat
REM ============================================================
cd /d "%~dp0"

echo [1/3] Verificando entorno virtual...
if exist ".venv\Scripts\python.exe" (
    set "PY=.venv\Scripts\python.exe"
) else (
    echo   ERROR: No se encontro .venv\Scripts\python.exe
    echo   Crealo con:  python -m venv .venv
    echo   e instala dependencias con:  .venv\Scripts\pip install -r requirements.txt
    exit /b 1
)

echo [2/3] Verificando DLLs de mpv...
if not exist "bin\libmpv-2.dll" (
    echo   AVISO: No se encontro bin\libmpv-2.dll
    echo   El ejecutable se generara SIN el motor mpv.
    echo   Descarga libmpv para Windows y coloca las DLLs en bin\ (ver README).
)

echo [3/3] Compilando con PyInstaller...
"%PY%" -m PyInstaller --noconfirm --clean IPTVViewer.spec
if errorlevel 1 (
    echo.
    echo   ERROR: Fallo la compilacion.
    exit /b 1
)

echo.
echo Listo: dist\IPTVViewer.exe
echo Siguiente paso: release.bat [tag]   (ejemplo: release.bat v1.1)
exit /b 0
