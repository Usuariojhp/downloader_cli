"""Core data models using Pydantic."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, computed_field


class Format(BaseModel):
    """Media format information."""

    format_id: str
    ext: str
    resolution: str | None = None
    fps: float | None = None
    vcodec: str | None = None
    acodec: str | None = None
    filesize: int | None = None
    filesize_approx: int | None = None
    tbr: float | None = None  # total bitrate
    vbr: float | None = None  # video bitrate
    abr: float | None = None  # audio bitrate
    quality_note: str | None = None
    protocol: str | None = None
    height: int | None = None
    width: int | None = None

    @property
    def is_video(self) -> bool:
        return self.vcodec is not None and self.vcodec != "none"

    @property
    def is_audio(self) -> bool:
        return not self.is_video and self.acodec is not None and self.acodec != "none"

    @property
    def display_name(self) -> str:
        parts = []
        if self.resolution:
            parts.append(self.resolution)
        elif self.height:
            parts.append(f"{self.height}p")
        if self.fps and self.fps > 30:
            parts.append(f"{self.fps}fps")
        if self.tbr:
            parts.append(f"{self.tbr:.0f}k")
        if self.quality_note:
            parts.append(self.quality_note)
        return " ".join(parts) if parts else self.format_id


class Thumbnail(BaseModel):
    """Thumbnail information."""

    url: str
    width: int | None = None
    height: int | None = None
    resolution: str | None = None


class PlaylistEntry(BaseModel):
    """Single playlist entry."""

    id: str
    title: str
    url: str
    media_url: str | None = None
    duration: float | None = None
    thumbnail: str | None = None
    uploader: str | None = None
    index: int | None = None
    formats: list[Format] = Field(default_factory=list)

    def __lt__(self, other: PlaylistEntry) -> bool:
        return (self.index or 0) < (other.index or 0)


class MediaInfo(BaseModel):
    """Complete media information."""

    id: str
    title: str
    url: str
    platform: str
    uploader: str | None = None
    uploader_id: str | None = None
    uploader_url: str | None = None
    duration: float | None = None
    view_count: int | None = None
    like_count: int | None = None
    description: str | None = None
    thumbnail: str | None = None
    thumbnails: list[Thumbnail] = Field(default_factory=list)
    formats: list[Format] = Field(default_factory=list)
    subtitles: dict[str, Any] = Field(default_factory=dict)
    automatic_captions: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    age_limit: int | None = None
    is_live: bool = False
    was_live: bool = False
    availability: str | None = None

    # URL directa de medios, cuando el extractor sabe resolverla.
    # Spotify, por ejemplo, devuelve un vídeo equivalente en YouTube Music.
    media_url: str | None = None

    # Playlist fields
    is_playlist: bool = False
    playlist_title: str | None = None
    playlist_id: str | None = None
    playlist_uploader: str | None = None
    playlist_count: int | None = None
    entries: list[PlaylistEntry] = Field(default_factory=list)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def available_heights(self) -> list[int]:
        """Get sorted unique available video heights."""
        heights = {f.height for f in self.formats if f.height and f.is_video}
        return sorted(heights, reverse=True)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def available_qualities(self) -> list[str]:
        """Get formatted quality strings."""
        return [f"{h}p" for h in self.available_heights]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def best_video_format(self) -> Format | None:
        """Get best video format."""
        video_formats = [f for f in self.formats if f.is_video and f.height]
        if not video_formats:
            return None
        return max(video_formats, key=lambda f: (f.height or 0, f.tbr or 0))

    @computed_field  # type: ignore[prop-decorator]
    @property
    def best_audio_format(self) -> Format | None:
        """Get best audio format."""
        audio_formats = [f for f in self.formats if f.is_audio and not f.is_video]
        if not audio_formats:
            return None
        return max(audio_formats, key=lambda f: f.abr or 0)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def duration_str(self) -> str:
        """Format duration as human readable string."""
        if not self.duration:
            return "N/A"
        total = int(self.duration)
        hours, rem = divmod(total, 3600)
        minutes, seconds = divmod(rem, 60)
        if hours:
            return f"{hours}h {minutes}m {seconds}s"
        return f"{minutes}m {seconds}s"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def estimated_size(self) -> int | None:
        """Estimate total download size."""
        if self.is_playlist and self.entries:
            total = 0
            for entry in self.entries:
                if entry.formats:
                    best = max(entry.formats, key=lambda f: f.filesize or f.filesize_approx or 0)
                    total += best.filesize or best.filesize_approx or 0
            return total if total > 0 else None
        if self.formats:
            best = max(self.formats, key=lambda f: f.filesize or f.filesize_approx or 0)
            return best.filesize or best.filesize_approx
        return None


class DownloadRequest(BaseModel):
    """Download request parameters."""

    url: str
    media_type: Literal["video", "audio"] = "video"
    quality: str | None = None
    format: Literal["mp3", "original"] = "mp3"
    bitrate: Literal[128, 192, 320] = 192
    subtitles: list[str] = Field(default_factory=list)
    strategy: Literal["ultra", "normal"] = "ultra"
    output_path: str | None = None
    playlist_range: str | None = None
    force: bool = False


class DownloadResult(BaseModel):
    """Download operation result."""

    success: bool
    message: str
    filepath: str | None = None
    filesize: int | None = None
    duration: float | None = None
    error: str | None = None


DownloadRequest.model_rebuild()
