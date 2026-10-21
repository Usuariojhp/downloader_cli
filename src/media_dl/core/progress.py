"""Unified progress hooks for yt-dlp with Rich.

yt-dlp only emits the ``finished`` hook when it delegates a download to an
external downloader such as aria2c.  That makes the progress bar stay at 0%
until the file is complete.  ``PartialFileMonitor`` fills that gap by polling
aria2c's ``.aria2`` control file and counting completed pieces.

aria2c writes pieces out of order, so the size of the ``.part`` file is *not*
the number of bytes downloaded: one connection can write the last piece first
and make the file look almost complete while most pieces are still missing.
The control file contains the real piece bitfield, so it is the accurate
source.  The ``.part`` size is only used as a fallback before the first control
file appears.

The monitor only performs small local reads: it does not touch the network or
the aria2c process, so downloads keep their full speed.
"""

from __future__ import annotations

import contextlib
import glob
import struct
import threading
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.progress import Progress, TaskID

from media_dl.core.models import Format

# Media extensions that can be part of a yt-dlp download.  Used to count a
# finished stream while the next one (video + audio) is still downloading.
_MEDIA_EXTENSIONS = {
    ".mp4",
    ".m4a",
    ".webm",
    ".mkv",
    ".mp3",
    ".opus",
    ".ogg",
    ".flac",
    ".wav",
    ".ts",
    ".m4v",
    ".mov",
}


def _format_size(fmt: Format) -> int | None:
    """Return the known or estimated size of a format."""
    return fmt.filesize or fmt.filesize_approx


def downloaded_total_from_info(info: dict[str, Any]) -> int | None:
    """Total bytes yt-dlp selected for this download.

    ``extract_info(download=False)`` returns the already selected format(s),
    so this is exact (or the extractor's own estimate), not a guess based on
    every format available for the video.
    """
    requested = info.get("requested_formats") or []
    total = sum(
        (fmt.get("filesize") or fmt.get("filesize_approx") or 0)
        for fmt in requested
        if isinstance(fmt, dict)
    )
    if total:
        return int(total)
    size = info.get("filesize") or info.get("filesize_approx")
    return int(size) if size else None


def estimate_download_size(
    formats: Iterable[Format],
    media_type: str = "video",
    selector: str = "",
) -> int | None:
    """Estimate the bytes that yt-dlp will download for a selector.

    This is intentionally an estimate: it is only used as the total of the
    progress bar.  When no reliable value is available the caller shows an
    indeterminate bar instead of inventing a percentage.
    """
    formats = list(formats)
    if not formats:
        return None

    if media_type == "audio":
        audio = [f for f in formats if f.is_audio]
        if not audio:
            return None
        best = max(audio, key=lambda f: (f.abr or 0, f.tbr or 0, _format_size(f) or 0))
        return _format_size(best)

    # Playlists may still use "bestvideo+bestaudio": sum both streams.
    if "bestvideo" in selector and "bestaudio" in selector:
        video = [f for f in formats if f.is_video and not f.is_audio]
        audio = [f for f in formats if f.is_audio]
        video_size = (
            _format_size(
                max(video, key=lambda f: (f.height or 0, f.tbr or 0, _format_size(f) or 0))
            )
            if video
            else None
        )
        audio_size = (
            _format_size(max(audio, key=lambda f: (f.abr or 0, f.tbr or 0, _format_size(f) or 0)))
            if audio
            else None
        )
        if video_size or audio_size:
            return (video_size or 0) + (audio_size or 0)
        return None

    # The current selectors ask for a single combined format ("best...").
    combined = [f for f in formats if f.is_video and f.acodec not in (None, "none")]

    wanted_height: int | None = None
    marker = "height<="
    if marker in selector:
        try:
            wanted_height = int(selector.split(marker, 1)[1].split("]", 1)[0])
        except (ValueError, IndexError):
            wanted_height = None

    if wanted_height is not None:
        combined = [f for f in combined if (f.height or 0) <= wanted_height]

    # Prefer https: the extractor skips dash/hls on YouTube and the direct
    # https format is the one yt-dlp will actually download.
    https = [f for f in combined if f.protocol == "https"]
    pool = https or combined
    if not pool:
        return None

    best = max(pool, key=lambda f: (f.height or 0, f.tbr or 0, _format_size(f) or 0))
    return _format_size(best)


