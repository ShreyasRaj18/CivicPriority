
import pandas as pd

NUMERIC_LIMITS = {
    "severity": (1, 5),
    "population_affected": (0, None),
    "recurrence": (0, None),
    "duration_days": (0, None),
    "geographic_importance": (1, 5),
    "estimated_cost": (0, None),
    "crew_required": (1, None),
    "equipment_required": (0, None)
}


def validate_issues(df):
    """Validate required fields and numeric values."""
    df = df.copy()
    errors = []

    if df["issue_id"].isna().any():
        errors.append("Some issues have missing IDs.")

    if df["issue_id"].astype(str).duplicated().any():
        errors.append("Duplicate issue IDs detected.")

    for col, (minimum, maximum) in NUMERIC_LIMITS.items():
        df[col] = pd.to_numeric(df[col], errors="coerce")

        if df[col].isna().any():
            errors.append(
                f"{col} contains missing or non-numeric values."
            )
            continue

        if (df[col] < minimum).any():
            errors.append(f"{col} contains values below {minimum}.")

        if maximum is not None and (df[col] > maximum).any():
            errors.append(f"{col} contains values above {maximum}.")

    if df["issue_type"].isna().any() or df["location"].isna().any():
        errors.append("Issue type or location is missing.")

    if errors:
        raise ValueError("\n".join(errors))

    return df


def normalize_issues(df):
    """Normalize factors using fixed 0-100 scales."""
    df = df.copy()

    # Severity and geographic importance: scale 1-5 to 0-100.
    df["severity_score"] = (
        (df["severity"] - 1) / 4 * 100
    ).clip(0, 100)

    df["geographic_score"] = (
        (df["geographic_importance"] - 1) / 4 * 100
    ).clip(0, 100)

    # Provisional thresholds for the prototype.
    df["population_score"] = (
        df["population_affected"] / 2000 * 100
    ).clip(0, 100)

    df["recurrence_score"] = (
        df["recurrence"] / 5 * 100
    ).clip(0, 100)

    df["duration_score"] = (
        df["duration_days"] / 30 * 100
    ).clip(0, 100)

    return df


def process_issues(df):
    """Validate and normalize infrastructure issue records."""
    validated = validate_issues(df)
    processed = normalize_issues(validated)
    return processed
