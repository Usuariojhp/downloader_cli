"""Unified progress hooks for yt-dlp with Rich."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from rich.console import Console
from rich.progress import Progress, TaskID


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

        # Update speed display
        speed = d.get("speed")
        if speed:
            self.progress.update(self.task_id, speed=speed)

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
