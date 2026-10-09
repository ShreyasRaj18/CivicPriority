
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent

INPUT_FILE = ROOT / "data" / "processed_infrastructure_issues.csv"
OUTPUT_FILE = ROOT / "data" / "ranked_real_issues.csv"

WEIGHTS = {
    "recurrence_signal": 0.35,
    "status_signal": 0.25,
    "age_signal": 0.20,
    "ward_concentration": 0.20,
}

STATUS_SCORES = {
    "open": 100,
    "re-opened": 90,
    "on-the-job": 75,
    "resolved": 25,
    "closed": 15,
    "rejected": 0,
}


def load_processed_data():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Processed dataset not found: {INPUT_FILE}\n"
            "Run 'python -m src.real_data' first."
        )

    df = pd.read_csv(
        INPUT_FILE,
        encoding="utf-8-sig",
        low_memory=False,
    )

    required = [
        "record_id",
        "created_at",
        "ward_id",
        "category_title",
        "sub_category_title",
        "complaint_status_title",
        "recurrence_count",
    ]

    missing = [col for col in required if col not in df.columns]

    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    df = df.copy()

    df["created_at"] = pd.to_datetime(
        df["created_at"],
        errors="coerce",
    )

    df["recurrence_count"] = pd.to_numeric(
        df["recurrence_count"],
        errors="coerce",
    )

    df["ward_id"] = df["ward_id"].astype("string").str.strip()

    df = df.dropna(
        subset=[
            "record_id",
            "created_at",
            "ward_id",
            "recurrence_count",
        ]
    ).copy()

    df = df[
        df["ward_id"].ne("")
        & df["recurrence_count"].ge(0)
    ].copy()

    if df.empty:
        raise ValueError("No valid records available for scoring.")

    return df


def calculate_real_priority(df):
    df = df.copy()

    df["recurrence_signal"] = (
        df.groupby("category_title", dropna=False)["recurrence_count"]
        .rank(method="average", pct=True)
        .mul(100)
    )

    status = (
        df["complaint_status_title"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.lower()
    )

    df["status_signal"] = status.map(STATUS_SCORES).fillna(0)

    reference_date = df["created_at"].max()

    df["age_days_at_dataset_end"] = (
        reference_date - df["created_at"]
    ).dt.total_seconds().div(86400).clip(lower=0)

    active_statuses = {"open", "re-opened", "on-the-job"}
    active_mask = status.isin(active_statuses)

    df["age_signal"] = 0.0

    if active_mask.any():
        df.loc[active_mask, "age_signal"] = (
            df.loc[active_mask, "age_days_at_dataset_end"]
            .rank(method="average", pct=True)
            .mul(100)
        )

    df["ward_complaint_count"] = (
        df.groupby("ward_id")["record_id"].transform("count")
    )

    df["ward_concentration"] = (
        df["ward_complaint_count"]
        .rank(method="average", pct=True)
        .mul(100)
    )

    for factor, weight in WEIGHTS.items():
        df[f"{factor}_contribution"] = df[factor] * weight

    contribution_columns = [
        f"{factor}_contribution" for factor in WEIGHTS
    ]

    df["priority_score"] = (
        df[contribution_columns].sum(axis=1)
    ).round(2)

    df = df.sort_values(
        ["priority_score", "created_at"],
        ascending=[False, True],
    ).reset_index(drop=True)

    df["priority_rank"] = range(1, len(df) + 1)

    def explain_priority(row):
        return (
            f"Recurrence: {row['recurrence_signal']:.1f}/100; "
            f"historical status: {row['status_signal']:.0f}/100; "
            f"age: {row['age_signal']:.1f}/100; "
            f"ward concentration: "
            f"{row['ward_concentration']:.1f}/100."
        )

    df["priority_explanation"] = df.apply(
        explain_priority,
        axis=1,
    )

    df["scoring_reference_date"] = reference_date
    df["scoring_model"] = "Historical rule-based review priority"

    return df


def main():
    issues = load_processed_data()
    ranked = calculate_real_priority(issues)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    ranked.to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    print("=== CIVICPRIORITY: HISTORICAL REVIEW PRIORITIES ===")
    print(f"Records scored: {len(ranked):,}")
    print(f"Reference date: {ranked['created_at'].max()}")
    print(f"Output file: {OUTPUT_FILE}")
    print("Model: Explainable rule-based scoring")
    print(f"Weights total: {sum(WEIGHTS.values()) * 100:.0f}%")

    print("\n--- TOP 10 RECORDS FOR REVIEW ---")

    display_columns = [
        "priority_rank",
        "record_id",
        "category_title",
        "sub_category_title",
        "complaint_status_title",
        "priority_score",
        "priority_explanation",
    ]

    print(
        ranked[display_columns]
        .head(10)
        .to_string(index=False)
    )

    print("\n--- SCORE SUMMARY ---")
    print(ranked["priority_score"].describe().round(2).to_string())

    print("\n--- TOP 100 CATEGORY DISTRIBUTION ---")
    print(
        ranked.head(100)["category_title"]
        .value_counts(dropna=False)
        .to_string()
    )


if __name__ == "__main__":
    main()
