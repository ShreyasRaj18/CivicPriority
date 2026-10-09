
from pathlib import Path
import re

import pandas as pd


ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "data" / "processed_infrastructure_issues.csv"


def load_real_data():
    if not DATA_FILE.exists():
        raise FileNotFoundError(f"Dataset not found: {DATA_FILE}")

    df = pd.read_csv(
        DATA_FILE,
        encoding="utf-8-sig",
        low_memory=False
    )

    return df


def flag_suspicious_categories(df):
    df = df.copy()

    required = [
        "title",
        "category_title",
        "sub_category_title"
    ]

    missing = [
        column for column in required
        if column not in df.columns
    ]

    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    def normalize(value):
        if pd.isna(value):
            return ""

        text = str(value).lower()
        text = re.sub(r"[^a-z0-9\s]", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        text = re.sub(r"\bpot\s+holes?\b", "pothole", text)
        text = re.sub(r"\bpatholes?\b", "pothole", text)
        text = re.sub(r"\bstreet\s+lights?\b", "streetlight", text)
        text = re.sub(r"\bspeed\s+breakers?\b", "speedbreaker", text)

        return text

    topic_patterns = {
        "streetlight": (
            r"streetlight|street lamp|lamp post|bulb|"
            r"illumination|lighting"
        ),
        "road": (
            r"pothole|road|footpath|pavement|sidewalk|"
            r"asphalt|tarring|speedbreaker|crater|"
            r"kutcha road|unpaved road"
        ),
        "traffic": (
            r"traffic signal|traffic jam|congestion|parking|"
            r"parked car|vehicle blocking|zebra crossing|"
            r"bike lane|traffic police"
        ),
        "garbage": (
            r"garbage|rubbish|litter|waste dump|garbage dump|"
            r"dustbin|debris|waste collection|bad smell|foul smell"
        ),
        "water": (
            r"water leakage|water leak|water scarcity|"
            r"water supply|water pipeline|no water|water pressure"
        ),
        "drainage": (
            r"drainage|drain|sewage|sewer|waterlogging|"
            r"water logging|manhole|desilting|drain blockage"
        ),
        "electricity": (
            r"power cut|power outage|electricity supply|"
            r"electric wire|transformer|voltage problem"
        )
    }

    category_patterns = {
        "streetlight": r"streetlights?|street lighting",
        "road": r"mobility|roads and footpaths|road infrastructure|pwd",
        "traffic": r"traffic and road safety",
        "garbage": (
            r"garbage|waste|unsanitary|yellow spot|"
            r"solid waste|sanitation"
        ),
        "water": r"water supply|water services",
        "drainage": r"storm water drains|sewerage systems",
        "electricity": r"electricity|power supply"
    }

    def find_topics(text):
        return {
            topic
            for topic, pattern in topic_patterns.items()
            if re.search(r"\b(?:" + pattern + r")\b", text)
        }

    reasons = []

    for _, row in df.iterrows():
        title = normalize(row["title"])
        category = normalize(row["category_title"])
        subcategory = normalize(row["sub_category_title"])

        if not title or title in {"checking", "test", "testing"}:
            reasons.append("Insufficient information in title; ")
            continue

        assigned_topics = {
            topic
            for topic, pattern in category_patterns.items()
            if re.search(r"\b(?:" + pattern + r")\b", category)
        }

        if not assigned_topics:
            reasons.append("")
            continue

        title_topics = find_topics(title)
        subcategory_topics = find_topics(subcategory)
        expected_topics = assigned_topics | subcategory_topics

        if title_topics & expected_topics:
            reasons.append("")
            continue

        conflicting_topics = title_topics - expected_topics

        if conflicting_topics:
            reasons.append(
                "Possible category mismatch: "
                + ", ".join(sorted(conflicting_topics))
                + "; "
            )
        elif len(title.split()) < 2:
            reasons.append("Insufficient information in title; ")
        else:
            reasons.append("")

    df["review_reason"] = reasons
    df["needs_category_review"] = df["review_reason"].ne("")

    return df


if __name__ == "__main__":
    data = load_real_data()
    reviewed = flag_suspicious_categories(data)
    flagged = reviewed[reviewed["needs_category_review"]]

    print(f"Total records: {len(reviewed):,}")
    print(f"Flagged for review: {len(flagged):,}")

    if len(reviewed):
        percentage = len(flagged) / len(reviewed) * 100
        print(f"Flagged percentage: {percentage:.2f}%")
