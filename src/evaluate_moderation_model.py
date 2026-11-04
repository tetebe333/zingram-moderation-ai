import csv
from pathlib import Path

import torch
from PIL import Image, UnidentifiedImageError
from transformers import AutoImageProcessor, AutoModelForImageClassification


MODEL_NAME = "Falconsai/nsfw_image_detection"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
IMAGE_DIR = PROJECT_ROOT / "data" / "raw"
OUTPUT_CSV = PROJECT_ROOT / "data" / "processed" / "model_predictions.csv"

SUPPORTED_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".bmp",
}

DEVICE = torch.device("cpu")


def main():
    images = sorted(
        path
        for path in IMAGE_DIR.iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    )

    if not images:
        print(f"No supported images found in {IMAGE_DIR}")
        return

    print(f"Found {len(images)} image(s).")
    print("Loading the model...")

    processor = AutoImageProcessor.from_pretrained(MODEL_NAME)
    model = AutoModelForImageClassification.from_pretrained(MODEL_NAME)
    model.to(DEVICE)
    model.eval()

    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    results = []

    for image_path in images:
        try:
            with Image.open(image_path) as image:
                image_format = image.format or "Unknown"
                image = image.convert("RGB")
                inputs = processor(images=image, return_tensors="pt")

            inputs = {
                key: value.to(DEVICE)
                for key, value in inputs.items()
            }

            with torch.inference_mode():
                logits = model(**inputs).logits
                probabilities = torch.softmax(logits, dim=-1)[0]

            scores = {
                model.config.id2label[index]: float(probability.item())
                for index, probability in enumerate(probabilities)
            }

            predicted_label = max(scores, key=scores.get)

            result = {
                "filename": image_path.name,
                "image_format": image_format,
                "predicted_label": predicted_label,
                "normal_score": scores.get("normal", ""),
                "nsfw_score": scores.get("nsfw", ""),
                "status": "prediction_only",
            }
            results.append(result)

            print(f"\nImage: {image_path.name}")
            print(f"  Actual format: {image_format}")
            print(f"  Normal score: {scores.get('normal', 0):.4f}")
            print(f"  NSFW score: {scores.get('nsfw', 0):.4f}")
            print(f"  Predicted class: {predicted_label}")

        except (UnidentifiedImageError, OSError) as error:
            print(f"\nCould not open {image_path.name}: {error}")

    if results:
        with OUTPUT_CSV.open(
            "w", encoding="utf-8", newline=""
        ) as file:
            writer = csv.DictWriter(
                file,
                fieldnames=[
                    "filename",
                    "image_format",
                    "predicted_label",
                    "normal_score",
                    "nsfw_score",
                    "status",
                ],
            )
            writer.writeheader()
            writer.writerows(results)

        print(f"\nSaved predictions to: {OUTPUT_CSV.relative_to(PROJECT_ROOT)}")

    print("\nThese are experimental predictions, not safety decisions.")
    print("No image has been approved or rejected by this script.")


if __name__ == "__main__":
    main()