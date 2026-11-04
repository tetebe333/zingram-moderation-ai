
import json
import subprocess
from pathlib import Path


class ModerationError(Exception):
    pass


def moderate_images(image_paths: list[str | Path]) -> list[dict]:
    """Scan multiple images in one operation."""

    if not image_paths:
        return []

    images = [Path(path).resolve() for path in image_paths]

    for image in images:
        if not image.is_file():
            raise FileNotFoundError(f"Image not found: {image}")

    result = subprocess.run(
        ["openmoderate", "scan", "--json", *map(str, images)],
        capture_output=True,
        text=True,
        timeout=300
    )

    if result.returncode != 0:
        raise ModerationError(
            result.stderr.strip() or "Image moderation failed."
        )

    results = []

    for line in result.stdout.splitlines():
        line = line.strip()

        if line.startswith("{"):
            results.append(json.loads(line))

    if len(results) != len(images):
        raise ModerationError("Some images did not return moderation results.")

    return results


def moderate_image(image_path: str | Path) -> dict:
    """Scan one image and return its moderation result."""

    return moderate_images([image_path])[0]


def is_image_safe(image_path: str | Path) -> bool:
    """Return True when no moderation violations are detected."""

    return moderate_image(image_path).get("is_safe", False)


def are_images_safe(image_paths: list[str | Path]) -> bool:
    """Return True only when every image passes moderation."""

    return all(result.get("is_safe", False) for result in moderate_images(image_paths))
