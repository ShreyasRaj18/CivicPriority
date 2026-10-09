
from pathlib import Path
import pandas as pd

# Project data location
DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "sample_issues.csv"

REQUIRED_COLUMNS = [
    "issue_id",
    "issue_type",
    "location",
    "severity",
    "population_affected",
    "recurrence",
    "duration_days",
    "geographic_importance",
    "estimated_cost",
    "crew_required",
    "equipment_required"
]


def load_issues(file_path=DATA_FILE):
    """Load infrastructure issues from a CSV file."""
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"Issue dataset not found: {path}")

    df = pd.read_csv(path)

    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    if df.empty:
        raise ValueError("The issue dataset is empty.")

    return df


def add_issue(issue, file_path=DATA_FILE):
    """Add a new infrastructure issue to the CSV dataset."""
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    new_issue = pd.DataFrame([issue])

    missing = [col for col in REQUIRED_COLUMNS if col not in new_issue.columns]
    if missing:
        raise ValueError(f"Missing required fields: {missing}")

    if path.exists():
        existing = load_issues(path)

        if issue["issue_id"] in existing["issue_id"].astype(str).values:
            raise ValueError("An issue with this ID already exists.")

        updated = pd.concat([existing, new_issue], ignore_index=True)
    else:
        updated = new_issue

    updated.to_csv(path, index=False)
    return updated
