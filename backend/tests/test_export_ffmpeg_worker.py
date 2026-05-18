"""Unit tests for the local FFmpeg export worker."""
import os
import shutil
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from export_ffmpeg import ExportSegment, ffmpeg_available, run_ffmpeg_concat  # noqa: E402


@pytest.mark.skipif(not ffmpeg_available(), reason="ffmpeg/ffprobe not installed")
def test_ffmpeg_concat_worker_creates_mp4(tmp_path):
    first = tmp_path / "first.mp4"
    second = tmp_path / "second.mp4"
    output = tmp_path / "final.mp4"
    _make_clip(first, "red")
    _make_clip(second, "blue")

    run_ffmpeg_concat(
        segments=[
            ExportSegment(path=first, segment_id="seg-1"),
            ExportSegment(path=second, segment_id="seg-2"),
        ],
        output_path=output,
        work_dir=tmp_path / "work",
        timeout_seconds=60,
    )

    assert output.exists()
    assert output.stat().st_size > 0


def _make_clip(path, color):
    cmd = [
        shutil.which("ffmpeg") or "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "lavfi",
        "-i",
        f"color=c={color}:s=320x180:d=0.5",
        "-an",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        str(path),
    ]
    subprocess.run(cmd, check=True)
