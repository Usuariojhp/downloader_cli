# 🚀 media-dl - Unified Media Downloader

**Cyan Edition v2.0.0** - Descargador multimedia unificado con interfaz moderna en tonos cian.

[![Version](https://img.shields.io/badge/version-2.0.0-blue)](https://github.com/media-dl/media-dl)
[![Python](https://img.shields.io/badge/python-3.11+-green)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-orange)](LICENSE)

---

## ✨ Características

### 🎯 Descargas Principales
- **Video** - Múltiples resoluciones (4K, 1080p, 720p, 480p, etc.)
- **Audio** - Formato original o conversión a MP3 (320, 192, 128 kbps)
- **Subtítulos** - Descarga automática en múltiples idiomas

### 🌐 Plataformas Soportadas
| Plataforma | Video | Audio | Playlists | Notas |
|------------|-------|-------|-----------|-------|
| YouTube | ✅ | ✅ | ✅ | Completo |
| TikTok | ✅ | ✅ | ✅ | Fallback tikwn.com |
| Instagram | ✅ | ✅ | ❌ | Reels, Stories |
| Twitter/X | ✅ | ✅ | ❌ | Videos nativos |
| Facebook | ✅ | ✅ | ❌ | fb.watch |
| Spotify | ❌ | ✅ | ✅ | Requiere `spotdl` |
| SoundCloud | ❌ | ✅ | ✅ | Requiere `scdl` |
| +100 más | ✅ | ✅ | ✅ | Via yt-dlp |

### ⚡ Rendimiento
- **Modo Ultra** - aria2c con 16 conexiones paralelas (hasta 10x más rápido)
- **Modo Normal** - yt-dlp nativo (sin dependencias externas)
- **Reintentos inteligentes** - Hasta 3 intentos con backoff
- **Descargas concurrentes** - Hasta 8 en lote

### 📊 Gestión Avanzada
- **Historial SQLite** - Registro completo con metadatos
- **Detección duplicados** - Por URL hash + hash de archivo
- **Configuración persistente** - JSON + variables de entorno
- **Playlists** - Rangos personalizados (ej: `1-5, 10, 15-20`)

### 🎨 Interfaz
- Tema **cian** moderno y consistente
- Barras de progreso en tiempo real
- Tablas formateadas con Rich
- Menús interactivos intuitivos

---

## 📦 Instalación

### Opción 1: Desde PyPI (recomendado)
```bash
pip install media-dl
```

### Opción 2: Desde código (desarrollo)
```bash
git clone https://github.com/media-dl/media-dl
cd media-dl
pip install -e ".[dev]"
```

### Opción 3: Ejecutable portable (sin Python)
```bash
# Descargar release desde GitHub Releases
chmod +x media-dl
./media-dl --help
```

### Dependencias del sistema (recomendadas)
```bash
# Ubuntu/Debian
sudo apt install aria2 ffmpeg

# macOS
brew install aria2 ffmpeg

# Windows (Chocolatey)
choco install aria2 ffmpeg

# Windows (Scoop)
scoop install aria2 ffmpeg
```

---

## 🚀 Uso Rápido

### Comandos básicos
```bash
# Descargar video (selector interactivo de calidad)
media-dl video "https://youtube.com/watch?v=..."

# Descargar audio MP3 192kbps
media-dl audio "https://youtube.com/watch?v=..."

# Descargar playlist completa
media-dl playlist "https://youtube.com/playlist?list=..."

# Ver historial
media-dl history

# Verificar sistema
media-dl doctor
```

### Opciones avanzadas
```bash
# Video calidad específica + subtítulos
media-dl video "URL" --quality 1080 --subs es,en

# Audio formato original (sin convertir)
media-dl audio "URL" --format original

# Descarga por lotes desde archivo
media-dl download batch urls.txt --type video

# Playlist solo videos 1-5 y 10
media-dl playlist "URL" --range 1-5,10

# Configurar carpeta de descargas
media-dl config set download_path ~/Downloads
```

### Modo interactivo
```bash
media-dl interactive
```

---

## ⚙️ Configuración

### Archivo de configuración (`~/.config/media-dl/config.json`)
```json
{
  "download_path": "./downloads",
  "download_mode": "ultra",
  "default_video_quality": "auto",
  "default_audio_format": "mp3",
  "default_audio_bitrate": 192,
  "aria2c_connections": 16,
  "retry_attempts": 3,
  "check_duplicates": true,
  "concurrent_downloads": 3,
  "embed_thumbnail": true,
  "embed_metadata": true
}
```

### Variables de entorno
```bash
export MEDIA_DL_DOWNLOAD_PATH=~/Downloads
export MEDIA_DL_DOWNLOAD_MODE=ultra
export MEDIA_DL_ARIA2C_CONNECTIONS=32
export MEDIA_DL_MAX_DOWNLOAD_SPEED=5000  # KB/s
```

---

## 🔧 Comandos Completos

### `media-dl download video`
```bash
media-dl download video URL [OPTIONS]

Options:
  -q, --quality TEXT    Calidad (auto, 2160, 1440, 1080, 720, 480)
  --ultra / --normal    Modo descarga (default: ultra)
  -s, --subs TEXT       Subtítulos (ej: es,en)
  -o, --output PATH     Directorio de salida
  -f, --force           Forzar descarga aunque exista
```

### `media-dl download audio`
```bash
media-dl download audio URL [OPTIONS]

Options:
  -f, --format [mp3|original]  Formato (default: mp3)
  -b, --bitrate [128|192|320]  Bitrate MP3 (default: 192)
  --ultra / --normal           Modo descarga
  -o, --output PATH            Directorio de salida
  -f, --force                  Forzar descarga
```

### `media-dl download batch`
```bash
media-dl download batch [OPTIONS]

Options:
  -f, --file PATH        Archivo con URLs (una por línea)
  -t, --type [video|audio] Tipo de descarga (default: video)
  -c, --concurrent INT   Descargas concurrentes (1-8, default: 3)
  --ultra / --normal     Modo descarga
```

### `media-dl playlist`
```bash
media-dl playlist URL [OPTIONS]

Options:
  -r, --range TEXT       Rango (ej: 1-5,10,15-20)
  -t, --type [video|audio] Tipo (default: video)
  -f, --format [mp3|original] Formato audio
  -b, --bitrate [128|192|320] Bitrate MP3
```

### `media-dl history`
```bash
media-dl history [OPTIONS]

Options:
  -l, --limit INT        Límite entradas (default: 20)
  -p, --platform TEXT    Filtrar plataforma
  -t, --type [video|audio] Filtrar tipo
  -s, --stats            Mostrar estadísticas
```

### `media-dl config`
```bash
media-dl config show          # Ver configuración
media-dl config set KEY [VAL] # Establecer valor
media-dl config reset         # Restablecer defaults
media-dl config path          # Ver rutas
```

### `media-dl doctor`
```bash
media-dl doctor [--verbose]   # Diagnóstico sistema
media-dl update               # Actualizar yt-dlp y deps
```

---

## 🏗️ Arquitectura

```
media-dl/
├── src/media_dl/
│   ├── main.py              # Entry point Typer
│   ├── config/              # Pydantic Settings
│   ├── core/
│   │   ├── models.py        # Pydantic models
│   │   ├── extractors/      # Extractores por plataforma
│   │   ├── strategies/      # Estrategias descarga
│   │   ├── history/         # SQLAlchemy + Repository
│   │   └── progress.py      # Rich progress hooks
│   ├── ui/                  # Tema cian + componentes
│   └── cli/commands/        # Comandos Typer
├── build/                   # PyInstaller scripts
└── tests/                   # pytest suite
```

### Patrones de diseño
- **Extractor Registry** - Prioridad por plataforma (TikTok → tikwn.com)
- **Strategy Pattern** - aria2c / native intercambiables
- **Repository Pattern** - Historial tipado con SQLAlchemy 2.0
- **Settings Management** - Pydantic Settings v2 (JSON + env)

---

## 🧪 Testing

```bash
# Ejecutar tests
pytest

# Con coverage
pytest --cov=src/media_dl

# Solo tests unitarios
pytest tests/test_models.py tests/test_strategies.py
```

---

## 📦 Empaquetado

### PyInstaller (binario portable)
```bash
# Linux/macOS
./build/build.sh

# Windows
build\build.bat

# O manual
pyinstaller --clean --onefile --name media-dl src/media_dl/main.py
```

### PyPI Package
```bash
# Build
pip install build
python -m build

# Publicar
twine upload dist/*
```

---

## 🤝 Contribuir

1. Fork del repositorio
2. Crear rama: `git checkout -b feature/nueva-funcionalidad`
3. Commit: `git commit -am 'Agregar nueva funcionalidad'`
4. Push: `git push origin feature/nueva-funcionalidad`
5. Abrir Pull Request

### Estándares de código
```bash
# Formatear
ruff format .

# Lint
ruff check .

# Type check
mypy src/
```

---

## 📄 Licencia

MIT License - ver [LICENSE](LICENSE) para detalles.

---

## 🙏 Créditos

- **yt-dlp** - Motor de descarga principal
- **Rich** - Interfaz de terminal hermosa
- **Typer** - CLI framework moderno
- **Pydantic** - Validación de datos
- **SQLAlchemy** - ORM para historial
- **aria2** - Descargador ultra rápido
- **FFmpeg** - Procesamiento multimedia

---

## 💬 Soporte

- **Issues**: [GitHub Issues](https://github.com/media-dl/media-dl/issues)
- **Documentación**: [Wiki](https://github.com/media-dl/media-dl/wiki)
- **Discusiones**: [GitHub Discussions](https://github.com/media-dl/media-dl/discussions)

---

## 🌟 ¿Te gusta el proyecto?

¡Dale una ⭐ en GitHub! Ayuda a que más gente lo descubra.

---

**Desarrollado con ❤️ para la comunidad**

*media-dl v2.0.0 - Cyan Edition*