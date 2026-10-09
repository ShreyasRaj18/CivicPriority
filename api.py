
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.input_layer import load_issues
from src.processing import process_issues
from src.scoring import calculate_priority, explain_priority
from src.planner import plan_interventions

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

app = FastAPI(
    title="CivicPriority API",
    description="Urban Infrastructure Priority Engine API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ScoreRequest(BaseModel):
    issues: list[dict] | None = None


class PlanRequest(BaseModel):
    budget: float = Field(ge=0)
    available_crews: int = Field(ge=0)
    available_equipment: int = Field(ge=0)
    issues: list[dict] | None = None


def get_processed_issues():
    raw_issues = load_issues()
    return process_issues(raw_issues)


def get_ranked_issues(issues=None):
    if issues is None:
        issues = get_processed_issues()

    return calculate_priority(pd.DataFrame(issues))


def records_from_dataframe(df):
    clean_df = df.copy()
    clean_df = clean_df.astype(object)
    clean_df = clean_df.where(pd.notna(clean_df), None)
    return clean_df.to_dict(orient="records")


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "service": "CivicPriority API",
    }


@app.get("/api/historical")
def historical(limit: int = 100, offset: int = 0):
    if limit < 1 or limit > 1000 or offset < 0:
        raise HTTPException(
            status_code=400,
            detail="Limit must be 1-1000 and offset must be non-negative.",
        )

    file_path = DATA_DIR / "ranked_real_issues.csv"

    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Historical dataset was not found.",
        )

    df = pd.read_csv(file_path)

    return {
        "total": len(df),
        "limit": limit,
        "offset": offset,
        "records": records_from_dataframe(
            df.iloc[offset:offset + limit]
        ),
    }


@app.post("/api/score")
def score(request: ScoreRequest):
    try:
        if request.issues is None:
            ranked = get_ranked_issues()
        else:
            if not request.issues:
                raise HTTPException(
                    status_code=400,
                    detail="Provide at least one issue to score.",
                )

            ranked = get_ranked_issues(request.issues)

        records = records_from_dataframe(ranked)
        explanations = []

        for index, (_, row) in enumerate(ranked.iterrows()):
            explanation = explain_priority(row)
            explanations.append({
                "issue_id": str(row.get("issue_id", row.get("id", index))),
                "explanation": explanation,
            })

        return {
            "count": len(records),
            "issues": records,
            "explanations": explanations,
        }

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Unable to score issues: {exc}",
        ) from exc


@app.post("/api/plan")
def plan(request: PlanRequest):
    try:
        if request.issues is None:
            ranked = get_ranked_issues()
        else:
            if not request.issues:
                raise HTTPException(
                    status_code=400,
                    detail="Provide at least one issue to plan.",
                )

            ranked = get_ranked_issues(request.issues)

        result = plan_interventions(
            ranked,
            budget=request.budget,
            available_crews=request.available_crews,
            available_equipment=request.available_equipment,
        )

        if isinstance(result, pd.DataFrame):
            return {
                "issues": records_from_dataframe(result),
            }

        if isinstance(result, dict):
            response = {}

            for key, value in result.items():
                if isinstance(value, pd.DataFrame):
                    response[key] = records_from_dataframe(value)
                elif isinstance(value, pd.Series):
                    response[key] = records_from_dataframe(
                        value.to_frame().T
                    )
                elif hasattr(value, "item"):
                    response[key] = value.item()
                else:
                    response[key] = value

            return response

        return {"result": result}

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Unable to plan interventions: {exc}",
        ) from exc