class ProgressHook:
    """Progress hook for yt-dlp that integrates with Rich Progress."""

    def __init__(
        self,
        progress: Progress,
        task_id: TaskID,
        console: Console | None = None,
    ):
        self.progress = progress
        self.task_id = task_id
        self.console = console
        self._last_downloaded = 0

    def __call__(self, d: dict[str, Any]) -> None:
        """Handle progress updates from yt-dlp."""
        try:
            if d["status"] == "downloading":
                self._handle_downloading(d)
            elif d["status"] == "finished":
                self._handle_finished(d)
            elif d["status"] == "error":
                self._handle_error(d)
        except Exception:
            # Silently ignore progress errors
            pass

    def _handle_downloading(self, d: dict[str, Any]) -> None:
        """Handle downloading progress."""
        total = d.get("total_bytes") or d.get("total_bytes_estimate")
        downloaded = d.get("downloaded_bytes", 0)

        if total:
            self.progress.update(self.task_id, total=total, completed=downloaded)
        else:
            # Indeterminate progress
            self.progress.update(self.task_id, completed=downloaded)

        self._last_downloaded = downloaded

    def _handle_finished(self, d: dict[str, Any]) -> None:
        """Handle download finished."""
        total = d.get("total_bytes") or d.get("total_bytes_estimate") or self._last_downloaded
        if total:
            self.progress.update(self.task_id, completed=total, total=total)

    def _handle_error(self, d: dict[str, Any]) -> None:
        """Handle download error."""
        error = d.get("error", "Unknown error")
        if self.console:
            self.console.print(f"[red]Download error: {error}[/red]")


_ARIA2_MAX_INFO_HASH = 20
_ARIA2_MAX_IN_FLIGHT = 4096
_ARIA2_MAX_SUB_BITFIELD = 1 << 20


def _count_bits(data: bytes, limit: int | None = None) -> int:
    """Count set bits, optionally ignoring padding past ``limit`` bits."""
    if limit is None:
        return sum(byte.bit_count() for byte in data)
    full_bytes, remaining = divmod(limit, 8)
    count = sum(byte.bit_count() for byte in data[:full_bytes])
    if remaining and len(data) > full_bytes:
        # Only the high ``remaining`` bits of this byte are meaningful.
        count += (data[full_bytes] >> (8 - remaining)).bit_count()
    return count


