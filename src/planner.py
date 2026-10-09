
from itertools import combinations

import pandas as pd


def plan_interventions(
    ranked_issues,
    budget,
    available_crews,
    available_equipment
):
    if budget < 0 or available_crews < 0 or available_equipment < 0:
        raise ValueError("Resource limits cannot be negative.")

    df = ranked_issues.copy().reset_index(drop=True)

    required = [
        "issue_id",
        "priority_score",
        "estimated_cost",
        "crew_required",
        "equipment_required"
    ]

    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"Missing planner fields: {missing}")

    if df[required].isna().any().any():
        raise ValueError("Planner inputs cannot contain missing values.")

    numeric_columns = [
        "priority_score",
        "estimated_cost",
        "crew_required",
        "equipment_required"
    ]

    for col in numeric_columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    if df[numeric_columns].isna().any().any():
        raise ValueError("Planner fields must contain numeric values.")

    if not df["priority_score"].between(0, 100).all():
        raise ValueError("Priority scores must be between 0 and 100.")

    if (df["estimated_cost"] < 0).any():
        raise ValueError("Estimated costs cannot be negative.")

    if (df["crew_required"] < 0).any():
        raise ValueError("Crew requirements cannot be negative.")

    if (df["equipment_required"] < 0).any():
        raise ValueError("Equipment requirements cannot be negative.")

    if not (df["crew_required"] % 1 == 0).all():
        raise ValueError("Crew requirements must be whole numbers.")

    if not (df["equipment_required"] % 1 == 0).all():
        raise ValueError("Equipment requirements must be whole numbers.")

    if df["issue_id"].astype(str).duplicated().any():
        raise ValueError("Issue IDs must be unique.")

    if len(df) > 20:
        raise ValueError("Exact planner supports at most 20 issues.")

    output_columns = [
        "selected_for_intervention",
        "planning_status",
        "constraint_conflicts",
        "extra_budget_needed",
        "extra_crews_needed",
        "extra_equipment_needed",
        "budget_used",
        "crews_used",
        "equipment_used",
        "budget_remaining",
        "crews_remaining",
        "equipment_remaining"
    ]

    if df.empty:
        for col in output_columns:
            df[col] = pd.Series(dtype="object")
        return df

    best_indices = ()
    best_score = -1.0
    best_count = -1
    best_cost = float("inf")

    # Find the highest-value feasible combination.
    for count in range(len(df) + 1):
        for indices in combinations(range(len(df)), count):
            group = df.iloc[list(indices)]

            total_cost = float(group["estimated_cost"].sum())
            total_crews = int(group["crew_required"].sum())
            total_equipment = int(group["equipment_required"].sum())
            total_score = float(group["priority_score"].sum())

            feasible = (
                total_cost <= budget
                and total_crews <= available_crews
                and total_equipment <= available_equipment
            )

            if not feasible:
                continue

            better = (
                total_score > best_score
                or (
                    total_score == best_score
                    and count > best_count
                )
                or (
                    total_score == best_score
                    and count == best_count
                    and total_cost < best_cost
                )
            )

            if better:
                best_indices = indices
                best_score = total_score
                best_count = count
                best_cost = total_cost

    selected_indices = set(best_indices)

    df["selected_for_intervention"] = [
        i in selected_indices for i in range(len(df))
    ]

    selected = df[df["selected_for_intervention"]]

    used_budget = float(selected["estimated_cost"].sum())
    used_crews = int(selected["crew_required"].sum())
    used_equipment = int(selected["equipment_required"].sum())

    df["budget_used"] = used_budget
    df["crews_used"] = used_crews
    df["equipment_used"] = used_equipment

    df["budget_remaining"] = max(0, budget - used_budget)
    df["crews_remaining"] = max(0, available_crews - used_crews)
    df["equipment_remaining"] = max(
        0, available_equipment - used_equipment
    )

    statuses = []
    conflicts_list = []
    extra_budgets = []
    extra_crews_list = []
    extra_equipment_list = []

    for _, row in df.iterrows():
        if row["selected_for_intervention"]:
            statuses.append(
                "Selected: part of the highest-value feasible plan"
            )
            conflicts_list.append("None")
            extra_budgets.append(0.0)
            extra_crews_list.append(0)
            extra_equipment_list.append(0)
            continue

        # Test adding this deferred issue to the selected plan.
        budget_excess = max(
            0.0,
            used_budget + float(row["estimated_cost"]) - budget
        )
        crew_excess = max(
            0,
            used_crews + int(row["crew_required"]) - available_crews
        )
        equipment_excess = max(
            0,
            used_equipment
            + int(row["equipment_required"])
            - available_equipment
        )

        conflicts = []

        if budget_excess > 0:
            conflicts.append("budget")

        if crew_excess > 0:
            conflicts.append("crew capacity")

        if equipment_excess > 0:
            conflicts.append("equipment capacity")

        if conflicts:
            reason = (
                "Deferred: adding this issue exceeds "
                + ", ".join(conflicts)
            )
        else:
            reason = (
                "Deferred: another feasible combination has "
                "a higher total priority value"
            )

        statuses.append(reason)
        conflicts_list.append(
            ", ".join(conflicts) if conflicts else "None"
        )
        extra_budgets.append(budget_excess)
        extra_crews_list.append(crew_excess)
        extra_equipment_list.append(equipment_excess)

    df["planning_status"] = statuses
    df["constraint_conflicts"] = conflicts_list
    df["extra_budget_needed"] = extra_budgets
    df["extra_crews_needed"] = extra_crews_list
    df["extra_equipment_needed"] = extra_equipment_list

    return df.reset_index(drop=True)
