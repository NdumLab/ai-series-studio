"""Local FFmpeg export worker.

This worker is deliberately narrow for the MVP: it concatenates approved local
MP4 segment assets into one MP4. Voice/music mixing is handled in the next
download/finalization loop after the video-only worker is stable.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional


class FFmpegExportError(RuntimeError):
    pass


@dataclass(frozen=True)
class ExportSegment:
    path: Path
    segment_id: str


def ffmpeg_bin(env: Optional[dict] = None) -> str:
    source = env if env is not None else os.environ
    return (source.get("FFMPEG_BIN") or "ffmpeg").strip() or "ffmpeg"


def ffprobe_bin(env: Optional[dict] = None) -> str:
    source = env if env is not None else os.environ
    return (source.get("FFPROBE_BIN") or "ffprobe").strip() or "ffprobe"


def ffmpeg_available(env: Optional[dict] = None) -> bool:
    return bool(shutil.which(ffmpeg_bin(env)) and shutil.which(ffprobe_bin(env)))


def run_ffmpeg_concat(
    *,
    segments: Iterable[ExportSegment],
    output_path: Path,
    work_dir: Path,
    timeout_seconds: int = 300,
    env: Optional[dict] = None,
) -> None:
    rows = list(segments)
    if not rows:
        raise FFmpegExportError("No approved local video segments to export")
    if not ffmpeg_available(env):
        raise FFmpegExportError("FFmpeg is not installed or not on PATH")
    work_dir.mkdir(parents=True, exist_ok=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    concat_path = work_dir / "concat.txt"
    concat_path.write_text("".join(_concat_line(row.path) for row in rows), encoding="utf-8")
    cmd = [
        ffmpeg_bin(env),
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_path),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    proc = subprocess.run(  # noqa: S603 - command path is configured server-side
        cmd,
        cwd=str(work_dir),
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
        check=False,
    )
    if proc.returncode != 0:
        message = (proc.stderr or proc.stdout or "FFmpeg export failed").strip()
        raise FFmpegExportError(message[:500])
    if not output_path.exists() or output_path.stat().st_size <= 0:
        raise FFmpegExportError("FFmpeg export produced no output")


def _concat_line(path: Path) -> str:
    resolved = path.resolve()
    if not resolved.exists():
        raise FFmpegExportError(f"Missing segment file: {path}")
    safe = str(resolved).replace("'", "'\\''")
    return f"file '{safe}'\n"
