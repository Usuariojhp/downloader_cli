@echo off
REM Build script for media-dl portable executable (Windows)

setlocal enabledelayedexpansion

REM Colors
set RED=
set GREEN=
set YELLOW=
set CYAN=
set NC=

echo ==========================================
echo   media-dl - Build Portable Executable
echo ==========================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python no está instalado o no está en PATH
    exit /b 1
)
for /f "tokens=*" %%a in ('python --version') do set PYTHON_VERSION=%%a
echo [OK] Python encontrado: %PYTHON_VERSION%

REM Check pip
pip --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] pip no está instalado
    exit /b 1
)
echo [OK] pip encontrado

REM Install dependencies
echo.
echo [INFO] Instalando dependencias...
pip install -e ".[dev]"

REM Install PyInstaller
echo.
echo [INFO] Instalando PyInstaller...
pip install pyinstaller

REM Build with PyInstaller
echo.
echo [INFO] Compilando ejecutable portable...
echo.

pyinstaller --clean --noconfirm build\media_dl.spec

REM Verify build
if exist "dist\media-dl.exe" (
    echo.
    echo ==========================================
    echo [SUCCESS] ¡COMPILACIÓN EXITOSA!
    echo ==========================================
    echo.
    echo [INFO] El ejecutable está en: .\dist\media-dl.exe
    echo.
    echo [INFO] Archivo generado:
    dir dist\media-dl.exe
    echo.
    echo [INFO] Para usar el programa portable:
    echo   1. Copia el ejecutable dist\media-dl.exe a cualquier ubicación
    echo   2. Ejecuta: media-dl.exe
    echo.
    echo [NOTE] Necesitarás tener instalado en el sistema:
    echo   - aria2c (opcional, para descargas ultra rápidas)
    echo   - ffmpeg (para conversión de audio a MP3)
    echo.
) else (
    echo.
    echo [ERROR] Error en la compilación
    exit /b 1
)

REM Cleanup
set /p CLEANUP=¿Deseas limpiar archivos temporales? (s/n):
if /i "%CLEANUP%"=="s" (
    echo.
    echo [INFO] Limpiando archivos temporales...
    rmdir /s /q build\media-dl 2>nul
    echo [OK] Limpieza completada
)

echo.
echo [SUCCESS] ¡Proceso completado!
pause