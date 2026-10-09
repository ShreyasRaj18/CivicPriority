
from src.input_layer import load_issues
from src.processing import process_issues
from src.scoring import calculate_priority, explain_priority
from src.planner import plan_interventions

# 1. Load the dataset
issues = load_issues()

# 2. Validate and normalize
processed = process_issues(issues)

# 3. Calculate priority scores
ranked = calculate_priority(processed)

# 4. Plan interventions
plan = plan_interventions(
    ranked_issues=ranked,
    budget=100000,  # Change to 100000 for comparison
    available_crews=6,
    available_equipment=4
)

# 5. Display the results
print("\n=== CIVICPRIORITY: INTERVENTION PLAN ===\n")

for _, row in plan.iterrows():
    status = (
        "SELECTED"
        if row["selected_for_intervention"]
        else "DEFERRED"
    )

    print(
        f"{status} | {row['issue_id']} | "
        f"{row['issue_type']} | "
        f"Priority: {row['priority_score']} | "
        f"Cost: Rs. {row['estimated_cost']}"
    )

    print(f"Reason: {row['planning_status']}")
    print(f"Explanation: {explain_priority(row)}\n")

selected = plan[plan["selected_for_intervention"]]

print("=== RESOURCE SUMMARY ===")
print(f"Budget allocated: Rs. {selected['estimated_cost'].sum():,.0f}")
print(f"Issues selected: {len(selected)}")
print(f"Issues deferred: {len(plan) - len(selected)}")
