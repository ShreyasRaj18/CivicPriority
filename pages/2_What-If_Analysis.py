
from pathlib import Path

import pandas as pd
import streamlit as st

from src.input_layer import load_issues
from src.processing import process_issues
from src.scoring import calculate_priority
from src.planner import plan_interventions


ROOT = Path(__file__).resolve().parent.parent

st.set_page_config(
    page_title="CivicPriority | What-If Analysis",
    page_icon="🏙️",
    layout="wide",
)

st.title("What-If Analysis")
st.caption(
    "Compare intervention plans under different budgets "
    "and resource constraints."
)

st.warning(
    "This analysis uses illustrative sample records. "
    "Costs, crew requirements, equipment requirements, and "
    "several scoring factors are not verified municipal measurements."
)


@st.cache_data
def get_issues():
    raw = load_issues()
    processed = process_issues(raw)
    return calculate_priority(processed)


def run_plan(issues, budget, crews, equipment):
    return plan_interventions(
        ranked_issues=issues,
        budget=budget,
        available_crews=crews,
        available_equipment=equipment,
    )


try:
    issues = get_issues()
except Exception as error:
    st.error(f"Could not load or score the sample dataset: {error}")
    st.stop()


if len(issues) > 20:
    st.error(
        "The current exact planner supports at most 20 issues. "
        "Reduce the dataset before running this analysis."
    )
    st.stop()


if issues.empty:
    st.error("The sample dataset contains no issues to plan.")
    st.stop()


st.subheader("Baseline scenario")

base_col1, base_col2, base_col3 = st.columns(3)

with base_col1:
    baseline_budget = st.number_input(
        "Baseline budget (₹)",
        min_value=0,
        max_value=100000000,
        value=65000,
        step=5000,
        key="baseline_budget",
    )

with base_col2:
    baseline_crews = st.number_input(
        "Baseline available crews",
        min_value=0,
        max_value=100,
        value=6,
        step=1,
        key="baseline_crews",
    )

with base_col3:
    baseline_equipment = st.number_input(
        "Baseline equipment units",
        min_value=0,
        max_value=100,
        value=4,
        step=1,
        key="baseline_equipment",
    )


st.subheader("Alternative scenario")

alt_col1, alt_col2, alt_col3 = st.columns(3)

with alt_col1:
    alternative_budget = st.slider(
        "Alternative budget (₹)",
        min_value=0,
        max_value=200000,
        value=100000,
        step=5000,
        key="alternative_budget",
    )

with alt_col2:
    alternative_crews = st.slider(
        "Alternative available crews",
        min_value=0,
        max_value=12,
        value=8,
        step=1,
        key="alternative_crews",
    )

with alt_col3:
    alternative_equipment = st.slider(
        "Alternative equipment units",
        min_value=0,
        max_value=12,
        value=6,
        step=1,
        key="alternative_equipment",
    )


baseline_plan = run_plan(
    issues,
    int(baseline_budget),
    int(baseline_crews),
    int(baseline_equipment),
)

alternative_plan = run_plan(
    issues,
    int(alternative_budget),
    int(alternative_crews),
    int(alternative_equipment),
)


baseline_selected = baseline_plan[
    baseline_plan["selected_for_intervention"].astype(bool)
].copy()

alternative_selected = alternative_plan[
    alternative_plan["selected_for_intervention"].astype(bool)
].copy()


baseline_ids = set(baseline_selected["issue_id"].astype(str))
alternative_ids = set(alternative_selected["issue_id"].astype(str))

added_ids = alternative_ids - baseline_ids
removed_ids = baseline_ids - alternative_ids

baseline_value = float(baseline_selected["priority_score"].sum())
alternative_value = float(alternative_selected["priority_score"].sum())

baseline_cost = float(baseline_selected["estimated_cost"].sum())
alternative_cost = float(alternative_selected["estimated_cost"].sum())

baseline_crew_use = int(baseline_selected["crew_required"].sum())
alternative_crew_use = int(alternative_selected["crew_required"].sum())

baseline_equipment_use = int(
    baseline_selected["equipment_required"].sum()
)
alternative_equipment_use = int(
    alternative_selected["equipment_required"].sum()
)


st.divider()
st.subheader("Scenario comparison")

