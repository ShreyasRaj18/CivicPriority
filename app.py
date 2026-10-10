from pathlib import Path
import html

import pandas as pd
import plotly.express as px
import pydeck as pdk
import streamlit as st
import re

ROOT = Path(__file__).resolve().parent
REAL_DATA_FILE = ROOT / "data" / "ranked_real_issues.csv"
UNCATEGORIZED = "Uncategorized (missing category)"
MAP_LAYER_ID = "complaint_points"


st.set_page_config(
    page_title="CivicPriority | Bengaluru",
    page_icon="🏙️",
    layout="wide",
    initial_sidebar_state="expanded",
)


st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'DM Sans', sans-serif;
    }

    h1, h2, h3, h4, h5, h6 {
        font-family: 'DM Sans', sans-serif !important;
        letter-spacing: -.02em;
    }

    .block-container {
        max-width: 1440px;
        padding-top: 1.1rem;
        padding-bottom: 2.5rem;
    }
    :root { color-scheme: light; }
    [data-testid="stAppViewContainer"] { background: #f7f8fc; color: #17213b; }
    [data-testid="stHeader"] { background: rgba(247,248,252,.92); }
    [data-testid="stSidebar"] { background: #ffffff; border-right: 1px solid #e7eaf2; }
    [data-testid="stMetric"] {
        background: #ffffff;
        border: 1px solid #e6e9f2;
        padding: 1rem 1.1rem;
        border-radius: 16px;
        box-shadow: 0 2px 10px rgba(20,32,70,.035);
    }
    div[data-testid="stDataFrame"] {
        border: 1px solid #e6e9f2;
        border-radius: 14px;
        overflow: hidden;
        background: #ffffff;
    }
    div[data-testid="stPlotlyChart"] {
        background: #ffffff;
        border: 1px solid #e6e9f2;
        border-radius: 16px;
        padding: .35rem;
    }

    .hero-panel {
        padding: 2rem 2.1rem;
        border-radius: 22px;
        color: white;
        background: linear-gradient(118deg, #101d54 0%, #2449bd 58%, #5577ef 100%);
        margin-bottom: 1rem;
        box-shadow: 0 12px 32px rgba(27,57,150,.16);
    }

    .hero-panel h1 {
        color: white !important;
        margin-bottom: .35rem;
    }

    .hero-panel p {
        color: rgba(255,255,255,.9);
        margin-bottom: 0;
        font-size: 1rem;
    }

    [data-testid="stMetric"] {
        background: #f6f7ff;
        border: 1px solid #e3e7ff;
        padding: 1rem;
        border-radius: 12px;
    }

    [data-testid="stMetricLabel"] {
        color: #505776;
    }

    [data-testid="stMetricValue"] {
        color: #0719b8;
    }

    div[data-testid="stDataFrame"] {
        border: 1px solid #e5e7eb;
        border-radius: 10px;
        overflow: hidden;
    }

    .info-note {
        border-left: 4px solid #0719b8;
        background: #f4f6ff;
        padding: .85rem 1rem;
        border-radius: 0 9px 9px 0;
        color: #333b60;
        margin: .7rem 0 1rem;
    }

    div.stButton > button[kind="primary"] {
        background: #0719b8;
        border-color: #0719b8;
    }
    [data-testid="stPydeckChart"] { cursor: crosshair; }
    .map-instructions { display:flex; flex-wrap:wrap; gap:.55rem; margin:.45rem 0 .8rem; }
    .map-instructions span { background:#fff; border:1px solid #dce3f1; border-radius:999px; padding:.35rem .7rem; color:#34415e; font-size:.86rem; }
    .selection-pulse { border:1px solid #cbd8ff; background:#f3f6ff; border-radius:12px; padding:.8rem 1rem; animation: selectionFade 1.2s ease-out 1; }
    @keyframes selectionFade { 0% { background:#dce6ff; box-shadow:0 0 0 4px rgba(49,87,213,.12); } 100% { background:#f3f6ff; box-shadow:0 0 0 0 rgba(49,87,213,0); } }
    </style>
    """,
    unsafe_allow_html=True,
)
def clean_title(value):
    if pd.isna(value):
        return "Untitled complaint"

    title = html.unescape(str(value)).strip()
    title = re.sub(r"\s+", " ", title)

    if not title:
        return "Untitled complaint"

    if len(title) < 4:
        return "Unclear complaint title"

    if re.fullmatch(r"[\W_]+", title):
        return "Unclear complaint title"

    compact = re.sub(r"[^A-Za-z0-9]", "", title)
    if re.search(r"(?i)(?:[a-z]\d){3,}|(?:\d[a-z]){3,}", compact):
        return "Unclear complaint title"
    if re.fullmatch(r"[A-Za-z0-9]{8,}", compact) and not re.search(r"[aeiou]", compact, re.I):
        return "Unclear complaint title"
    return title

@st.cache_data(show_spinner="Loading historical complaint records…")
def load_real_data(path: str, modified_time: float) -> pd.DataFrame:
    frame = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)

    for column in ["priority_score", "priority_rank", "latitude", "longitude", "recurrence_count"]:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")

    if "title" in frame.columns:
        frame["title"] = frame["title"].apply(clean_title)

    if "created_at" in frame.columns:
        frame["created_at"] = pd.to_datetime(frame["created_at"], errors="coerce")

    if "category_title" in frame.columns:
        frame["category_title"] = (
            frame["category_title"].fillna(UNCATEGORIZED).replace("", UNCATEGORIZED)
        )

    if "complaint_status_title" in frame.columns:
        frame["complaint_status_title"] = (
            frame["complaint_status_title"].fillna("Unknown").replace("", "Unknown")
        )

    return frame


def fmt_count(value) -> str:
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return "0"


def available_columns(frame: pd.DataFrame, columns: list[str]) -> list[str]:
    return [column for column in columns if column in frame.columns]


def clean_text(value, fallback="Not recorded") -> str:
    if value is None:
        return fallback
    try:
        if pd.isna(value):
            return fallback
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    return text if text else fallback


def selection_from_event(event, layer_id: str):
    """Read a selected map object across Streamlit's supported selection-state shapes."""
    if event is None:
        return None

    selection = getattr(event, "selection", None)
    if selection is None and isinstance(event, dict):
        selection = event.get("selection", event)

    objects = getattr(selection, "objects", None)
    if objects is None and isinstance(selection, dict):
        objects = selection.get("objects", {})

    if not isinstance(objects, dict):
        return None

    candidates = objects.get(layer_id, [])
    if isinstance(candidates, dict):
        candidates = [candidates]

    if not candidates:
        for value in objects.values():
            if isinstance(value, dict):
                candidates = [value]
                break
            if isinstance(value, list) and value and isinstance(value[0], dict):
                candidates = value
                break

    return candidates[0] if candidates else None


def make_map_frame(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()

    if not {"latitude", "longitude"}.issubset(result.columns):
        return pd.DataFrame()

    result["latitude"] = pd.to_numeric(result["latitude"], errors="coerce")
    result["longitude"] = pd.to_numeric(result["longitude"], errors="coerce")
    result = result.dropna(subset=["latitude", "longitude"])
    result = result[
        result["latitude"].between(12.70, 13.25)
        & result["longitude"].between(77.35, 77.85)
    ].copy()

    if result.empty:
        return result

    if "record_id" in result.columns:
        result["map_record_id"] = result["record_id"].astype(str)
    else:
        result["map_record_id"] = result.index.astype(str)

    if "title" in result.columns:
        result["map_title"] = result["title"].apply(clean_title)
    else:
        result["map_title"] = "Civic complaint"
    result["map_category"] = result["category_title"].fillna(UNCATEGORIZED).astype(str)
    result["map_status"] = result["complaint_status_title"].fillna("Unknown").astype(str)
    result["map_ward"] = (
        result["ward_title"].fillna("Not recorded").astype(str)
        if "ward_title" in result.columns
        else "Not recorded"
    )
    result["map_score"] = pd.to_numeric(result["priority_score"], errors="coerce")
    result["map_score"] = result["map_score"].fillna(-1)
    result["point_color"] = result["map_score"].apply(
        lambda score: [229, 72, 77, 220] if score >= 75 else [49, 109, 255, 210]
    )

    return result


if not REAL_DATA_FILE.exists():
    st.error(
        "The historical dataset could not be found. Ensure "
        "data/ranked_real_issues.csv exists in the project."
    )
    st.stop()

try:
    real_df = load_real_data(str(REAL_DATA_FILE), REAL_DATA_FILE.stat().st_mtime)
except Exception:
    st.error(
        "CivicPriority could not load the historical dataset. "
        "Check that the CSV exists and is readable."
    )
    st.stop()


required_columns = [
    "priority_score",
    "priority_rank",
    "category_title",
    "complaint_status_title",
]
missing_columns = [column for column in required_columns if column not in real_df.columns]

if missing_columns:
    st.error("The historical dataset is missing required fields: " + ", ".join(missing_columns))
    st.stop()


categories = sorted(real_df["category_title"].dropna().astype(str).unique().tolist())
statuses = sorted(real_df["complaint_status_title"].dropna().astype(str).unique().tolist())

score_min = float(real_df["priority_score"].min())
score_max = float(real_df["priority_score"].max())


st.sidebar.markdown("## CivicPriority")
st.sidebar.caption("Bengaluru civic complaint explorer")
st.sidebar.divider()

selected_categories = st.sidebar.multiselect(
    "Complaint categories",
    options=categories,
    default=categories,
    help="Choose which types of complaints appear in the map, charts and tables.",
)

selected_statuses = st.sidebar.multiselect(
    "Status in historical records",
    options=statuses,
    default=statuses,
    help="These are historical statuses from the source dataset, not live updates.",
)

score_range = st.sidebar.slider(
    "Historical priority score",
    min_value=0.0,
    max_value=100.0,
    value=(score_min, score_max),
    step=1.0,
    help="Show records in this historical score range.",
)

if st.sidebar.button("Reset filters", use_container_width=True):
    for key in [
        "selected_map_record_id",
        "complaint_map",
        "category_filter",
        "status_filter",
        "score_filter",
    ]:
        st.session_state.pop(key, None)
    st.rerun()


historical = real_df[
    real_df["category_title"].isin(selected_categories)
    & real_df["complaint_status_title"].isin(selected_statuses)
    & real_df["priority_score"].between(score_range[0], score_range[1])
].copy()


st.markdown(
    """
    <div class="hero-panel">
      <h1>CivicPriority</h1>
      <p>Explore where civic complaints were recorded, understand historical patterns, and compare the issues that ranked highest in the dataset.</p>
    </div>
    """,
    unsafe_allow_html=True,
)
st.caption("Bengaluru historical complaints · 2019–2022 · Historical decision-support tool")


overview_tab, records_tab, about_tab = st.tabs(
    ["City overview", "Explore complaints", "About the data"]
)


with overview_tab:
    open_count = int(
        historical["complaint_status_title"].astype(str).str.lower().eq("open").sum()
    )
    mean_score = historical["priority_score"].mean()
    category_count = historical["category_title"].nunique()
    map_df = make_map_frame(historical)

    metric1, metric2, metric3, metric4 = st.columns(4)
    metric1.metric("Complaints in view", fmt_count(len(historical)))
    metric2.metric("Recorded as open", fmt_count(open_count))
    metric3.metric("Categories", fmt_count(category_count))
    metric4.metric(
        "Average historical score",
        f"{mean_score:.1f}/100" if pd.notna(mean_score) else "—",
    )

    st.markdown(
        '<div class="info-note">This is historical information, not live incident tracking. A high score means a record ranked highly under the historical review method; it does not confirm that the problem is still present.</div>',
        unsafe_allow_html=True,
    )

    map_heading, map_metric = st.columns([3, 1])
    with map_heading:
        st.subheader("Explore complaint locations")
        st.caption("Select an individual dot to inspect the historical complaint behind it.")
        st.markdown(
            '<div class="map-instructions"><span>① Hover over a dot to preview it</span><span>② Click a dot to select it</span><span>③ Read the full record below the map</span><span>Scroll to zoom · Map stays focused on Bengaluru</span></div>',
            unsafe_allow_html=True,
        )
    with map_metric:
        map_metric.metric("Mapped records", fmt_count(len(map_df)))

    selected_map_record = None

    if not map_df.empty:
        tooltip = {
            "html": """
                <div style="font-family: sans-serif; padding: 5px; min-width: 220px;">
                  <b>{map_title}</b><br/>
                  <span>Category: {map_category}</span><br/>
                  <span>Status: {map_status}</span><br/>
                  <span>Ward: {map_ward}</span><br/>
                  <span>Historical score: {map_score}</span><br/>
                  <span>Record ID: {map_record_id}</span>
                </div>
            """,
            "style": {
                "backgroundColor": "#ffffff",
                "color": "#111827",
                "fontSize": "12px",
                "padding": "10px",
            },
        }

        selected_id_for_map = str(st.session_state.get("selected_map_record_id", ""))
        map_df["is_selected"] = map_df["map_record_id"].astype(str).eq(selected_id_for_map)
        map_df["point_radius"] = map_df["is_selected"].apply(lambda selected: 115 if selected else 65)
        map_df["point_color"] = map_df.apply(
            lambda row: [18, 43, 150, 255] if row["is_selected"] else ([229, 72, 77, 220] if row["map_score"] >= 75 else [49, 109, 255, 210]),
            axis=1,
        )

        layer = pdk.Layer(
            "ScatterplotLayer",
            id=MAP_LAYER_ID,
            data=map_df,
            get_position="[longitude, latitude]",
            get_fill_color="point_color",
            get_radius="point_radius",
            radius_min_pixels=4,
            radius_max_pixels=10,
            pickable=True,
            auto_highlight=True,
            stroked=True,
            get_line_color=[255, 255, 255, 220],
            line_width_min_pixels=1,
        )

        view_state = pdk.ViewState(
            latitude=12.9716,
            longitude=77.5946,
            zoom=10.5,
            min_zoom=9,
            max_zoom=16,
            pitch=0,
        )

        deck = pdk.Deck(
            layers=[layer],
            initial_view_state=view_state,
            tooltip=tooltip,
            map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
            views=[
                pdk.View(
                    type="MapView",
                    controller={
                        "dragPan": False,
                        "scrollZoom": True,
                        "doubleClickZoom": True,
                        "touchZoom": True,
                        "dragRotate": False,
                        "keyboard": False,
                    },
                )
            ],
        )

        try:
            map_event = st.pydeck_chart(
                deck,
                use_container_width=True,
                height=570,
                key="complaint_map",
                on_select="rerun",
                selection_mode="single-object",
            )
            clicked_record = selection_from_event(map_event, MAP_LAYER_ID)
        except Exception:
            st.error(
                "Map point selection is not supported by the installed Streamlit version. "
                "Run: pip install --upgrade streamlit pydeck, then restart the app."
            )
            clicked_record = None

        if clicked_record:
            selected_id = str(
                clicked_record.get(
                    "map_record_id",
                    clicked_record.get("record_id", ""),
                )
            )
            if selected_id:
                st.session_state["selected_map_record_id"] = selected_id

        saved_id = st.session_state.get("selected_map_record_id")
        if saved_id:
            matched = map_df[map_df["map_record_id"].astype(str) == str(saved_id)]
            if not matched.empty:
                selected_map_record = matched.iloc[0].to_dict()
            else:
                st.session_state.pop("selected_map_record_id", None)

        st.caption(
            "Blue points: historical score below 75 · Red points: historical score 75 or above. "
            "Colour represents the historical score only, not live danger."
        )

        if selected_map_record:
            st.divider()
            st.markdown('<div class="selection-pulse"><strong>Point selected</strong> · Complaint details are shown below. The selected point is highlighted in dark blue on the map.</div>', unsafe_allow_html=True)
            st.markdown("### Selected complaint")
            st.caption(
                "This is the record attached to the point you selected. "
                "Check current conditions before acting on historical information."
            )

            title = clean_title(selected_map_record.get("map_title", "Civic complaint"))
            st.markdown(f"#### {title}")

            detail1, detail2, detail3 = st.columns(3)
            detail1.write("**Category**")
            detail1.write(clean_text(selected_map_record.get("map_category")))
            detail2.write("**Status when recorded**")
            detail2.write(clean_text(selected_map_record.get("map_status")))
            score_value = float(selected_map_record.get("map_score", -1))
            detail3.metric(
                "Historical score",
                f"{score_value:.1f}/100" if score_value >= 0 else "Not available",
            )

            detail4, detail5, detail6 = st.columns(3)
            detail4.write("**Record ID**")
            detail4.write(clean_text(selected_map_record.get("map_record_id")))
            detail5.write("**Ward / area**")
            detail5.write(clean_text(selected_map_record.get("map_ward")))
            detail6.write("**Date recorded**")
            detail6.write(clean_text(selected_map_record.get("created_at")))

            location = selected_map_record.get("location")
            if location is None or pd.isna(location) or not str(location).strip():
                location = selected_map_record.get("address")
            st.write(f"**Reported location:** {clean_text(location)}")

            description = selected_map_record.get("description")
            if description is None or pd.isna(description) or not str(description).strip():
                description = title
            st.write("**What was reported**")
            st.write(clean_text(description))

            recurrence = selected_map_record.get("recurrence_count")
            if recurrence is not None and not pd.isna(recurrence):
                st.write(f"**Recurrence count in source data:** {clean_text(recurrence)}")

            explanation = selected_map_record.get("priority_explanation")
            if explanation is not None and not pd.isna(explanation) and str(explanation).strip():
                with st.expander("Why did this record receive this score?"):
                    st.write(str(explanation))
            else:
                st.caption(
                    "A detailed score explanation is not available for this record."
                )

            if score_value >= 75:
                st.warning(
                    "This record ranked highly in the historical review. "
                    "That does not confirm the problem is still present or urgent today."
                )
            elif score_value >= 0:
                st.info(
                    "This record's historical score is below 75. "
                    "The score is for comparison, not a live risk rating."
                )

            if st.button("Clear selected complaint"):
                st.session_state.pop("selected_map_record_id", None)
                st.rerun()
        else:
            st.info("Select a point on the map to see its complaint details here.")
    else:
        st.info("No valid coordinates match the current filters.")

    left, right = st.columns(2)

    with left:
        st.subheader("Most common complaint categories")
        category_counts = (
            historical["category_title"]
            .value_counts()
            .head(10)
            .sort_values()
            .rename_axis("Category")
            .reset_index(name="Complaints")
        )

        if not category_counts.empty:
            figure = px.bar(
                category_counts,
                x="Complaints",
                y="Category",
                orientation="h",
                labels={"Complaints": "Number of complaints", "Category": ""},
                color_discrete_sequence=["#0719b8"],
            )
            figure.update_layout(
                height=380,
                margin=dict(l=12, r=18, t=18, b=12),
                showlegend=False,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(family="DM Sans, sans-serif", color="#27324b"),
                xaxis=dict(showgrid=True, gridcolor="#edf0f6", zeroline=False),
                yaxis=dict(showgrid=False),
            )
            st.plotly_chart(figure, use_container_width=True)
        else:
            st.info("No category data matches these filters.")

    with right:
        st.subheader("Recorded complaint statuses")
        status_counts = (
            historical["complaint_status_title"]
            .value_counts()
            .rename_axis("Status")
            .reset_index(name="Complaints")
        )

        if not status_counts.empty:
            figure = px.pie(
                status_counts,
                names="Status",
                values="Complaints",
                hole=0.55,
                color_discrete_sequence=[
                    "#0719b8",
                    "#4f67e8",
                    "#8b9aff",
                    "#c2caff",
                    "#e3e7ff",
                ],
            )
            figure.update_layout(
                height=380,
                margin=dict(l=12, r=12, t=18, b=12),
                legend_title_text="",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(family="DM Sans, sans-serif", color="#27324b"),
            )
            st.plotly_chart(figure, use_container_width=True)
        else:
            st.info("No status data matches these filters.")

    st.subheader("Highest-ranked complaints")
    top_columns = available_columns(
        historical,
        [
            "priority_rank",
            "record_id",
            "title",
            "category_title",
            "ward_title",
            "complaint_status_title",
            "priority_score",
        ],
    )
    top = historical.sort_values(
        "priority_score", ascending=False, na_position="last"
    ).head(12)

    if not top.empty and top_columns:
        st.dataframe(
            top[top_columns],
            use_container_width=True,
            hide_index=True,
            height=380,
            column_config={
                "priority_score": st.column_config.NumberColumn(
                    "Historical score", format="%.2f / 100"
                ),
                "priority_rank": st.column_config.NumberColumn("Rank", format="%d"),
                "title": st.column_config.TextColumn("Complaint", width="large"),
            },
        )

    st.download_button(
        "Download records in this view",
        data=historical.to_csv(index=False).encode("utf-8-sig"),
        file_name="civicpriority_historical_records.csv",
        mime="text/csv",
    )


with records_tab:
    st.subheader("Explore complaints")
    st.write(
        "Search historical records, review what was reported, and download the results."
    )

    search_text = st.text_input(
        "Search complaints",
        placeholder="Try a title, category, ward, location, or record ID",
    )

    records_view = historical.copy()
    searchable_columns = available_columns(
        records_view,
        [
            "record_id",
            "title",
            "description",
            "category_title",
            "sub_category_title",
            "ward_title",
            "location",
            "address",
            "complaint_status_title",
        ],
    )

    if search_text.strip() and searchable_columns:
        matched = pd.Series(False, index=records_view.index)
        for column in searchable_columns:
            matched |= records_view[column].fillna("").astype(str).str.contains(
                search_text.strip(), case=False, regex=False
            )
        records_view = records_view[matched]

    records_view = records_view.sort_values(
        "priority_score", ascending=False, na_position="last"
    )
    st.caption(f"{len(records_view):,} matching records")

    display_columns = available_columns(
        records_view,
        [
            "priority_rank",
            "record_id",
            "title",
            "category_title",
            "sub_category_title",
            "ward_title",
            "complaint_status_title",
            "created_at",
            "priority_score",
            "priority_explanation",
            "location",
        ],
    )

    st.dataframe(
        records_view[display_columns],
        use_container_width=True,
        hide_index=True,
        height=520,
        column_config={
            "priority_score": st.column_config.NumberColumn(
                "Historical score", format="%.2f"
            ),
            "created_at": st.column_config.DatetimeColumn(
                "Recorded date", format="D MMM YYYY"
            ),
            "title": st.column_config.TextColumn("Complaint", width="large"),
            "priority_explanation": st.column_config.TextColumn(
                "Why it ranked here", width="large"
            ),
        },
    )

    st.download_button(
        "Download search results",
        data=records_view.to_csv(index=False).encode("utf-8-sig"),
        file_name="civicpriority_complaint_search.csv",
        mime="text/csv",
    )


with about_tab:
    st.subheader("About this information")

    st.markdown("#### Where does the data come from?")
    st.write(
        "This dashboard presents historical Bengaluru civic complaint records from 2019–2022. "
        "The status and location are the values recorded in the source dataset."
    )

    st.markdown("#### What does the historical score mean?")
    st.write(
        "The score is a rule-based ranking using recurrence, recorded status, age of the record, "
        "and ward-level complaint concentration. A higher score means the record ranked higher "
        "under that method. It is not a prediction of future incidents or a confirmation of current urgency."
    )

    st.markdown("#### What should I do with a high score?")
    st.write(
        "Use it to identify records worth reviewing. Confirm the location and whether the issue "
        "still exists before using the record to guide real-world decisions."
    )

    st.markdown("#### Data coverage")
    coordinate_count = 0
    if {"latitude", "longitude"}.issubset(real_df.columns):
        latitude = pd.to_numeric(real_df["latitude"], errors="coerce")
        longitude = pd.to_numeric(real_df["longitude"], errors="coerce")
        coordinate_count = int(
            (
                latitude.between(-90, 90)
                & longitude.between(-180, 180)
            ).fillna(False).sum()
        )

    metric1, metric2, metric3 = st.columns(3)
    metric1.metric("Historical records", fmt_count(len(real_df)))
    metric2.metric("Records with valid coordinates", fmt_count(coordinate_count))
    metric3.metric("Categories", fmt_count(real_df["category_title"].nunique()))


st.divider()
st.caption(
    "CivicPriority · Historical civic intelligence · Not a live emergency-response service"
)
