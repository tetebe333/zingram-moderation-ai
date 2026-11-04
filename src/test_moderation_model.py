from pathlib import Path

import torch
from PIL import Image
from transformers import AutoImageProcessor, AutoModelForImageClassification


MODEL_NAME = "Falconsai/nsfw_image_detection"
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Keep inference on the CPU for this first test.
DEVICE = torch.device("cpu")


def main():
    image_input = input(
        "Enter the image path (for example, data/raw/test.jpg): "
    ).strip().strip('"')

    image_path = Path(image_input)

    if not image_path.is_absolute():
        image_path = PROJECT_ROOT / image_path

    if not image_path.is_file():
        print(f"Image not found: {image_path}")
        return

    print("Loading model...")

    processor = AutoImageProcessor.from_pretrained(MODEL_NAME)
    model = AutoModelForImageClassification.from_pretrained(MODEL_NAME)
    model.to(DEVICE)
    model.eval()

    try:
        with Image.open(image_path) as image:
            image = image.convert("RGB")
            inputs = processor(images=image, return_tensors="pt")

        inputs = {key: value.to(DEVICE) for key, value in inputs.items()}

        with torch.inference_mode():
            logits = model(**inputs).logits
            probabilities = torch.softmax(logits, dim=-1)[0]

        print("\nPrediction scores:")
        for index, probability in enumerate(probabilities):
            label = model.config.id2label[index]
            print(f"{label}: {probability.item():.4f}")

        predicted_index = int(probabilities.argmax().item())
        predicted_label = model.config.id2label[predicted_index]

        print(f"\nPredicted class: {predicted_label}")
        print("Research test only — this prediction is not a publishing decision.")

    except Exception as error:
        print(f"Could not process the image: {error}")


if __name__ == "__main__":
    main()