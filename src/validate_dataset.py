import csv
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = PROJECT_ROOT / "data" / "manifest.csv"

LABEL_COLUMNS = [
    "nudity",
    "sexual_content",
    "suggestive_content",
    "violence",
    "graphic_content",
    "weapons",
    "self_harm",
    "hate_symbols",
]

REQUIRED_COLUMNS = [
    "image_path",
    "split",
    *LABEL_COLUMNS,
    "review_required",
]

VALID_SPLITS = {"train", "validation", "test"}
VALID_VALUES = {"0", "1", ""}


def main():
    if not MANIFEST_PATH.exists():
        raise SystemExit(f"ERROR: Manifest not found: {MANIFEST_PATH}")

    errors = []
    warnings = []
    seen_paths = set()
    split_counts = {split: 0 for split in VALID_SPLITS}

    with MANIFEST_PATH.open(
        "r", encoding="utf-8-sig", newline=""
    ) as file:
        reader = csv.DictReader(file)

        if not reader.fieldnames:
            raise SystemExit("ERROR: Manifest has no header.")

        missing_columns = set(REQUIRED_COLUMNS) - set(reader.fieldnames)

        if missing_columns:
            raise SystemExit(
                "ERROR: Missing columns: "
                + ", ".join(sorted(missing_columns))
            )

        for row_number, row in enumerate(reader, start=2):
            image_path = (row["image_path"] or "").strip()
            split = (row["split"] or "").strip()
            review_required = (
                row["review_required"] or ""
            ).strip()

            if not image_path:
                errors.append(f"Row {row_number}: missing image_path.")
            else:
                if image_path in seen_paths:
                    errors.append(
                        f"Row {row_number}: duplicate image path "
                        f"{image_path!r}."
                    )
                seen_paths.add(image_path)

                full_path = PROJECT_ROOT / image_path

                if not full_path.is_file():
                    warnings.append(
                        f"Row {row_number}: image not found: "
                        f"{image_path}"
                    )

            if split not in VALID_SPLITS:
                errors.append(
                    f"Row {row_number}: invalid split {split!r}."
                )
            else:
                split_counts[split] += 1

            for label in LABEL_COLUMNS:
                value = (row[label] or "").strip()

                if value not in VALID_VALUES:
                    errors.append(
                        f"Row {row_number}: {label} must be "
                        "0, 1, or blank."
                    )

            if review_required not in VALID_VALUES:
                errors.append(
                    f"Row {row_number}: review_required must be "
                    "0, 1, or blank."
                )

    print("\nZingram dataset validation")
    print("-" * 32)
    print("Training rows:", split_counts["train"])
    print("Validation rows:", split_counts["validation"])
    print("Test rows:", split_counts["test"])
    print("Unique image paths:", len(seen_paths))
    print("Errors:", len(errors))
    print("Warnings:", len(warnings))

    for warning in warnings[:20]:
        print("WARNING:", warning)

    for error in errors[:20]:
        print("ERROR:", error)

    if len(warnings) > 20:
        print("Additional warnings omitted.")

    if len(errors) > 20:
        print("Additional errors omitted.")

    if errors:
        raise SystemExit("\nValidation FAILED.")

    print("\nValidation PASSED.")
    print("Missing images must be resolved before training.")


if __name__ == "__main__":
    main()