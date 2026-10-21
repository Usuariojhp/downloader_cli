#!/bin/bash
# Build script for veluz portable executable
# Supports Linux and macOS

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}=========================================="
echo -e "  veluz - Build Portable Executable"
echo -e "==========================================${NC}"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 no está instalado${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 --version)
echo -e "${GREEN}✅ Python encontrado: ${PYTHON_VERSION}${NC}"

# Check pip
if ! command -v pip3 &> /dev/null; then
    echo -e "${RED}❌ pip no está instalado${NC}"
    exit 1
fi

echo -e "${GREEN}✅ pip encontrado${NC}"

# Install dependencies
echo ""
echo -e "${CYAN}📦 Instalando dependencias...${NC}"
pip3 install -e ".[dev]"

# Install PyInstaller
echo ""
echo -e "${CYAN}📦 Instalando PyInstaller...${NC}"
pip3 install pyinstaller

# Build with PyInstaller
echo ""
echo -e "${CYAN}🔨 Compilando ejecutable portable...${NC}"
echo ""

pyinstaller --clean --noconfirm build/veluz.spec

# Verify build
if [ -f "dist/veluz" ]; then
    echo ""
    echo -e "${GREEN}=========================================="
    echo -e "✅ ¡COMPILACIÓN EXITOSA!"
    echo -e "==========================================${NC}"
    echo ""
    echo -e "${CYAN}📁 El ejecutable está en: ./dist/veluz${NC}"
    echo ""
    echo -e "${YELLOW}Archivo generado:${NC}"
    ls -lh dist/veluz
    echo ""
    echo -e "${CYAN}Para usar el programa portable:${NC}"
    echo "  1. Copia el ejecutable 'dist/veluz' a cualquier ubicación"
    echo "  2. Dale permisos: chmod +x veluz"
    echo "  3. Ejecuta: ./veluz"
    echo ""
    echo -e "${YELLOW}Nota: Necesitarás tener instalado en el sistema:${NC}"
    echo "  • aria2c (opcional, para descargas ultra rápidas)"
    echo "  • ffmpeg (para conversión de audio a MP3)"
    echo ""
else
    echo ""
    echo -e "${RED}❌ Error en la compilación${NC}"
    exit 1
fi

# Cleanup
read -p "¿Deseas limpiar archivos temporales? (s/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Ss]$ ]]; then
    echo -e "${CYAN}🧹 Limpiando archivos temporales...${NC}"
    rm -rf build/veluz
    rm -rf *.spec
    echo -e "${GREEN}✅ Limpieza completada${NC}"
fi

echo ""
echo -e "${GREEN}🎉 ¡Proceso completado!${NC}"