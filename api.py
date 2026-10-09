
from pathlib import Path
from typing import Any

import math
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / "data" / "ranked_real_issues.csv"

app = FastAPI(
    title="CivicPriority API",
    description="Historical civic complaints, geographic records, scoring and intervention planning.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "https://civicpriority.onrender.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

historical_df = None


def clean_value(value: Any):
    if value is None:
        return None

    if pd.isna(value):
        return None

    if hasattr(value, "item"):
        value = value.item()

    if isinstance(value, float) and not math.isfinite(value):
        return None

    if hasattr(value, "isoformat"):
        return value.isoformat()

    return value


def clean_records(df: pd.DataFrame):
    return [
        {str(key): clean_value(value) for key, value in row.items()}
        for row in df.to_dict(orient="records")
    ]


def load_historical():
    global historical_df

    if historical_df is not None:
        return historical_df

    if not DATA_PATH.exists():
        raise HTTPException(
            status_code=500,
            detail=f"Historical CSV not found at {DATA_PATH}",
        )

    df = pd.read_csv(DATA_PATH, low_memory=False)

    if df.empty:
        raise HTTPException(
            status_code=500,
            detail="Historical CSV exists but contains no records.",
        )

    df.columns = [str(column).strip() for column in df.columns]
    historical_df = df
    return historical_df


def find_column(df, candidates):
    lookup = {str(column).strip().lower(): column for column in df.columns}

    for candidate in candidates:
        found = lookup.get(candidate.lower())
        if found is not None:
            return found

    return None


def normalized_record(row, columns):
    result = dict(row)

    aliases = {
        "_id": ["record_id", "issue_id", "complaint_id", "request_id", "id"],
        "_title": ["title", "complaint_title", "description", "subject"],
        "_category": ["category_title", "category", "issue_type", "complaint_type"],
        "_subcategory": ["sub_category_title", "subcategory", "sub_category"],
        "_status": ["complaint_status_title", "status", "state"],
        "_ward": ["ward_name", "ward", "ward_no", "ward_id", "zone"],
        "_date": ["created_at", "date", "created_date", "timestamp", "complaint_date"],
        "_score": ["historical_review_score", "priority_score", "review_score", "score"],
    }

    for normalized_name, candidates in aliases.items():
        source_column = find_column(
            pd.DataFrame(columns=columns),
            candidates,
        )

        result[normalized_name] = (
            clean_value(row.get(source_column))
            if source_column is not None
            else None
        )

    latitude_column = find_column(
        pd.DataFrame(columns=columns),
        ["latitude", "lat", "complaint_latitude", "y"],
    )

    longitude_column = find_column(
        pd.DataFrame(columns=columns),
        ["longitude", "lon", "lng", "complaint_longitude", "x"],
    )

    latitude = clean_value(row.get(latitude_column)) if latitude_column else None
    longitude = clean_value(row.get(longitude_column)) if longitude_column else None

    try:
        latitude = float(latitude) if latitude is not None else None
        longitude = float(longitude) if longitude is not None else None
    except (ValueError, TypeError):
        latitude = None
        longitude = None

    result["_latitude"] = latitude
    result["_longitude"] = longitude
    result["_has_coordinates"] = (
        latitude is not None
        and longitude is not None
        and -90 <= latitude <= 90
        and -180 <= longitude <= 180
    )

    if not result.get("_category"):
        result["_category"] = "Uncategorized (missing category)"

    if not result.get("_status"):
        result["_status"] = "Unknown"

    return result


class ScoreRequest(BaseModel):
    issues: list[dict] | None = None


class PlanRequest(BaseModel):
    budget: float = Field(ge=0)
    available_crews: int = Field(ge=0)
    available_equipment: int = Field(ge=0)
    issues: list[dict] | None = None


@app.get("/")
def root():
    return {
        "name": "CivicPriority API",
        "docs": "/docs",
        "health": "/api/health",
        "historical": "/api/historical",
        "analytics": "/api/historical/analytics",
        "map": "/api/historical/map",
    }


@app.get("/api/health")
def health():
    df = load_historical()

    return {
        "status": "ok",
        "service": "CivicPriority API",
        "historical_records": int(len(df)),
        "source_file": DATA_PATH.name,
        "columns_available": df.columns.tolist(),
    }


@app.get("/api/historical/schema")
def historical_schema():
    df = load_historical()

    return {
        "total_records": int(len(df)),
        "columns": [
            {
                "name": str(column),
                "dtype": str(df[column].dtype),
                "non_null_count": int(df[column].notna().sum()),
                "null_count": int(df[column].isna().sum()),
                "sample_values": [
                    clean_value(value)
                    for value in df[column].dropna().head(3).tolist()
                ],
            }
            for column in df.columns
        ],
    }


@app.get("/api/historical")
def get_historical(
    limit: int = Query(default=500, ge=1, le=20000),
    offset: int = Query(default=0, ge=0),
    category: str | None = None,
    status: str | None = None,
    search: str | None = None,
    min_score: float | None = None,
    max_score: float | None = None,
):
    df = load_historical()
    filtered = df.copy()

    category_column = find_column(
        filtered,
        ["category_title", "category", "issue_type", "complaint_type"],
    )

    status_column = find_column(
        filtered,
        ["complaint_status_title", "status", "state"],
    )

    score_column = find_column(
        filtered,
        ["historical_review_score", "priority_score", "review_score", "score"],
    )

    if category and category_column:
        filtered = filtered[
            filtered[category_column].fillna(
                "Uncategorized (missing category)"
            ).astype(str).str.casefold() == category.casefold()
        ]

    if status and status_column:
        filtered = filtered[
            filtered[status_column].fillna("Unknown").astype(str).str.casefold()
            == status.casefold()
        ]

    if search:
        search_text = search.casefold()
        mask = filtered.astype(str).apply(
            lambda column: column.str.casefold().str.contains(
                search_text,
                regex=False,
                na=False,
            )
        ).any(axis=1)
        filtered = filtered[mask]

    if score_column and (min_score is not None or max_score is not None):
        scores = pd.to_numeric(filtered[score_column], errors="coerce")

        if min_score is not None:
            filtered = filtered[scores >= min_score]
            scores = pd.to_numeric(filtered[score_column], errors="coerce")

        if max_score is not None:
            filtered = filtered[scores <= max_score]

    total_filtered = len(filtered)
    page = filtered.iloc[offset:offset + limit]

    records = [
        normalized_record(row, df.columns)
        for row in page.to_dict(orient="records")
    ]

    return {
        "total": int(len(df)),
        "filtered_total": int(total_filtered),
        "limit": limit,
        "offset": offset,
        "returned": len(records),
        "columns": df.columns.tolist(),
        "records": records,
    }


@app.get("/api/historical/map")
def historical_map(
    limit: int = Query(default=20000, ge=1, le=20000),
    category: str | None = None,
    status: str | None = None,
    min_score: float | None = None,
    max_score: float | None = None,
):
    response = get_historical(
        limit=limit,
        offset=0,
        category=category,
        status=status,
        min_score=min_score,
        max_score=max_score,
    )

    points = [
        record
        for record in response["records"]
        if record["_has_coordinates"]
    ]

    return {
        "total_records": response["total"],
        "filtered_records": response["filtered_total"],
        "returned_records": response["returned"],
        "records_with_coordinates": len(points),
        "records_without_coordinates": response["returned"] - len(points),
        "points": points,
    }


@app.get("/api/historical/analytics")
def historical_analytics():
    df = load_historical()

    category_column = find_column(
        df,
        ["category_title", "category", "issue_type", "complaint_type"],
    )

    status_column = find_column(
        df,
        ["complaint_status_title", "status", "state"],
    )

    score_column = find_column(
        df,
        ["historical_review_score", "priority_score", "review_score", "score"],
    )

    date_column = find_column(
        df,
        ["created_at", "date", "created_date", "timestamp", "complaint_date"],
    )

    category_counts = {}
    status_counts = {}

    if category_column:
        category_counts = (
            df[category_column]
            .fillna("Uncategorized (missing category)")
            .astype(str)
            .value_counts()
            .to_dict()
        )

    if status_column:
        status_counts = (
            df[status_column]
            .fillna("Unknown")
            .astype(str)
            .value_counts()
            .to_dict()
        )

    scores = (
        pd.to_numeric(df[score_column], errors="coerce").dropna()
        if score_column
        else pd.Series(dtype=float)
    )

    dates = (
        pd.to_datetime(df[date_column], errors="coerce").dropna()
        if date_column
        else pd.Series(dtype="datetime64[ns]")
    )

    return {
        "total_records": int(len(df)),
        "unique_categories": int(df[category_column].nunique(dropna=True))
        if category_column else 0,
        "missing_categories": int(df[category_column].isna().sum())
        if category_column else None,
        "category_counts": category_counts,
        "status_counts": status_counts,
        "score": {
            "column": score_column,
            "count": int(scores.count()),
            "min": float(scores.min()) if not scores.empty else None,
            "max": float(scores.max()) if not scores.empty else None,
            "mean": float(scores.mean()) if not scores.empty else None,
            "median": float(scores.median()) if not scores.empty else None,
        },
        "date_range": {
            "column": date_column,
            "start": dates.min().isoformat() if not dates.empty else None,
            "end": dates.max().isoformat() if not dates.empty else None,
        },
        "columns_available": df.columns.tolist(),
    }
