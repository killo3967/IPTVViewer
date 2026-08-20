@echo off
setlocal
REM ============================================================
REM  release.bat - Sube dist\IPTVViewer.exe a una release de GitHub
REM  Uso:  release.bat [tag]   (ejemplo: release.bat v1.1)
REM        Si no indicas tag, te lo pregunta.
REM ============================================================
cd /d "%~dp0"

set "REPO=killo3967/IPTVViewer"
set "TAG=%~1"

if "%TAG%"=="" (
    set /p TAG="Version del tag (ejemplo: v1.1): "
)
if "%TAG%"=="" (
    echo   ERROR: No se indico un tag.
    exit /b 1
)

if not exist "dist\IPTVViewer.exe" (
    echo   ERROR: No existe dist\IPTVViewer.exe.
    echo   Ejecuta primero:  build.bat
    exit /b 1
)

echo Verificando autenticacion de GitHub CLI...
gh auth status 1>nul 2>nul
if errorlevel 1 (
    echo   ERROR: gh no esta autenticado. Ejecuta:  gh auth login
    exit /b 1
)

echo Subiendo release %TAG% a %REPO% ...
gh release create %TAG% -R %REPO% --title "%TAG%" --generate-notes dist\IPTVViewer.exe
if errorlevel 1 (
    echo   ERROR: Fallo la creacion de la release.
    echo   Si el tag ya existe, borralo con:  gh release delete %TAG% -R %REPO% --yes
    exit /b 1
)

echo.
echo Release publicada: https://github.com/%REPO%/releases/tag/%TAG%
exit /b 0