def _parse_aria2_control(data: bytes) -> tuple[int, int] | None:
    """Return ``(completed_bytes, total_bytes)`` from an aria2 control file.

    aria2 saves its progress in ``<download>.aria2``.  The format (version 1,
    network byte order) is defined in aria2's ``DefaultBtProgressInfoFile.cc``:

    * 2 bytes version, 4 bytes extension
    * 4 bytes info-hash length + info hash (BitTorrent only)
    * 4 bytes piece length, 8 bytes total length, 8 bytes upload length
    * 4 bytes bitfield length + one bit per completed piece
    * 4 bytes number of in-flight pieces; for each one: 4-byte index,
      4-byte length, 4-byte partial-bitfield length, partial bitfield

    The in-flight partial bitfield is what makes this better than the ``.part``
    size: it counts blocks actually received, even when aria2c writes pieces
    out of order.
    """
    if len(data) < 34:
        return None
    try:
        version, _extension = struct.unpack_from(">HI", data, 0)
        if version != 1:
            # Version 0 used host byte order and is ancient; fall back to the
            # .part size rather than risk showing nonsense.
            return None

        pos = 6
        (info_hash_length,) = struct.unpack_from(">I", data, pos)
        pos += 4
        if info_hash_length > _ARIA2_MAX_INFO_HASH:
            return None
        if pos + info_hash_length > len(data):
            return None
        pos += info_hash_length

        piece_length, total_length, _upload_length = struct.unpack_from(
            ">IQQ", data, pos
        )
        pos += 20
        if piece_length <= 0 or total_length <= 0:
            return None

        (bitfield_length,) = struct.unpack_from(">I", data, pos)
        pos += 4
        num_pieces = (total_length + piece_length - 1) // piece_length
        if bitfield_length != (num_pieces + 7) // 8:
            return None
        if pos + bitfield_length > len(data):
            return None
        bitfield = data[pos : pos + bitfield_length]
        pos += bitfield_length

        completed = 0
        for index in range(num_pieces):
            if bitfield[index // 8] & (0x80 >> (index % 8)):
                completed += min(piece_length, total_length - index * piece_length)

        if pos + 4 <= len(data):
            (num_in_flight,) = struct.unpack_from(">I", data, pos)
            pos += 4
            if num_in_flight > _ARIA2_MAX_IN_FLIGHT:
                return None
            for _ in range(num_in_flight):
                if pos + 12 > len(data):
                    break
                index, length, sub_length = struct.unpack_from(">III", data, pos)
                pos += 12
                if (
                    index >= num_pieces
                    or length <= 0
                    or sub_length <= 0
                    or sub_length > _ARIA2_MAX_SUB_BITFIELD
                ):
                    continue
                if pos + sub_length > len(data):
                    break
                sub_bitfield = data[pos : pos + sub_length]
                pos += sub_length
                piece_bytes = min(
                    piece_length,
                    length,
                    total_length - index * piece_length,
                )
                if piece_bytes <= 0:
                    continue
                done_bits = _count_bits(sub_bitfield)
                completed += piece_bytes * done_bits // (sub_length * 8)

        return min(int(completed), int(total_length)), int(total_length)
    except (IndexError, struct.error, ValueError):
        return None


class PartialFileMonitor:
    """Show real progress for external downloaders (aria2c).

    yt-dlp's ``ExternalFD`` only calls ``progress_hooks`` when the external
    process exits.  While it runs, aria2c saves a control file with the real
    piece bitfield next to the ``.part`` file.  Polling that file gives exact
    progress without changing any download option.
    """

    def __init__(
        self,
        progress: Progress,
        task_id: TaskID,
        outtmpl: str | dict[str, str],
        expected_total: int | None = None,
        interval: float = 0.25,
    ):
        self.progress = progress
        self.task_id = task_id
        self.expected_total = expected_total if expected_total and expected_total > 0 else None
        self.interval = interval
        self._pattern = self._build_pattern(outtmpl)
        self._control_patterns = self._build_control_patterns(self._pattern)
        self._last_completed = 0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    @staticmethod
    def _build_pattern(outtmpl: str | dict[str, str]) -> str:
        """Turn a yt-dlp output template into a glob for its partial files."""
        # YoutubeDL normalizes ``outtmpl`` from a string to
        # ``{"default": "..."}`` in-place.  Accept both forms so the monitor
        # works whether it is created before or after that normalization.
        if isinstance(outtmpl, dict):
            outtmpl = outtmpl.get("default") or next(iter(outtmpl.values()), "")
        outtmpl = str(outtmpl)
        prefix = outtmpl.split("%(ext)s", 1)[0] if "%(ext)s" in outtmpl else outtmpl
        return glob.escape(prefix) + "*.part"

    @staticmethod
    def _build_control_patterns(part_pattern: str) -> tuple[str, ...]:
        """Globs for aria2's control file next to a ``.part`` file.

        yt-dlp normally writes ``name.mp4.part`` and aria2 appends ``.aria2``.
        A plain aria2c invocation may write ``name.mp4.aria2`` directly, so
        consider both forms.
        """
        base = part_pattern[: -len("*.part")]
        return (base + "*.part.aria2", base + "*.aria2")

    def _control_file(self) -> Path | None:
        """Newest aria2 control file for this download, if any."""
        candidates: list[Path] = []
        for pattern in self._control_patterns:
            try:
                candidates.extend(
                    Path(pattern).parent.glob(Path(pattern).name)
                )
            except OSError:
                continue
        if not candidates:
            return None
        try:
            return max(candidates, key=lambda path: path.stat().st_mtime)
        except OSError:
            return candidates[-1]

    def _control_progress(self) -> tuple[int, int] | None:
        """Read the control file and return its completed/total bytes."""
        path = self._control_file()
        if path is None:
            return None
        try:
            data = path.read_bytes()
        except OSError:
            return None
        progress = _parse_aria2_control(data)
        if progress is None:
            return None
        completed, total = progress
        if self.expected_total:
            # yt-dlp's size and aria2's size can differ by a few KB (merged
            # streams, container overhead).  Reject a control file that is
            # clearly from another download.
            tolerance = max(1024, int(self.expected_total * 0.01))
            if abs(total - self.expected_total) > tolerance:
                return None
        return completed, total

    def _downloaded_bytes(self) -> int:
        """Bytes downloaded so far, including streams that already finished."""
        control = self._control_progress()
        total = 0
        part_names: set[str] = set()

        if control is not None:
            # Exact block count from aria2's bitfield.  Ignore the .part size:
            # out-of-order writes make it jump to nearly 100% immediately.
            total += control[0]
            control_file = self._control_file()
            if control_file is not None:
                name = control_file.name.removesuffix(".aria2")
                part_names.add(name)
                part_names.add(name.removesuffix(".part"))
        else:
            # No control file yet (aria2 is still connecting, or this is a
            # native download).  The .part size is a rough fallback.
            try:
                for path in Path(self._pattern).parent.glob(Path(self._pattern).name):
                    try:
                        total += path.stat().st_size
                        part_names.add(path.name)
                        part_names.add(path.name.removesuffix(".part"))
                    except OSError:
                        continue
            except OSError:
                pass

        # When yt-dlp downloads video and audio separately, the first stream
        # is renamed from .part to its final extension before the second one
        # starts.  Count it so the bar does not go backwards.  Skip a final
        # file that is the target of the current .part (it may be a leftover
        # from a previous --force run).
        prefix = self._pattern[: -len("*.part")]
        try:
            for path in Path(prefix).parent.glob(Path(prefix).name + "*"):
                if path.suffix.lower() not in _MEDIA_EXTENSIONS:
                    continue
                if path.name in part_names:
                    continue
                try:
                    total += path.stat().st_size
                except OSError:
                    continue
        except OSError:
            pass

        return total

    def _update(self) -> None:
        downloaded = self._downloaded_bytes()
        if downloaded <= 0:
            return

        if self.expected_total:
            # Keep 1% for yt-dlp to rename/merge the file.  Monotonic so a
            # control-file rotation between video and audio cannot move the
            # bar backwards.
            completed = min(downloaded, int(self.expected_total * 0.99))
            completed = max(completed, self._last_completed)
            self._last_completed = completed
            self.progress.update(
                self.task_id,
                completed=completed,
                total=self.expected_total,
            )
        else:
            completed = max(downloaded, self._last_completed)
            self._last_completed = completed
            self.progress.update(self.task_id, completed=completed)

    def _run(self) -> None:
        while not self._stop.wait(self.interval):
            # A progress failure must never break a download.
            with contextlib.suppress(Exception):
                self._update()

    def start(self) -> PartialFileMonitor:
        if self._thread is None:
            self._thread = threading.Thread(
                target=self._run,
                name="media-dl-progress",
                daemon=True,
            )
            self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=1.0)

    def complete(self) -> None:
        """Stop polling and mark the task as finished."""
        self.stop()
        if self.expected_total:
            self.progress.update(
                self.task_id,
                completed=self.expected_total,
                total=self.expected_total,
            )
        else:
            downloaded = self._downloaded_bytes()
            if downloaded:
                self.progress.update(self.task_id, completed=downloaded, total=downloaded)

    def __enter__(self) -> PartialFileMonitor:
        return self.start()

    def __exit__(self, *exc_info: object) -> None:
        self.stop()


