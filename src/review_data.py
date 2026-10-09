
from pathlib import Path
import pandas as pd

from src.real_data import flag_suspicious_categories

ROOT = Path(__file__).resolve().parent.parent
INPUT_FILE = ROOT / "data" / "processed_infrastructure_issues.csv"
REVIEW_FILE = ROOT / "data" / "category_review.csv"
SUMMARY_FILE = ROOT / "data" / "category_review_summary.csv"


def main():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Dataset not found: {INPUT_FILE}")

    df = pd.read_csv(
        INPUT_FILE,
        encoding="utf-8-sig",
        low_memory=False
    )

    required = [
        "record_id",
        "title",
        "category_title",
        "sub_category_title"
    ]

    missing = [column for column in required if column not in df.columns]

    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    reviewed = flag_suspicious_categories(df)

    flagged = reviewed[
        reviewed["needs_category_review"]
    ].copy()

    if flagged.empty:
        summary = pd.DataFrame(
            columns=[
                "category_title",
                "review_reason",
                "records_flagged"
            ]
        )
    else:
        summary = (
            flagged.groupby(
                ["category_title", "review_reason"],
                dropna=False
            )
            .size()
            .reset_index(name="records_flagged")
            .sort_values(
                "records_flagged",
                ascending=False
            )
        )

    REVIEW_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    flagged.to_csv(
        REVIEW_FILE,
        index=False,
        encoding="utf-8-sig"
    )

    summary.to_csv(
        SUMMARY_FILE,
        index=False,
        encoding="utf-8-sig"
    )

    total = len(reviewed)
    flagged_count = len(flagged)
    percentage = flagged_count / total * 100 if total else 0

    print("=== CIVICPRIORITY CATEGORY REVIEW ===")
    print(f"Total records: {total:,}")
    print(f"Flagged for review: {flagged_count:,}")
    print(f"Flagged percentage: {percentage:.2f}%")

    print("\n--- REVIEW COUNTS BY CATEGORY ---")

    if summary.empty:
        print("No records flagged for review.")
    else:
        print(
            summary.groupby(
                "category_title",
                dropna=False
            )["records_flagged"]
            .sum()
            .sort_values(ascending=False)
            .to_string()
        )

    print(f"\nReview file: {REVIEW_FILE}")
    print(f"Summary file: {SUMMARY_FILE}")
    print("\nOriginal records have not been modified or deleted.")


if __name__ == "__main__":
    main()
