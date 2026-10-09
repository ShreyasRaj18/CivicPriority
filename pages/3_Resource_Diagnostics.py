
import pandas as pd
import streamlit as st

from src.input_layer import load_issues
from src.processing import process_issues
from src.scoring import calculate_priority
from src.planner import plan_interventions


st.set_page_config(
    page_title="CivicPriority | Resource Diagnostics",
    page_icon="🏙️",
    layout="wide",
)

st.title("Resource Constraint Diagnostics")
st.caption(
    "Understand why interventions are deferred and which resources "
    "limit the current plan."
)

st.warning(
    "This page uses illustrative sample records. Costs and resource "
    "requirements are not verified municipal estimates."
)


@st.cache_data
def load_scored_issues():
    issues = process_issues(load_issues())
    return calculate_priority(issues)


try:
    issues = load_scored_issues()
except Exception as error:
    st.error(f"Could not load and score issues: {error}")
    st.stop()


if issues.empty:
    st.error("The sample dataset contains no issues to plan.")
    st.stop()

if len(issues) > 20:
    st.error(
        "The exact planner supports at most 20 issues. "
        "This page requires a smaller planning dataset."
    )
    st.stop()


st.subheader("Available resources")

col1, col2, col3 = st.columns(3)

with col1:
    budget = st.number_input(
        "Available budget (₹)",
        min_value=0,
        max_value=100000000,
        value=100000,
        step=5000,
    )

with col2:
    crews = st.number_input(
        "Available crews",
        min_value=0,
        max_value=100,
        value=6,
        step=1,
    )

with col3:
    equipment = st.number_input(
        "Available equipment units",
        min_value=0,
        max_value=100,
        value=4,
        step=1,
    )


plan = plan_interventions(
    ranked_issues=issues,
    budget=int(budget),
    available_crews=int(crews),
    available_equipment=int(equipment),
)

selected = plan[plan["selected_for_intervention"].astype(bool)].copy()
deferred = plan[~plan["selected_for_intervention"].astype(bool)].copy()

budget_used = float(selected["estimated_cost"].sum())
crews_used = int(selected["crew_required"].sum())
equipment_used = int(selected["equipment_required"].sum())

budget_remaining = max(0, int(budget) - budget_used)
crews_remaining = max(0, int(crews) - crews_used)
equipment_remaining = max(0, int(equipment) - equipment_used)


st.divider()
st.subheader("Plan summary")

m1, m2, m3, m4 = st.columns(4)

m1.metric("Selected interventions", len(selected))
m2.metric("Deferred interventions", len(deferred))
m3.metric("Budget used", f"₹{budget_used:,.0f}")
m4.metric("Budget remaining", f"₹{budget_remaining:,.0f}")

r1, r2, r3 = st.columns(3)

r1.metric("Crews used", f"{crews_used} / {int(crews)}")
r2.metric("Equipment used", f"{equipment_used} / {int(equipment)}")
r3.metric(
    "Selected priority value",
    f"{selected['priority_score'].sum():.2f}",
)


st.subheader("Resource utilisation")

utilisation = pd.DataFrame(
    {
        "Resource": ["Budget", "Crews", "Equipment"],
        "Used": [budget_used, crews_used, equipment_used],
        "Available": [budget, crews, equipment],
        "Remaining": [
            budget_remaining,
            crews_remaining,
            equipment_remaining,
        ],
    }
)

st.dataframe(utilisation, use_container_width=True, hide_index=True)


st.subheader("Constraint diagnosis")

if budget_remaining == 0:
    st.warning("Budget is fully utilised.")
else:
    st.info(f"₹{budget_remaining:,.0f} of the budget remains available.")

if crews_remaining == 0:
    st.warning("Crew capacity is fully utilised.")
else:
    st.info(f"{crews_remaining} crew units remain available.")

if equipment_remaining == 0:
    st.warning("Equipment capacity is fully utilised.")
else:
    st.info(f"{equipment_remaining} equipment units remain available.")


st.subheader("Deferred intervention diagnostics")

if deferred.empty:
    st.success("All issues in the current dataset were selected.")
else:
    diagnostic_columns = [
        "issue_id",
        "issue_type",
        "location",
        "urgency_score",
        "priority_score",
        "estimated_cost",
        "crew_required",
        "equipment_required",
        "constraint_conflicts",
        "extra_budget_needed",
        "extra_crews_needed",
        "extra_equipment_needed",
        "planning_status",
    ]

    st.dataframe(
        deferred[diagnostic_columns],
        use_container_width=True,
        hide_index=True,
    )

    selected_issue_id = st.selectbox(
        "Inspect a deferred intervention",
        deferred["issue_id"].astype(str).tolist(),
    )

    issue = deferred[
        deferred["issue_id"].astype(str) == selected_issue_id
    ].iloc[0]

    st.markdown(f"### Issue {selected_issue_id}")

    st.write(f"**Issue type:** {issue['issue_type']}")
    st.write(f"**Location:** {issue['location']}")
    st.write(f"**Urgency score:** {issue['urgency_score']:.2f}/100")
    st.write(f"**Overall priority score:** {issue['priority_score']:.2f}/100")
    st.write(f"**Estimated cost:** ₹{issue['estimated_cost']:,.0f}")
    st.write(f"**Crews required:** {int(issue['crew_required'])}")
    st.write(f"**Equipment required:** {int(issue['equipment_required'])}")
    st.write(f"**Current constraint conflicts:** {issue['constraint_conflicts']}")
    st.write(f"**Planner decision:** {issue['planning_status']}")

    st.markdown("#### Additional resources needed alongside the current plan")

    d1, d2, d3 = st.columns(3)

    d1.metric(
        "Additional budget",
        f"₹{issue['extra_budget_needed']:,.0f}",
    )
    d2.metric(
        "Additional crews",
        int(issue["extra_crews_needed"]),
    )
    d3.metric(
        "Additional equipment",
        int(issue["extra_equipment_needed"]),
    )

    st.caption(
        "These requirements are calculated against the existing selected "
        "plan. They are not a guarantee that increasing just one resource "
        "will make this issue selectable."
    )


st.subheader("Selected interventions")

if selected.empty:
    st.info("No interventions fit the current resource limits.")
else:
    selected_columns = [
        "issue_id",
        "issue_type",
        "location",
        "urgency_score",
        "priority_score",
        "estimated_cost",
        "crew_required",
        "equipment_required",
        "planning_status",
    ]

    st.dataframe(
        selected[selected_columns],
        use_container_width=True,
        hide_index=True,
    )


st.download_button(
    "Download full resource diagnostic report",
    data=plan.to_csv(index=False).encode("utf-8-sig"),
    file_name="civicpriority_resource_diagnostics.csv",
    mime="text/csv",
)
