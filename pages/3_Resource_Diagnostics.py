from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from src.input_layer import load_issues
from src.processing import process_issues
from src.scoring import calculate_priority
from src.planner import plan_interventions

st.set_page_config(page_title="CivicPriority | Intervention Planner", page_icon="🏙️", layout="wide")

st.markdown(
    '''
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
    h1, h2, h3, h4, h5, h6 { font-family: 'DM Sans', sans-serif !important; letter-spacing: -.02em; }
    .block-container { max-width: 1400px; padding-top: 1.2rem; padding-bottom: 3rem; }
    [data-testid="stAppViewContainer"] { background: #f7f8fc; }
    [data-testid="stMetric"] { background: #fff; border: 1px solid #e6e9f2; padding: 1rem 1.1rem; border-radius: 16px; box-shadow: 0 2px 10px rgba(20,32,70,.035); }
    .hero { padding: 1.8rem 2rem; border-radius: 22px; color: white; background: linear-gradient(118deg,#101d54 0%,#2449bd 58%,#5577ef 100%); margin-bottom: 1rem; box-shadow: 0 12px 32px rgba(27,57,150,.15); }
    .hero h1 { color: white !important; margin-bottom: .35rem; }
    .hero p { color: rgba(255,255,255,.9); margin: 0; }
    div[data-testid="stDataFrame"] { border: 1px solid #e6e9f2; border-radius: 14px; overflow: hidden; background: white; }
    </style>
    ''',
    unsafe_allow_html=True,
)

st.markdown(
    '''
    <div class="hero">
      <h1>Resource planning: what can we do first?</h1>
      <p>Choose a budget, number of work crews and equipment units. CivicPriority then selects the combination of sample interventions that gives the highest total priority score without exceeding those limits.</p>
    </div>
    ''',
    unsafe_allow_html=True,
)
st.caption("Demonstration only · Uses illustrative sample interventions, costs and staffing requirements—not verified Bengaluru estimates")
st.info("**Use case:** A civic team has more problems to address than it can handle at once. This page helps compare which combination of work fits the resources available today, and shows what may need to wait. It does not dispatch crews or make a real municipal work order.")

@st.cache_data
def load_scored_issues():
    issues = process_issues(load_issues())
    return calculate_priority(issues)

try:
    issues = load_scored_issues()
except Exception:
    st.error("The sample planning data could not be loaded. Check the input data and try again.")
    st.stop()

if issues.empty:
    st.error("There are no sample interventions to plan.")
    st.stop()

if len(issues) > 20:
    st.error("This exact planning demonstration supports up to 20 sample interventions. Reduce the sample dataset to continue.")
    st.stop()

st.subheader("1. Tell the planner what you have")
st.write("Change these values to see how the proposed work changes. The plan updates automatically.")

a, b, c = st.columns(3)
with a:
    budget = st.number_input("Budget available (₹)", min_value=0, max_value=100000000, value=100000, step=5000, help="Total money available for this planning run.")
with b:
    crews = st.number_input("Work crews available", min_value=0, max_value=100, value=6, step=1, help="Number of crews that can be assigned.")
with c:
    equipment = st.number_input("Equipment units available", min_value=0, max_value=100, value=4, step=1, help="Number of equipment units available.")

plan = plan_interventions(ranked_issues=issues, budget=int(budget), available_crews=int(crews), available_equipment=int(equipment))
selected = plan[plan["selected_for_intervention"].astype(bool)].copy()
deferred = plan[~plan["selected_for_intervention"].astype(bool)].copy()

budget_used = float(selected["estimated_cost"].sum())
crews_used = int(selected["crew_required"].sum())
equipment_used = int(selected["equipment_required"].sum())
budget_remaining = max(0, int(budget) - budget_used)
crews_remaining = max(0, int(crews) - crews_used)
equipment_remaining = max(0, int(equipment) - equipment_used)

def percent(used, available):
    return min(100, int(used / available * 100)) if available else 0

st.divider()
st.subheader("2. What fits within those limits?")
m1, m2, m3, m4 = st.columns(4)
m1.metric("Work selected", f"{len(selected)} of {len(plan)}")
m2.metric("Work postponed", f"{len(deferred)}")
m3.metric("Budget committed", f"₹{budget_used:,.0f}")
m4.metric("Budget remaining", f"₹{budget_remaining:,.0f}")

if selected.empty:
    st.warning("No sample interventions fit within these limits. Try increasing one or more resources.")
else:
    st.success(f"The current plan can take on {len(selected)} intervention(s) within the limits you set.")

