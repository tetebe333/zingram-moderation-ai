
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.openapi.utils import get_openapi
from PIL import Image, ImageOps
from pillow_heif import register_heif_opener
from fastapi.middleware.cors import CORSMiddleware

from . import moderate_images, moderate_video, ModerationError

register_heif_opener()

app = FastAPI(title="Zingram Moderation API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "https://zingram.vercel.app"
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(
        title=app.title,
        version="0.1.0",
        routes=app.routes,
        openapi_version="3.0.3",
    )

    schemas = schema.get("components", {}).get("schemas", {})

    batch_schema = schemas.get(
        "Body_moderate_batch_moderate_batch_post", {}
    )

    files_field = batch_schema.get("properties", {}).get("files")

    if files_field:
        files_field.clear()
        files_field.update({
            "type": "array",
            "items": {
                "type": "string",
                "format": "binary",
            },
            "title": "Files",
            "description": "Select multiple photos (up to 10), or one video.",
        })

    single_schema = schemas.get(
        "Body_moderate_moderate_post", {}
    )

    single_field = single_schema.get("properties", {}).get("file")

    if single_field:
        single_field["type"] = "string"
        single_field["format"] = "binary"

    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = custom_openapi


IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp",
    ".heic", ".heif", ".gif", ".bmp",
    ".tif", ".tiff",
}

VIDEO_EXTENSIONS = {
    ".mp4", ".mov", ".webm", ".mkv",
    ".avi", ".m4v", ".3gp",
}

ALL_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS

MAX_FILE_SIZE = 100 * 1024 * 1024
MAX_PHOTOS = 10

BLOCKED_CATEGORIES = {"sexual_activity", "gore"}

CATEGORY_MESSAGES = {
    "sexual_activity": "Explicit sexual content is not allowed on Zingram.",
    "gore": "Graphic violence, mutilation and extreme gore are not allowed on Zingram.",
}


def get_category(violation):
    if isinstance(violation, dict):
        return violation.get("name")
    return violation


def evaluate_image(results):
    detected = set()

    for result in results:
        if "error" in result:
            raise ModerationError(result["error"])

        for violation in result.get("violations", []):
            category = get_category(violation)
            if category:
                detected.add(category)

    return detected, detected & BLOCKED_CATEGORIES


def evaluate_animated_image(results):
    detected = set()
    category_frames = {}

    for result in results:
        if "error" in result:
            raise ModerationError(result["error"])

        frame_categories = set()

        for violation in result.get("violations", []):
            category = get_category(violation)
            if category:
                detected.add(category)
                frame_categories.add(category)

        for category in frame_categories:
            category_frames[category] = (
                category_frames.get(category, 0) + 1
            )

    total_frames = len(results)
    blocked = set()

    if total_frames:
        for category in BLOCKED_CATEGORIES:
            if category_frames.get(category, 0) / total_frames > 0.50:
                blocked.add(category)

    return detected, blocked


def evaluate_video(results):
    detected = set()
    category_frames = {}

    total_frames = sum(
        result.get("frames_analyzed", 0)
        for result in results
    )

    for result in results:
        if "error" in result:
            raise ModerationError(result["error"])

        for violation in result.get("violations", []):
            category = get_category(violation)
            if category:
                detected.add(category)

        segments_by_category = {}

        for segment in result.get("segments", []):
            category = segment.get("name")

            if not category:
                continue

            detected.add(category)

            start = int(segment.get("start", 0))
            end = int(segment.get("end", start))

            segments_by_category.setdefault(category, []).append(
                (start, end)
            )

        for category, intervals in segments_by_category.items():
            intervals.sort()
            merged = []

            for start, end in intervals:
                if merged and start <= merged[-1][1]:
                    merged[-1] = (
                        merged[-1][0],
                        max(merged[-1][1], end),
                    )
                else:
                    merged.append((start, end))

            category_frames[category] = (
                category_frames.get(category, 0)
                + sum(end - start + 1 for start, end in merged)
            )

    blocked = set()

    if total_frames:
        for category in BLOCKED_CATEGORIES:
            percentage = (
                category_frames.get(category, 0) / total_frames
            )

            if percentage > 0.50:
                blocked.add(category)

    return detected, blocked


