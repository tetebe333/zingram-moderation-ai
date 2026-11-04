
import json
import subprocess
from pathlib import Path

from .moderation import ModerationError


def moderate_video(
    video_path: str | Path,
    fps: float = 1.0,
    max_duration: float | None = None,
    min_frames: int = 1,
) -> list[dict]:
    """Scan a video by sampling frames and return moderation results."""

    video = Path(video_path).resolve()

    if not video.is_file():
        raise FileNotFoundError(f"Video not found: {video}")

    if fps <= 0 or min_frames < 1:
        raise ValueError("FPS must be positive and min_frames at least 1.")

    command = [
        "openmoderate", "scan", "--json",
        "--fps", str(fps),
        "--min-frames", str(min_frames),
    ]

    if max_duration is not None:
        if max_duration <= 0:
            raise ValueError("max_duration must be positive.")
        command.extend(["--max-duration", str(max_duration)])

    command.append(str(video))

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=1800,
    )

    if result.returncode != 0:
        raise ModerationError(
            result.stderr.strip() or "Video moderation failed."
        )

    results = []

    for line in result.stdout.splitlines():
        line = line.strip()

        if line.startswith("{"):
            results.append(json.loads(line))

    if not results:
        raise ModerationError("No video moderation results were returned.")

    return results

def is_video_safe(video_path: str | Path) -> bool:
    """Return True only when every scanned video frame is safe."""

    results = moderate_video(video_path)

    return all(
        result.get("is_safe", False)
        for result in results
    )
