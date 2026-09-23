"""Core data models using Pydantic."""

from __future__ import annotations

from typing import Optional, List
from pydantic import BaseModel, Field, computed_field


class Format(BaseModel):
    """Media format information."""

    format_id: str
    ext: str
    resolution: Optional[str] = None
    fps: Optional[int] = None
    vcodec: Optional[str] = None
    acodec: Optional[str] = None
    filesize: Optional[int] = None
    filesize_approx: Optional[int] = None
    tbr: Optional[float] = None  # total bitrate
    vbr: Optional[float] = None  # video bitrate
    abr: Optional[float] = None  # audio bitrate
    quality_note: Optional[str] = None
    protocol: Optional[str] = None
    height: Optional[int] = None
    width: Optional[int] = None

    @property
    def is_video(self) -> bool:
        return self.vcodec is not None and self.vcodec != "none"

    @property
    def is_audio(self) -> bool:
        return self.acodec is not None and self.acodec != "none"

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
    width: Optional[int] = None
    height: Optional[int] = None
    resolution: Optional[str] = None


class PlaylistEntry(BaseModel):
    """Single playlist entry."""

    id: str
    title: str
    url: str
    duration: Optional[int] = None
    thumbnail: Optional[str] = None
    uploader: Optional[str] = None
    index: Optional[int] = None
    formats: List[Format] = Field(default_factory=list)

    def __lt__(self, other: PlaylistEntry) -> bool:
        return (self.index or 0) < (other.index or 0)


class MediaInfo(BaseModel):
    """Complete media information."""

    id: str
    title: str
    url: str
    platform: str
    uploader: Optional[str] = None
    uploader_id: Optional[str] = None
    uploader_url: Optional[str] = None
    duration: Optional[int] = None
    view_count: Optional[int] = None
    like_count: Optional[int] = None
    description: Optional[str] = None
    thumbnail: Optional[str] = None
    thumbnails: List[Thumbnail] = Field(default_factory=list)
    formats: List[Format] = Field(default_factory=list)
    subtitles: dict = Field(default_factory=dict)
    automatic_captions: dict = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)
    categories: List[str] = Field(default_factory=list)
    age_limit: Optional[int] = None
    is_live: bool = False
    was_live: bool = False
    availability: Optional[str] = None

    # Playlist fields
    is_playlist: bool = False
    playlist_title: Optional[str] = None
    playlist_id: Optional[str] = None
    playlist_uploader: Optional[str] = None
    playlist_count: Optional[int] = None
    entries: List[PlaylistEntry] = Field(default_factory=list)

    @computed_field
    @property
    def available_heights(self) -> List[int]:
        """Get sorted unique available video heights."""
        heights = {f.height for f in self.formats if f.height and f.is_video}
        return sorted(heights, reverse=True)

    @computed_field
    @property
    def available_qualities(self) -> List[str]:
        """Get formatted quality strings."""
        return [f"{h}p" for h in self.available_heights]

    @computed_field
    @property
    def best_video_format(self) -> Format | None:
        """Get best video format."""
        video_formats = [f for f in self.formats if f.is_video and f.height]
        if not video_formats:
            return None
        return max(video_formats, key=lambda f: (f.height or 0, f.tbr or 0))

    @computed_field
    @property
    def best_audio_format(self) -> Format | None:
        """Get best audio format."""
        audio_formats = [f for f in self.formats if f.is_audio and not f.is_video]
        if not audio_formats:
            return None
        return max(audio_formats, key=lambda f: f.abr or 0)

    @computed_field
    @property
    def duration_str(self) -> str:
        """Format duration as human readable string."""
        if not self.duration:
            return "N/A"
        hours, rem = divmod(self.duration, 3600)
        minutes, seconds = divmod(rem, 60)
        if hours:
            return f"{hours}h {minutes}m {seconds}s"
        return f"{minutes}m {seconds}s"

    @computed_field
    @property
    def estimated_size(self) -> Optional[int]:
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
    quality: Optional[str] = None
    format: Literal["mp3", "original"] = "mp3"
    bitrate: Literal[128, 192, 320] = 192
    subtitles: List[str] = Field(default_factory=list)
    strategy: Literal["ultra", "normal"] = "ultra"
    output_path: Optional[str] = None
    playlist_range: Optional[str] = None
    force: bool = False


class DownloadResult(BaseModel):
    """Download operation result."""

    success: bool
    message: str
    filepath: Optional[str] = None
    filesize: Optional[int] = None
    duration: Optional[float] = None
    error: Optional[str] = None