metric1, metric2, metric3, metric4 = st.columns(4)

metric1.metric(
    "Baseline interventions",
    len(baseline_selected),
)

metric2.metric(
    "Alternative interventions",
    len(alternative_selected),
    delta=len(alternative_selected) - len(baseline_selected),
)

metric3.metric(
    "Baseline budget used",
    f"₹{baseline_cost:,.0f}",
)

metric4.metric(
    "Alternative budget used",
    f"₹{alternative_cost:,.0f}",
    delta=f"₹{alternative_cost - baseline_cost:,.0f}",
)


value1, value2, value3 = st.columns(3)

value1.metric(
    "Baseline total priority value",
    f"{baseline_value:.2f}",
)

value2.metric(
    "Alternative total priority value",
    f"{alternative_value:.2f}",
    delta=f"{alternative_value - baseline_value:+.2f}",
)

value3.metric(
    "Priority value change",
    f"{alternative_value - baseline_value:+.2f}",
)


st.subheader("Resource utilisation")

resource_data = pd.DataFrame(
    {
        "Resource": ["Budget", "Crews", "Equipment"],
        "Baseline used": [
            baseline_cost,
            baseline_crew_use,
            baseline_equipment_use,
        ],
        "Baseline available": [
            baseline_budget,
            baseline_crews,
            baseline_equipment,
        ],
        "Alternative used": [
            alternative_cost,
            alternative_crew_use,
            alternative_equipment_use,
        ],
        "Alternative available": [
            alternative_budget,
            alternative_crews,
            alternative_equipment,
        ],
    }
)

st.dataframe(
    resource_data,
    use_container_width=True,
    hide_index=True,
)


display_columns = [
    "issue_id",
    "issue_type",
    "location",
    "urgency_score",
    "priority_score",
    "estimated_cost",
    "crew_required",
    "equipment_required",
]


st.subheader("Interventions added in the alternative plan")

if added_ids:
    st.dataframe(
        alternative_selected[
            alternative_selected["issue_id"].astype(str).isin(added_ids)
        ][
            [column for column in display_columns
             if column in alternative_selected.columns]
        ],
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info("No additional interventions were selected.")


st.subheader("Interventions removed from the baseline plan")

if removed_ids:
    st.dataframe(
        baseline_selected[
            baseline_selected["issue_id"].astype(str).isin(removed_ids)
        ][
            [column for column in display_columns
             if column in baseline_selected.columns]
        ],
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info("No baseline interventions were removed.")


st.subheader("Baseline intervention plan")

st.dataframe(
    baseline_plan[
        [
            column for column in [
                "issue_id",
                "issue_type",
                "location",
                "urgency_score",
                "priority_score",
                "priority_rank",
                "selected_for_intervention",
                "planning_status",
            ]
            if column in baseline_plan.columns
        ]
    ],
    use_container_width=True,
    hide_index=True,
)


st.subheader("Alternative intervention plan")

st.dataframe(
    alternative_plan[
        [
            column for column in [
                "issue_id",
                "issue_type",
                "location",
                "urgency_score",
                "priority_score",
                "priority_rank",
                "selected_for_intervention",
                "planning_status",
            ]
            if column in alternative_plan.columns
        ]
    ],
    use_container_width=True,
    hide_index=True,
)


st.subheader("Interpretation")

if alternative_value > baseline_value:
    st.success(
        "The alternative scenario produces a higher total selected "
        "priority value under the configured constraints."
    )
elif alternative_value < baseline_value:
    st.warning(
        "The alternative scenario produces a lower total selected "
        "priority value. Review the resource limits and selected issues."
    )
else:
    st.info(
        "The total selected priority value is unchanged. Additional "
        "resources may not improve the plan if other constraints remain "
        "binding or no better feasible combination exists."
    )


st.caption(
    "Both scenarios use the shared scoring engine and the same issue scores. "
    "Priority value is the sum of selected issue scores, not a monetary "
    "benefit or measured reduction in complaints. Scoring scales and resource "
    "estimates are prototype assumptions, not validated municipal policy."
)


download_data = alternative_plan.to_csv(index=False).encode("utf-8-sig")

st.download_button(
    "Download alternative intervention plan",
    data=download_data,
    file_name="civicpriority_what_if_plan.csv",
    mime="text/csv",
)