def scan_image(path: Path):
    with Image.open(path) as image:
        frame_count = getattr(image, "n_frames", 1)

        if frame_count > 1:
            frame_count_to_scan = min(frame_count, 30)

            indices = sorted({
                round(i * (frame_count - 1) / (frame_count_to_scan - 1))
                if frame_count_to_scan > 1 else 0
                for i in range(frame_count_to_scan)
            })
        else:
            indices = [0]

        with tempfile.TemporaryDirectory() as directory:
            frame_paths = []

            for index in indices:
                image.seek(index)
                frame = ImageOps.exif_transpose(image.copy())
                frame = frame.convert("RGB")

                frame_path = Path(directory) / f"frame_{index}.png"
                frame.save(frame_path, format="PNG")
                frame_paths.append(frame_path)

            results = moderate_images(frame_paths)

    if frame_count > 1:
        return evaluate_animated_image(results)

    return evaluate_image(results)


async def moderate_uploaded_file(file: UploadFile):
    suffix = Path(file.filename or "").suffix.lower()
    temp_path = None

    try:
        if suffix not in ALL_EXTENSIONS:
            raise ValueError(f"Unsupported file format: {suffix}")

        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=suffix,
        ) as temp:
            temp_path = Path(temp.name)
            total = 0

            while chunk := await file.read(1024 * 1024):
                total += len(chunk)

                if total > MAX_FILE_SIZE:
                    raise ValueError("File exceeds 100 MB.")

                temp.write(chunk)

        if total == 0:
            raise ValueError("Uploaded file is empty.")

        if suffix in IMAGE_EXTENSIONS:
            detected, blocked = scan_image(temp_path)
        else:
            results = moderate_video(temp_path)
            detected, blocked = evaluate_video(results)

        blocked = sorted(blocked)

        return {
            "filename": file.filename,
            "safe": not blocked,
            "status": "safe" if not blocked else "rejected",
            "detected_categories": sorted(detected),
            "reasons": [
                CATEGORY_MESSAGES[category]
                for category in blocked
            ],
        }

    except Exception as error:
        return {
            "filename": file.filename,
            "safe": False,
            "status": "error",
            "detected_categories": [],
            "reasons": [],
            "error": str(error),
        }

    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink()

        await file.close()


def validate_post_files(files):
    if not files:
        raise HTTPException(400, "No files uploaded.")

    if len(files) > MAX_PHOTOS:
        raise HTTPException(
            400,
            "A post can contain a maximum of 10 photos."
        )

    extensions = [
        Path(file.filename or "").suffix.lower()
        for file in files
    ]

    if any(ext not in ALL_EXTENSIONS for ext in extensions):
        raise HTTPException(
            415,
            "One or more files have unsupported formats."
        )

    image_count = sum(ext in IMAGE_EXTENSIONS for ext in extensions)
    video_count = sum(ext in VIDEO_EXTENSIONS for ext in extensions)

    if video_count and (video_count != 1 or image_count > 0):
        raise HTTPException(
            400,
            "A post can contain either one video or up to 10 photos, not both."
        )


@app.get("/health")
def health():
    return {
        "status": "online",
        "service": "zingram-moderation",
    }


@app.post("/moderate")
async def moderate(file: UploadFile = File(...)):
    result = await moderate_uploaded_file(file)

    if result["status"] == "error":
        raise HTTPException(422, result["error"])

    blocked = not result["safe"]

    return {
        "safe": result["safe"],
        "status": result["status"],
        "message": (
            "File passed moderation."
            if not blocked
            else "This file contains content that isn't allowed on Zingram."
        ),
        "detected_categories": result["detected_categories"],
        "reasons": result["reasons"],
    }



@app.post("/moderate/batch")
async def moderate_batch(
    files: list[UploadFile] = File(
        ...,
        description="Select multiple photos (up to 10), or one video."
    )
):
    validate_post_files(files)

    results = []

    for index, file in enumerate(files, start=1):
        result = await moderate_uploaded_file(file)

        result["file_number"] = index
        results.append(result)

    all_safe = all(result["safe"] for result in results)
    has_error = any(result["status"] == "error" for result in results)

    rejected_files = []

    for result in results:
        if not result["safe"]:
            if result["status"] == "error":
                reason = result.get("error", "The file could not be checked.")
            else:
                reason = " ".join(result.get("reasons", []))

            rejected_files.append({
                "file_number": result["file_number"],
                "filename": result["filename"],
                "message": (
                    f"File {result['file_number']} "
                    f"({result['filename']}) was not approved: {reason}"
                ),
            })

    return {
        "safe": all_safe,
        "status": (
            "safe" if all_safe
            else "error" if has_error
            else "rejected"
        ),
        "total_files": len(results),
        "message": (
            "All files passed moderation."
            if all_safe
            else "One or more files could not be approved."
        ),
        "files": results,
        "rejected_files": rejected_files,
    }
