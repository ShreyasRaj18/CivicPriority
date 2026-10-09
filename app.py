
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from src.input_layer import load_issues
from src.processing import process_issues
from src.scoring import calculate_priority
from src.planner import plan_interventions


ROOT = Path(__file__).resolve().parent
REAL_DATA_FILE = ROOT / "data" / "ranked_real_issues.csv"
UNCATEGORIZED = "Uncategorized (missing category)"

URGENCY_FACTORS = {
    "severity_score": ("Severity", 30),
    "population_score": ("Population affected", 25),
    "recurrence_score": ("Recurrence", 15),
    "duration_score": ("Duration", 10),
    "geographic_score": ("Geographic context", 10),
}

RESOURCE_FACTOR = "resource_requirement_score"
ALL_FACTORS = {
    **URGENCY_FACTORS,
    RESOURCE_FACTOR: ("Resource feasibility", 10),
}


st.set_page_config(
    page_title="CivicPriority",
    page_icon="🏙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🏙️ CivicPriority")
st.subheader("Urban Infrastructure Priority Engine")
st.caption(
    "Explainable complaint analysis, six-factor scoring and "
    "resource-aware intervention planning."
)


@st.cache_data
def load_real_data(path, modified_time):
    df = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)

    for col in ["priority_score", "priority_rank", "latitude", "longitude"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "created_at" in df.columns:
        df["created_at"] = pd.to_datetime(
            df["created_at"], errors="coerce"
        )

    if "category_title" in df.columns:
        df["category_title"] = (
            df["category_title"]
            .fillna(UNCATEGORIZED)
            .replace("", UNCATEGORIZED)
        )

    if "complaint_status_title" in df.columns:
        df["complaint_status_title"] = (
            df["complaint_status_title"]
            .fillna("Unknown")
            .replace("", "Unknown")
        )

    return df


@st.cache_data
def load_sample_data():
    raw = load_issues()
    processed = process_issues(raw)
    return calculate_priority(processed)


def apply_scenario_weights(sample, weights):
    scenario = sample.copy()

    total_weight = sum(weights.values())
    urgency_weight = sum(weights[factor] for factor in URGENCY_FACTORS)

    if total_weight <= 0:
        raise ValueError("At least one factor must have a non-zero weight.")

    for factor in ALL_FACTORS:
        scenario[f"{factor}_contribution"] = (
            pd.to_numeric(scenario[factor], errors="coerce")
            * weights[factor]
            / total_weight
        )

    scenario["priority_score"] = sum(
        scenario[f"{factor}_contribution"]
        for factor in ALL_FACTORS
    ).round(2)

    if urgency_weight > 0:
        scenario["urgency_score"] = sum(
            pd.to_numeric(scenario[factor], errors="coerce")
            * weights[factor]
            for factor in URGENCY_FACTORS
        ).div(urgency_weight).round(2)
    else:
        scenario["urgency_score"] = 0.0

    scenario = scenario.sort_values(
        ["priority_score", "urgency_score"],
        ascending=[False, False],
    ).reset_index(drop=True)

    scenario["priority_rank"] = range(1, len(scenario) + 1)

    return scenario


def explain_scenario_priority(row, weights):
    total_weight = sum(weights.values())

    contributions = [
        (
            ALL_FACTORS[factor][0],
            float(row[factor]) * weights[factor] / total_weight,
        )
        for factor in ALL_FACTORS
    ]

    strongest = sorted(
        contributions,
        key=lambda item: item[1],
        reverse=True,
    )[:3]

    reasons = "; ".join(
        f"{name} ({value:.1f} points)"
        for name, value in strongest
    )

    return (
        f"Urgency: {row['urgency_score']:.2f}/100; "
        f"overall priority: {row['priority_score']:.2f}/100; "
        f"strongest contributions: {reasons}"
    )


if not REAL_DATA_FILE.exists():
    st.error(f"Historical dataset not found: {REAL_DATA_FILE}")
    st.stop()

try:
    real_df = load_real_data(
        str(REAL_DATA_FILE),
        REAL_DATA_FILE.stat().st_mtime,
    )
    sample_df = load_sample_data()
except Exception as exc:
    st.error(f"Could not initialize CivicPriority: {exc}")
    st.stop()


required_real = [
    "priority_score",
    "priority_rank",
    "category_title",
    "complaint_status_title",
]

missing_real = [col for col in required_real if col not in real_df.columns]

if missing_real:
    st.error(f"Historical dataset is missing columns: {missing_real}")
    st.stop()

categories = sorted(real_df["category_title"].unique().tolist())
statuses = sorted(real_df["complaint_status_title"].unique().tolist())

st.sidebar.title("Historical Analysis")

selected_categories = st.sidebar.multiselect(
    "Categories",
    categories,
    default=categories,
)

selected_statuses = st.sidebar.multiselect(
    "Historical statuses",
    statuses,
    default=statuses,
)

score_min = float(real_df["priority_score"].min())
score_max = float(real_df["priority_score"].max())

score_range = st.sidebar.slider(
    "Historical review score",
    min_value=0.0,
    max_value=100.0,
    value=(score_min, score_max),
    step=1.0,
)

historical = real_df[
    real_df["category_title"].isin(selected_categories)
    & real_df["complaint_status_title"].isin(selected_statuses)
    & real_df["priority_score"].between(score_range[0], score_range[1])
].copy()


overview_tab, historical_tab, scoring_tab, planner_tab, map_tab, methodology_tab = st.tabs(
    [
        "Overview",
        "Historical Complaints",
        "Six-Factor Scoring",
        "Intervention Planner",
        "Map View",
        "Methodology",
    ]
)


with overview_tab:
    open_count = int(
        historical["complaint_status_title"]
        .astype(str)
        .str.lower()
        .eq("open")
        .sum()
    )

    m1, m2, m3, m4 = st.columns(4)

    m1.metric("Historical complaints", f"{len(historical):,}")
    m2.metric("Historically open", f"{open_count:,}")
    m3.metric(
        "Categories represented",
        f"{historical['category_title'].nunique():,}",
    )
    m4.metric(
        "Mean review score",
        f"{historical['priority_score'].mean():.1f}/100"
        if not historical.empty
        else "N/A",
    )

    st.info(
        "Historical records are from Bengaluru, 2019–2022. Historical "
        "status is not current status, and the historical review score "
        "is distinct from the six-factor sample-data score."
    )

    if UNCATEGORIZED in set(historical["category_title"]):
        missing_category_count = int(
            historical["category_title"].eq(UNCATEGORIZED).sum()
        )
        st.warning(
            f"{missing_category_count:,} historical records have no "
            "category assigned in the source data. They are retained "
            "under 'Uncategorized (missing category)'."
        )

    left, right = st.columns(2)

    with left:
        category_counts = (
            historical["category_title"]
            .value_counts()
            .rename_axis("Category")
            .reset_index(name="Complaints")
        )

        if not category_counts.empty:
            fig = px.bar(
                category_counts.head(12).sort_values("Complaints"),
                x="Complaints",
                y="Category",
                orientation="h",
                title="Most represented categories",
            )
            fig.update_layout(yaxis_title="")
            st.plotly_chart(fig, use_container_width=True)

    with right:
        status_counts = (
            historical["complaint_status_title"]
            .value_counts()
            .rename_axis("Status")
            .reset_index(name="Complaints")
        )

        if not status_counts.empty:
            fig = px.pie(
                status_counts,
                names="Status",
                values="Complaints",
                hole=0.45,
                title="Historical complaint statuses",
            )
            st.plotly_chart(fig, use_container_width=True)


with historical_tab:
    st.markdown("### Historical complaint ranking")

    search_text = st.text_input(
        "Search historical records",
        placeholder="Title, category, subcategory, ward or location",
    )

    view = historical.copy()

    if search_text.strip():
        search_columns = [
            col
            for col in [
                "title",
                "sub_category_title",
                "category_title",
                "ward_title",
                "location",
                "address",
            ]
            if col in view.columns
        ]

        match = pd.Series(False, index=view.index)

        for col in search_columns:
            match |= view[col].fillna("").astype(str).str.contains(
                search_text,
                case=False,
                regex=False,
            )

        view = view[match]

    view = view.sort_values("priority_score", ascending=False)

    columns = [
        col
        for col in [
            "priority_rank",
            "record_id",
            "title",
            "category_title",
            "sub_category_title",
            "ward_title",
            "complaint_status_title",
            "priority_score",
            "priority_explanation",
        ]
        if col in view.columns
    ]

    st.dataframe(
        view[columns],
        use_container_width=True,
        hide_index=True,
        height=450,
    )

    st.download_button(
        "Download filtered historical records",
        data=view.to_csv(index=False).encode("utf-8-sig"),
        file_name="civicpriority_historical_records.csv",
        mime="text/csv",
    )


with scoring_tab:
    st.markdown("### Six-factor priority scoring engine")

    st.warning(
        "This view uses the illustrative sample dataset. Severity, "
        "population, duration, geographic importance and resource values "
        "are not verified measurements from the Bengaluru records."
    )

    st.markdown("#### Model weights")

    weight_columns = st.columns(3)
    adjusted_weights = {}

    for index, (factor, (label, default)) in enumerate(ALL_FACTORS.items()):
        with weight_columns[index % 3]:
            adjusted_weights[factor] = st.number_input(
                f"{label} weight (%)",
                min_value=0,
                max_value=100,
                value=default,
                step=5,
                key=f"factor_weight_{factor}",
            )

    weight_total = sum(adjusted_weights.values())
    urgency_weight_total = sum(
        adjusted_weights[factor] for factor in URGENCY_FACTORS
    )

    if weight_total != 100:
        st.warning(
            f"Your weights total {weight_total}%. They will be "
            "normalized proportionally for this scenario."
        )

    if weight_total == 0:
        st.error("At least one factor must have a non-zero weight.")
        st.stop()

    scenario = apply_scenario_weights(sample_df, adjusted_weights)

    c1, c2, c3 = st.columns(3)

    c1.metric("Issues scored", len(scenario))
    c2.metric(
        "Mean urgency",
        f"{scenario['urgency_score'].mean():.2f}/100",
    )
    c3.metric(
        "Mean overall priority",
        f"{scenario['priority_score'].mean():.2f}/100",
    )

    chosen_id = st.selectbox(
        "Inspect an issue",
        scenario["issue_id"].astype(str).tolist(),
        key="scoring_issue",
    )

    selected = scenario[
        scenario["issue_id"].astype(str) == chosen_id
    ].iloc[0]

    selected_col1, selected_col2 = st.columns(2)

    selected_col1.metric(
        "Overall priority score",
        f"{selected['priority_score']:.2f}/100",
    )
    selected_col2.metric(
        "Urgency score",
        f"{selected['urgency_score']:.2f}/100",
    )

    contribution_rows = []

    for factor, (label, _) in ALL_FACTORS.items():
        contribution_rows.append(
            {
                "Factor": label,
                "Normalized factor score": round(float(selected[factor]), 2),
                "Weight (%)": adjusted_weights[factor],
                "Weighted contribution": round(
                    float(selected[factor])
                    * adjusted_weights[factor]
                    / weight_total,
                    2,
                ),
            }
        )

    contribution_df = pd.DataFrame(contribution_rows)

    st.markdown("#### Factor contributions")
    st.dataframe(
        contribution_df,
        use_container_width=True,
        hide_index=True,
    )

    fig = px.bar(
        contribution_df.sort_values("Weighted contribution"),
        x="Weighted contribution",
        y="Factor",
        orientation="h",
        title="Contribution to this scenario's overall score",
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("#### Ranked sample issues")

    ranked_columns = [
        col
        for col in [
            "priority_rank",
            "issue_id",
            "issue_type",
            "location",
            "urgency_score",
            RESOURCE_FACTOR,
            "priority_score",
            "estimated_cost",
        ]
        if col in scenario.columns
    ]

    st.dataframe(
        scenario[ranked_columns],
        use_container_width=True,
        hide_index=True,
    )

    st.download_button(
        "Download six-factor scores",
        data=scenario.to_csv(index=False).encode("utf-8-sig"),
        file_name="civicpriority_six_factor_scores.csv",
        mime="text/csv",
    )


with planner_tab:
    st.markdown("### Resource-aware intervention planner")

    st.warning(
        "Illustrative mode: costs, crews and equipment come from the "
        "sample dataset, not verified municipal estimates."
    )

    budget_col, crew_col, equipment_col = st.columns(3)

    with budget_col:
        budget = st.number_input(
            "Available budget (₹)",
            min_value=0,
            max_value=1000000000,
            value=65000,
            step=5000,
        )

    with crew_col:
        crews = st.number_input(
            "Available crews",
            min_value=0,
            max_value=1000,
            value=6,
            step=1,
        )

    with equipment_col:
        equipment = st.number_input(
            "Available equipment units",
            min_value=0,
            max_value=1000,
            value=4,
            step=1,
        )

    if st.button("Recalculate intervention plan", type="primary"):
        st.session_state["plan_budget"] = int(budget)
        st.session_state["plan_crews"] = int(crews)
        st.session_state["plan_equipment"] = int(equipment)

    plan_budget = st.session_state.get("plan_budget", int(budget))
    plan_crews = st.session_state.get("plan_crews", int(crews))
    plan_equipment = st.session_state.get(
        "plan_equipment", int(equipment)
    )

    planning_data = scenario.copy()

    plan = plan_interventions(
        ranked_issues=planning_data,
        budget=plan_budget,
        available_crews=plan_crews,
        available_equipment=plan_equipment,
    )

    selected_plan = plan[
        plan["selected_for_intervention"].astype(bool)
    ].copy()

    deferred_plan = plan[
        ~plan["selected_for_intervention"].astype(bool)
    ].copy()

    budget_used = float(selected_plan["estimated_cost"].sum())
    crews_used = int(selected_plan["crew_required"].sum())
    equipment_used = int(selected_plan["equipment_required"].sum())

    m1, m2, m3, m4 = st.columns(4)

    m1.metric("Selected", len(selected_plan))
    m2.metric("Deferred", len(deferred_plan))
    m3.metric("Budget used", f"₹{budget_used:,.0f}")
    m4.metric(
        "Budget remaining",
        f"₹{max(0, plan_budget - budget_used):,.0f}",
    )

    r1, r2 = st.columns(2)

    with r1:
        st.write(f"Crews used: **{crews_used} / {plan_crews}**")
        st.progress(
            min(1.0, crews_used / plan_crews)
            if plan_crews > 0
            else 0.0
        )

    with r2:
        st.write(
            f"Equipment used: **{equipment_used} / {plan_equipment}**"
        )
        st.progress(
            min(1.0, equipment_used / plan_equipment)
            if plan_equipment > 0
            else 0.0
        )

    planner_columns = [
        col
        for col in [
            "issue_id",
            "issue_type",
            "location",
            "urgency_score",
            "priority_score",
            "priority_rank",
            "estimated_cost",
            "crew_required",
            "equipment_required",
            "planning_status",
        ]
        if col in plan.columns
    ]

    selected_tab, deferred_tab = st.tabs(
        ["Selected interventions", "Deferred interventions"]
    )

    with selected_tab:
        st.dataframe(
            selected_plan[planner_columns],
            use_container_width=True,
            hide_index=True,
        )

    with deferred_tab:
        st.dataframe(
            deferred_plan[planner_columns],
            use_container_width=True,
            hide_index=True,
        )

    explanations = []

    for _, row in plan.iterrows():
        explanations.append(
            {
                "Issue": row["issue_id"],
                "Decision": (
                    "Selected"
                    if bool(row["selected_for_intervention"])
                    else "Deferred"
                ),
                "Explanation": explain_scenario_priority(
                    row, adjusted_weights
                ),
                "Planning reason": row["planning_status"],
            }
        )

    st.markdown("#### Decision explanations")
    st.dataframe(
        pd.DataFrame(explanations),
        use_container_width=True,
        hide_index=True,
    )

    st.download_button(
        "Download intervention plan",
        data=plan.to_csv(index=False).encode("utf-8-sig"),
        file_name="civicpriority_intervention_plan.csv",
        mime="text/csv",
    )


with map_tab:
    st.markdown("### Geographic distribution")

    if {"latitude", "longitude"}.issubset(historical.columns):
        map_df = historical.dropna(
            subset=["latitude", "longitude"]
        ).copy()

        map_df = map_df[
            map_df["latitude"].between(-90, 90)
            & map_df["longitude"].between(-180, 180)
        ]

        if not map_df.empty:
            st.caption(
                "Locations represent recorded complaint coordinates."
            )

            st.map(
                map_df.rename(
                    columns={
                        "latitude": "lat",
                        "longitude": "lon",
                    }
                )[["lat", "lon"]]
            )

            st.write(f"Mapped records: {len(map_df):,}")
        else:
            st.info("No valid coordinates match the current filters.")
    else:
        st.info("Coordinates are unavailable in the historical dataset.")


with methodology_tab:
    st.markdown("### Data provenance and model limitations")

    st.write(
        "**Historical dataset:** Bengaluru complaint records spanning "
        "2019–2022, analyzed using historical review signals."
    )

    st.write(
        "**Six-factor scoring:** demonstrated on a separate illustrative "
        "sample dataset. Weights are user-adjustable and are not calibrated "
        "against verified outcomes."
    )

    st.write(
        "**Urgency score:** combines severity, population affected, "
        "recurrence, duration and geographic context using the selected "
        "relative weights for those five factors."
    )

    st.write(
        "**Overall priority score:** combines all six factors using the "
        "selected weights normalized by their total."
    )

    st.write(
        "**Resource feasibility:** uses a provisional inverse-scale score "
        "derived from estimated cost, crew requirements and equipment "
        "requirements. Lower resource burden generally gives a higher "
        "feasibility score."
    )

    st.write(
        "**Planning:** selects a feasible combination under budget, crew "
        "and equipment limits. It does not schedule work over time or "
        "model crew skills, travel time, dependencies or emergencies."
    )

    st.write(
        "**Known data gaps:** verified severity, affected population, "
        "current status, repair cost, crew requirements, equipment "
        "requirements and validated emergency labels."
    )


st.divider()

st.caption(
    "CivicPriority | Explainable infrastructure decision support | "
    "Prototype, not a live emergency-response system"
)