st.subheader("3. How much of each resource will the selected work use?")
resource_rows = [
    ("Budget", budget_used, int(budget), budget_remaining, percent(budget_used, budget)),
    ("Work crews", crews_used, int(crews), crews_remaining, percent(crews_used, crews)),
    ("Equipment", equipment_used, int(equipment), equipment_remaining, percent(equipment_used, equipment)),
]
left, right = st.columns([1, 1])
with left:
    for name, used, available, remaining, pct in resource_rows:
        st.markdown(f"**{name}**")
        st.progress(pct)
        st.caption(f"{used:,.0f} used · {remaining:,.0f} left out of {available:,.0f}")
with right:
    usage = pd.DataFrame({"Resource": [r[0] for r in resource_rows], "Used (%)": [r[4] for r in resource_rows]})
    chart = px.bar(usage, x="Resource", y="Used (%)", text=usage["Used (%)"].map(lambda value: f"{value}%"), range_y=[0, 110], color_discrete_sequence=["#3157d5"])
    chart.update_layout(height=300, margin=dict(l=10, r=10, t=20, b=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(family="DM Sans, sans-serif", color="#27324b"), yaxis=dict(title="Capacity used", ticksuffix="%", showgrid=True, gridcolor="#edf0f6"), xaxis_title="", showlegend=False)
    st.plotly_chart(chart, use_container_width=True)

st.subheader("4. What does not fit—and why?")
st.write("Postponed does not mean unimportant. It means the work did not fit into the best combination under the limits you entered.")

if deferred.empty:
    st.success("All sample interventions fit within the current plan.")
else:
    for _, issue in deferred.iterrows():
        issue_type = str(issue.get("issue_type", "Intervention"))
        location = str(issue.get("location", "Location not recorded"))
        priority = float(issue.get("priority_score", 0) or 0)
        with st.expander(f"{issue_type} · {location} · Priority {priority:.1f}/100"):
            cost = float(issue.get("estimated_cost", 0) or 0)
            crews_needed = int(issue.get("crew_required", 0) or 0)
            equipment_needed = int(issue.get("equipment_required", 0) or 0)
            st.write(f"**Estimated cost:** ₹{cost:,.0f}")
            st.write(f"**People and equipment needed:** {crews_needed} crew(s), {equipment_needed} equipment unit(s)")
            conflicts = str(issue.get("constraint_conflicts", "")).strip()
            if conflicts and conflicts.lower() not in {"nan", "none", "[]"}:
                st.write(f"**What is getting in the way:** {conflicts.replace('_', ' ').replace(';', ', ')}")
            else:
                st.write("**What is getting in the way:** This intervention does not fit alongside the selected work within the current combined limits.")
            x, y, z = st.columns(3)
            x.metric("Extra budget estimate", f"₹{float(issue.get('extra_budget_needed', 0) or 0):,.0f}")
            y.metric("Extra crews estimate", int(issue.get("extra_crews_needed", 0) or 0))
            z.metric("Extra equipment estimate", int(issue.get("extra_equipment_needed", 0) or 0))
            st.caption("These are estimates compared with the current plan. Adding only one resource may not be enough.")

st.subheader("5. Work proposed for this planning run")
if selected.empty:
    st.info("Nothing is selected at the moment.")
else:
    rename = {
        "issue_id": "Reference",
        "issue_type": "Intervention",
        "location": "Area",
        "urgency_score": "Urgency",
        "priority_score": "Priority",
        "estimated_cost": "Estimated cost (₹)",
        "crew_required": "Crews",
        "equipment_required": "Equipment units",
    }
    selected_view = selected.rename(columns=rename)
    columns = [c for c in ["Reference", "Intervention", "Area", "Urgency", "Priority", "Estimated cost (₹)", "Crews", "Equipment units"] if c in selected_view.columns]
    st.dataframe(selected_view[columns], use_container_width=True, hide_index=True)

with st.expander("How to use this page and interpret the result"):
    st.write("1. Enter the money, crews and equipment available. 2. Review the work selected and the resources it consumes. 3. Expand postponed items to see their estimated needs and the constraints that kept them out of the current plan.")
    st.write("The planner tests combinations of the sample interventions and chooses the combination with the highest total priority score that fits all three limits. A postponed item is not necessarily unimportant; it may simply not fit alongside the selected work.")
    st.warning("All sample costs, staffing and equipment requirements are illustrative. This page is a prototype for explaining resource-aware planning, not an operational recommendation. Use validated local estimates before making real decisions.")

st.download_button("Download planning report (CSV)", data=plan.to_csv(index=False).encode("utf-8-sig"), file_name="civicpriority_intervention_plan.csv", mime="text/csv")