class MultiProgressHook:
    """Progress hook for multiple concurrent downloads."""

    def __init__(
        self,
        progress: Progress,
        console: Console | None = None,
    ):
        self.progress = progress
        self.console = console
        self._hooks: dict[str, ProgressHook] = {}

    def get_hook(self, url: str) -> ProgressHook:
        """Get or create hook for URL."""
        if url not in self._hooks:
            task_id = self.progress.add_task(f"[cyan]{url[:50]}...", total=None)
            self._hooks[url] = ProgressHook(self.progress, task_id, self.console)
        return self._hooks[url]

    def __call__(self, d: dict[str, Any]) -> None:
        """Handle progress - dispatches to appropriate hook."""
        # This would need URL context from yt-dlp
        # For now, we use single hook per download


def create_progress_hook(
    progress: Progress,
    task_id: TaskID,
    console: Console | None = None,
) -> Callable[[dict[str, Any]], None]:
    """Factory function to create a progress hook."""
    hook = ProgressHook(progress, task_id, console)
    return hook


def create_partial_monitor(
    progress: Progress,
    task_id: TaskID,
    outtmpl: str | dict[str, str],
    expected_total: int | None = None,
) -> PartialFileMonitor:
    """Create a monitor for an external-downloader download."""
    return PartialFileMonitor(progress, task_id, outtmpl, expected_total)


# Backwards-compatible alias used by older imports.
Monitor = PartialFileMonitor
