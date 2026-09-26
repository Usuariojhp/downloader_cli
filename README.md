# 🚀 media-dl - Unified Media Downloader

**Cyan Edition v2.0.0** - Descargador multimedia unificado con interfaz moderna en tonos cian.

[![Version](https://img.shields.io/badge/version-2.0.0-blue)](https://github.com/Usuariojhp/downloader_cli)
[![CI](https://github.com/Usuariojhp/downloader_cli/actions/workflows/ci.yml/badge.svg)](https://github.com/Usuariojhp/downloader_cli/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11+-green)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-orange)](LICENSE)

---

## ✨ Características

### 🎯 Descargas Principales
- **Video** - Múltiples resoluciones (4K, 1080p, 720p, 480p, etc.)
- **Audio** - Formato original o conversión a MP3 (320, 192, 128 kbps)
- **Subtítulos** - Descarga automática en múltiples idiomas

### 🌐 Plataformas Soportadas
La columna "Verificado" indica si la descarga se ha probado de extremo a
extremo contra la plataforma real, no solo si el extractor existe.

| Plataforma | Video | Audio | Playlists | Verificado | Notas |
|------------|-------|-------|-----------|-----------|-------|
| YouTube | ✅ | ✅ | ✅ | Sí | Vídeo, MP3, subtítulos, 4K, playlists |
| TikTok | ✅ | ✅ | ❌ | Sí | API tikwn con degradación a yt-dlp |
| Facebook | ✅ | ✅ | ❌ | Sí | Vídeos públicos (fb.watch) |
| Spotify | ❌ | ✅ | ✅ | Sí | Busca el audio en YouTube Music; necesita `spotdl`; incrusta la carátula |
| SoundCloud | ❌ | ✅ | ✅ | No | Metadatos con `scdl`, descarga con yt-dlp |
| Instagram | ⚠️ | ⚠️ | ❌ | No | Ver [Instagram](#instagram-y-x-requieren-cuenta) |
| Twitter/X | ⚠️ | ⚠️ | ❌ | No | Ver [Instagram](#instagram-y-x-requieren-cuenta) |
| +100 más | ✅ | ✅ | ✅ | Parcial | Via yt-dlp, depende de la plataforma |

#### Instagram y X requieren cuenta
Instagram y Twitter/X **no** funcionan de forma anónima: yt-dlp necesita
credenciales de sesión para ese contenido, y además cambia la API con
frecuencia. Si ves un error tipo `No video formats found` o `No video could
be found`, no es un fallo de media-dl sino que la publicación no es pública
o la plataforma pide login. Para YouTube, TikTok, Facebook y el resto vía
yt-dlp no hace falta ninguna cuenta.

### ⚡ Rendimiento
- **Modo Ultra** - aria2c con 16 conexiones paralelas (hasta 10x más rápido)
- **Modo Normal** - yt-dlp nativo (sin dependencias externas)
- **Reintentos inteligentes** - Hasta 3 intentos con backoff
- **Descargas concurrentes** - Hasta 8 en lote con `--concurrent`

### 📊 Gestión Avanzada
- **Historial SQLite** - Registro completo con metadatos
- **Detección de duplicados** - Por URL: si vuelves a descargar lo mismo te
  avisa. Si dices que sí, **no pisa el archivo anterior**: crea uno nuevo con
  `(1)`, `(2)`... y el primero queda intacto
- **Configuración persistente** - JSON + variables de entorno
- **Playlists** - Rangos personalizados (ej: `1-5, 10, 15-20`)

### 🎨 Interfaz
- Tema **cian** moderno y consistente
- Barras de progreso en tiempo real
- Tablas formateadas con Rich
- Menús interactivos intuitivos

---

## 📦 Instalación

> ⚠️ **Este proyecto NO está en PyPI.** Existe un paquete llamado `media-dl`
> en PyPI que **no es este proyecto** (lo publica un tercero, versión 0.1).
> `pip install media-dl` te instalaría su código, no el nuestro. Instala
> siempre desde el repositorio, como se explica abajo.

**Requisitos:** Python **3.11 o superior**. Con 3.10 o inferior la instalación falla.

### Opción 1: Desde el repositorio (la única vía soportada)

El repositorio es privado, así que hace falta tu clave SSH de GitHub.

```bash
git clone git@github.com:Usuariojhp/downloader_cli.git
cd downloader_cli
python3 -m venv .venv && source .venv/bin/activate   # opcional pero recomendado
pip install -e .
```

Para trabajar en el proyecto (tests, linter, tipos):

```bash
pip install -e ".[dev]"
```

### Opción 2: Ejecutable portable (sin instalar Python)

Cada push a `master` compila un binario autónomo para Linux. Se descarga desde
la pestaña **Actions** del repo → última ejecución → **Artifacts** →
`media-dl-linux` (requiere iniciar sesión en GitHub). Son ~183 MB porque
lleva Python y todas las dependencias dentro.

```bash
chmod +x media-dl
./media-dl doctor     # comprueba que funciona
./media-dl doctor --strict   # sale con error si le falta alguna extensión
```

El binario que publica la CI **incluye** el extra de Spotify, así que las
descargas de Spotify funcionan igual que con `pip` (verificado: MP3 con la
portada incrustada). `doctor --strict` existe justo para esto: si alguna vez
el empaquetado deja fuera una dependencia, el binario lo dice y sale con
código de error en vez de fingir que está bien. Si compilas tú el spec sin
instalar `.[spotify]`, `doctor` te avisará de que esa plataforma no está.

Solo para Linux x86-64. Para Windows usa `build\build.bat` (no verificado).

### Extras opcionales

Spotify y SoundCloud necesitan herramientas adicionales que **no** son
obligatorias:

```bash
pip install -e ".[spotify]"     # descarga de Spotify (requiere spotdl)
pip install -e ".[soundcloud]"  # descarga de SoundCloud (requiere scdl)
```

### Dependencias del sistema

Ninguna es obligatoria: sin ellas el programa funciona igual, pero sin
descargas "ultra" (aria2c) y sin conversión a MP3 (ffmpeg).

```bash
# Fedora
sudo dnf install aria2 ffmpeg

# Ubuntu/Debian
sudo apt install aria2 ffmpeg

# Arch
sudo pacman -S aria2 ffmpeg

# macOS
brew install aria2 ffmpeg

# Windows (Chocolatey)
choco install aria2 ffmpeg

# Windows (Scoop)
scoop install aria2 ffmpeg
```

Comprueba lo que tienes con:

```bash
media-dl doctor
```

---

## 🚀 Uso Rápido

### Comandos básicos
Al descargar te **pregunta la calidad** (o el formato de audio), con la que
tienes configurada marcada como actual. Si en la terminal no hay nadie —un
script, una tubería, CI— no pregunta y aplica tu configuración.

```bash
# Descargar video (pregunta la calidad)
media-dl download video "https://youtube.com/watch?v=..."

# Decidir tú la calidad y que no pregunte
media-dl download video "https://..." -q 1080

# Descargar audio (pregunta formato y bitrate)
media-dl download audio "https://youtube.com/watch?v=..."

# Descargar playlist completa (automática, no pregunta por cada vídeo)
media-dl playlist "https://youtube.com/playlist?list=..."

# Ver historial
media-dl history

# Verificar sistema
media-dl doctor
```

### Opciones avanzadas
```bash
# Video calidad específica + subtítulos
media-dl download video "URL" --quality 1080 --subs es,en

# Audio formato original (sin convertir)
media-dl download audio "URL" --format original

# Descarga por lotes desde archivo (hasta 8 en paralelo)
media-dl download batch -f urls.txt --type video --concurrent 4

# Playlist solo videos 1-5 y 10 (o todas con --range all)
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

### Todas las claves configurables

| Clave | Tipo | Valores / Rango | Default | Descripción |
|-------|------|-----------------|---------|-------------|
| `download_path` | `path` | carpeta absoluta o relativa | `./downloads` | Carpeta donde se guardan las descargas |
| `download_mode` | `choice` | `ultra` \| `normal` | `ultra` | `ultra` usa aria2c (8+ conexiones), `normal` usa yt-dlp directo |
| `default_video_quality` | `string` | `auto`, `1080`, `720`, `480`, `best`, `worst` | `auto` | Calidad de video por defecto |
| `default_audio_format` | `choice` | `mp3` \| `original` | `mp3` | Formato de audio por defecto |
| `default_audio_bitrate` | `int` | 128–320 | 192 | Bitrate MP3 en kbps |
| `auto_subtitle` | `bool` | `true` \| `false` | `false` | Descargar subtítulos automáticos |
| `subtitle_languages` | `list` | códigos ISO separados por coma (ej: `es,en`) | `""` | Idiomas de subtítulos preferidos |
| `retry_attempts` | `int` | 1–10 | 3 | Reintentos tras fallo de red |
| `check_duplicates` | `bool` | `true` \| `false` | `true` | Evita bajar archivos ya en historial |
| `aria2c_connections` | `int` | 4–32 | 16 | Conexiones simultáneas por archivo (modo ultra) |
| `aria2c_split` | `int` | 1–32 | 1 | Número de segmentos por conexión |
| `max_download_speed` | `int` | 0–1000000 KB/s (0 = sin límite) | 0 | Límite global de velocidad de descarga |
| `concurrent_downloads` | `int` | 1–8 | 3 | Archivos en paralelo (batch / playlist) |
| `embed_thumbnail` | `bool` | `true` \| `false` | `true` | Incrustar carátula en el archivo de audio |
| `embed_metadata` | `bool` | `true` \| `false` | `true` | Escribir metadatos ID3 (título, artista, álbum...) |
| `write_info_json` | `bool` | `true` \| `false` | `false` | Guardar `.info.json` de yt-dlp junto al archivo |

> **Notas:** `embed_thumbnail` solo funciona si la fuente provee la imagen (YouTube Music/Spotify: media-dl la descarga aparte y la inyecta). Si no hay carátula, el archivo se guarda sin ella — la descarga no falla.

### Variables de entorno
Tienen prioridad sobre `config.json` (prefijo `MEDIA_DL_` + nombre de la clave en mayúsculas).

```bash
export MEDIA_DL_DOWNLOAD_PATH=~/Downloads
export MEDIA_DL_DOWNLOAD_MODE=ultra
export MEDIA_DL_ARIA2C_CONNECTIONS=32
export MEDIA_DL_MAX_DOWNLOAD_SPEED=5000  # KB/s
export MEDIA_DL_CONFIG_DIR=~/.config/media-dl  # dónde vive config.json
```

### 🔑 Credenciales de Spotify (opcional)

**¿Por qué?** Sin credenciales, media-dl usa la API pública anónima de Spotify:
- Límites de tasa muy estrictos (IP compartida)
- A veces falla al obtener metadatos / carátulas

**Con tus credenciales propias:** límites mucho más altos, metadata consistente, cero errores 429.

**Cómo conseguir:**
1. Ve a [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. "Create App" → nombre cualquiera → guardar
3. Copia **Client ID** y **Client Secret**

**Dónde ponerlas (elige una):**

```bash
# Opción A: Variables de entorno (recomendado, no toca archivos)
export MEDIA_DL_SPOTIFY_CLIENT_ID=tu_client_id
export MEDIA_DL_SPOTIFY_CLIENT_SECRET=tu_client_secret
# Añádelas a tu ~/.bashrc o ~/.zshrc para que persistan
```

```bash
# Opción B: Archivo de configuración local
media-dl config set spotify_client_id TU_CLIENT_ID
media-dl config set spotify_client_secret TU_CLIENT_SECRET
# Se guarda en ~/.config/media-dl/config.json — **nunca lo subas a git ni lo compartas**
```

> **Nota:** El binario portable (`dist/media-dl`) también lee `~/.config/media-dl/config.json`. Las credenciales **no** van embebidas en el ejecutable.

### Modo interactivo — Configuración
```
media-dl interactive
  → 5 ⚙️ Configuración
      → 1 Ver configuración
      → 2 Cambiar valor  (te pide la clave y su nuevo valor)
      → 3 Restablecer por defecto
      → 4 Ver rutas
      → 0 Volver
```
En **Cambiar valor** se listan las claves válidas y se valida tu entrada.

---

## 🔧 Comandos Completos

### `media-dl download video`
```bash
media-dl download video URL [OPTIONS]

Options:
  -q, --quality TEXT    Calidad (pregunta si se omite)
  --ultra / --normal    Modo descarga (default: ultra)
  -s, --subs TEXT       Subtítulos (ej: es,en)
  -o, --output PATH     Directorio de salida
  -F, --force           Forzar descarga aunque exista
```

### `media-dl download audio`
```bash
media-dl download audio URL [OPTIONS]

Options:
  -f, --format [mp3|original]  Formato (pregunta si se omite)
  -b, --bitrate [128|192|320]  Bitrate MP3 (pregunta si se omite)
  --ultra / --normal           Modo descarga
  -o, --output PATH            Directorio de salida
  -F, --force                  Forzar descarga
```

### `media-dl download batch`
```bash
media-dl download batch [OPTIONS]

Options:
  -f, --file PATH        Archivo con URLs (una por línea)
  -t, --type [video|audio] Tipo de descarga (default: video)
  -c, --concurrent INT   Descargas simultáneas (1-8, default: 3)
  --ultra / --normal     Modo descarga
```

El lote **no pregunta nada**: baja cada URL a la mejor calidad, porque
preguntar por cada una sería insoportable. Usa la calidad de tu configuración
(`dl config set default_video_quality ...`).

### `media-dl playlist`
```bash
media-dl playlist URL [OPTIONS]

Options:
  -r, --range TEXT       Rango (ej: 1-5,10,15-20) o 'all'
  -t, --type [video|audio] Tipo (default: video)
  -f, --format [mp3|original] Formato audio
  -b, --bitrate [128|192|320] Bitrate MP3
  --ultra / --normal     Modo descarga
  -o, --output PATH      Directorio de salida
```

### `media-dl history`
```bash
media-dl history [OPTIONS]
media-dl history clear [--platform P] [--type T] [--force]

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
media-dl doctor [--verbose]      # Diagnóstico del sistema
media-dl doctor update           # Actualizar yt-dlp y dependencias
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
│   │   ├── history/         # sqlite3 + Repository
│   │   └── progress.py      # Rich progress hooks
│   ├── ui/                  # Tema cian + componentes
│   └── cli/commands/        # Comandos Typer
├── build/                   # PyInstaller scripts
└── tests/                   # pytest suite
```

### Patrones de diseño
- **Extractor Registry** - Prioridad por plataforma, con degradación a yt-dlp
- **Strategy Pattern** - aria2c / native intercambiables
- **Repository Pattern** - Historial tipado sobre `sqlite3` (stdlib)
- **Settings Management** - Pydantic Settings v2 (JSON + env)

---

## 🧪 Testing

```bash
# Ejecutar tests
pytest

# Con coverage
pytest --cov=src/media_dl --cov-report=term-missing

# Solo tests unitarios
pytest tests/test_models.py tests/test_strategies.py
```

La suite aísla `MEDIA_DL_CONFIG_DIR` en un directorio temporal, así que nunca
toca tu `~/.config/media-dl` real.

### Estado de la verificación

| Comprobación | Estado |
|---|---|
| `pytest` | 244 tests, todos en verde |
| `ruff check .` | 0 errores |
| `ruff format --check .` | 0 diferencias |
| `mypy src/` (strict) | 0 errores |
| Cobertura | 73% (CI falla si baja del 65%) |
| `pyinstaller` | binario portable verificado |
| CI (GitHub Actions) | `pytest` + `ruff` + `mypy` + cobertura + binario |

Todo esto corre automáticamente en cada push y en cada Pull Request
a `.github/workflows/ci.yml`.

---

## 📦 Empaquetado

### PyInstaller (binario portable)
```bash
# Linux/macOS
./build/build.sh

# Windows
build\build.bat

# O manual (usa el spec del repo)
pyinstaller --clean --noconfirm build/media_dl.spec
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
2. Rama: `git checkout -b feature/nueva-funcionalidad`
3. Antes de abrir el PR, las cuatro puertas tienen que pasar en verde:
   ```bash
   pytest                      # 212 tests
   ruff check .                # lint
   ruff format --check .       # formato
   mypy src/                   # tipos (modo strict)
   ```
4. Commit con un mensaje que explique el *porqué*, no solo el *qué*
5. `git push origin feature/nueva-funcionalidad` y abre el Pull Request

La CI ejecuta exactamente esos mismos comandos, así que si pasa en tu máquina
pasa en GitHub.

### Cómo está organizado el proyecto

| Carpeta | Contenido |
|---------|-----------|
| `src/media_dl/core/extractors/` | Un extractor por plataforma, con prioridad |
| `src/media_dl/core/strategies/` | aria2c y yt-dlp como estrategias intercambiables |
| `src/media_dl/core/history/` | Historial en SQLite |
| `src/media_dl/cli/commands/` | Los comandos de la terminal |
| `src/media_dl/ui/` | Colores, tablas, menús y barras de progreso |
| `tests/` | 212 tests, uno por comportamiento |

Añadir una plataforma nueva es un fichero en `core/extractors/` que herede de
`Extractor` y se registre con `@register_extractor`. El registro se encarga
de elegirlo por prioridad.

---

## 📄 Licencia

MIT License - ver [LICENSE](LICENSE) para detalles.

---

## 🙏 Créditos

- **yt-dlp** - Motor de descarga principal
- **Rich** - Interfaz de terminal hermosa
- **Typer** - CLI framework moderno
- **Pydantic** - Validación de datos
- **sqlite3** - Historial de descargas (stdlib)
- **aria2** - Descargador ultra rápido
- **FFmpeg** - Procesamiento multimedia

---

## 💬 Soporte

- **Errores**: [GitHub Issues](https://github.com/Usuariojhp/downloader_cli/issues/new/choose)
- **Preguntas**: [nueva pregunta](https://github.com/Usuariojhp/downloader_cli/issues/new/choose)
- **Estado de las pruebas**: [CI en GitHub Actions](https://github.com/Usuariojhp/downloader_cli/actions/workflows/ci.yml)

Es un proyecto personal y el soporte es limitado: si algo falla, abre una issue
con la salida de `media-dl doctor` y el comando exacto que ejecutaste.

---

## 🌟 ¿Te gusta el proyecto?

¡Dale una ⭐ en GitHub! Ayuda a que más gente lo descubra.

---

**Desarrollado con ❤️ para la comunidad**

*media-dl v2.0.0 - Cyan Edition*