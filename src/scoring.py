
import pandas as pd


URGENCY_WEIGHTS = {
    "severity_score": 0.30,
    "population_score": 0.25,
    "recurrence_score": 0.15,
    "duration_score": 0.10,
    "geographic_score": 0.10,
}

RESOURCE_WEIGHT = 0.10
TOTAL_URGENCY_WEIGHT = sum(URGENCY_WEIGHTS.values())

FACTOR_LABELS = {
    "severity_score": "Severity",
    "population_score": "Population affected",
    "recurrence_score": "Recurrence",
    "duration_score": "Duration",
    "geographic_score": "Geographic importance",
    "resource_requirement_score": "Resource feasibility",
}


def calculate_priority(df, weights=None):
    df = df.copy()

    required = [
        "severity_score",
        "population_score",
        "recurrence_score",
        "duration_score",
        "geographic_score",
        "estimated_cost",
        "crew_required",
        "equipment_required",
    ]

    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"Missing scoring fields: {missing}")

    for col in required:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    if df[required].isna().any().any():
        raise ValueError("Scoring fields must contain valid numeric values.")

    score_fields = [
        "severity_score",
        "population_score",
        "recurrence_score",
        "duration_score",
        "geographic_score",
    ]

    for col in score_fields:
        if not df[col].between(0, 100).all():
            raise ValueError(f"{col} must be between 0 and 100.")

    if (df["estimated_cost"] < 0).any():
        raise ValueError("Estimated costs cannot be negative.")

    if (df["crew_required"] < 0).any():
        raise ValueError("Crew requirements cannot be negative.")

    if (df["equipment_required"] < 0).any():
        raise ValueError("Equipment requirements cannot be negative.")

    if weights is None:
        active_weights = {
            **URGENCY_WEIGHTS,
            "resource_requirement_score": RESOURCE_WEIGHT,
        }
    else:
        expected = set(FACTOR_LABELS)
        supplied = set(weights)

        if supplied != expected:
            raise ValueError(
                f"Weights must contain exactly these factors: "
                f"{sorted(expected)}"
            )

        active_weights = {
            factor: float(weights[factor])
            for factor in FACTOR_LABELS
        }

        if any(
            value < 0 or value > 100
            for value in active_weights.values()
        ):
            raise ValueError("Weights must be between 0 and 100.")

        if sum(active_weights.values()) <= 0:
            raise ValueError("At least one factor must have a non-zero weight.")

        active_weights = {
            factor: value / sum(active_weights.values())
            for factor, value in active_weights.items()
        }

    cost = df["estimated_cost"]
    crews = df["crew_required"]
    equipment = df["equipment_required"]

    cost_burden = (cost / 100000).clip(0, 1)
    crew_burden = (crews / 6).clip(0, 1)
    equipment_burden = (equipment / 4).clip(0, 1)

    df["resource_requirement_score"] = (
        100
        - (
            cost_burden * 50
            + crew_burden * 30
            + equipment_burden * 20
        )
    ).clip(0, 100).round(2)

    urgency_weight_total = sum(
        active_weights[factor] for factor in URGENCY_WEIGHTS
    )

    urgency_contribution_columns = []

    for factor in URGENCY_WEIGHTS:
        contribution_column = f"{factor}_contribution"
        df[contribution_column] = (
            df[factor] * active_weights[factor]
        )
        urgency_contribution_columns.append(contribution_column)

    if urgency_weight_total > 0:
        df["urgency_score"] = (
            df[urgency_contribution_columns].sum(axis=1)
            / urgency_weight_total
        ).round(2)
    else:
        df["urgency_score"] = 0.0

    df["resource_contribution"] = (
        df["resource_requirement_score"]
        * active_weights["resource_requirement_score"]
    )

    total_weight = sum(active_weights.values())

    overall_contributions = []

    for factor in FACTOR_LABELS:
        contribution_column = f"{factor}_overall_contribution"
        df[contribution_column] = (
            df[factor] * active_weights[factor] / total_weight
        )
        overall_contributions.append(contribution_column)

    df["priority_score"] = (
        df[overall_contributions].sum(axis=1)
    ).round(2)

    df["scoring_weights"] = [
        active_weights.copy() for _ in range(len(df))
    ]

    df = df.sort_values(
        by=["priority_score", "urgency_score"],
        ascending=[False, False],
    ).reset_index(drop=True)

    df["priority_rank"] = range(1, len(df) + 1)

    return df


def explain_priority(row, weights=None):
    if weights is None and "scoring_weights" in row.index:
        weights = row["scoring_weights"]

    if weights is None:
        weights = {
            **URGENCY_WEIGHTS,
            "resource_requirement_score": RESOURCE_WEIGHT,
        }

    total_weight = sum(float(value) for value in weights.values())

    if total_weight <= 0:
        raise ValueError("At least one factor must have a non-zero weight.")

    contributions = {}

    for factor, label in FACTOR_LABELS.items():
        if factor not in row.index:
            raise ValueError(f"Missing explanation field: {factor}")

        contribution = (
            float(row[factor])
            * float(weights[factor])
            / total_weight
        )
        contributions[label] = contribution

    strongest = sorted(
        contributions.items(),
        key=lambda item: item[1],
        reverse=True,
    )[:3]

    reasons = [
        f"{name} (contribution: {value:.1f} points)"
        for name, value in strongest
    ]

    return (
        f"Urgency score: {float(row['urgency_score']):.2f}/100; "
        f"overall score: {float(row['priority_score']):.2f}/100; "
        + "; ".join(reasons)
    )
