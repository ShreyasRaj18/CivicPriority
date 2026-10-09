
import unittest
import pandas as pd

from src.processing import process_issues


class TestProcessing(unittest.TestCase):

    def setUp(self):
        self.issue = {
            "issue_id": "I001",
            "issue_type": "Damaged Road",
            "location": "Sector 5",
            "severity": 4,
            "population_affected": 1000,
            "recurrence": 3,
            "duration_days": 10,
            "geographic_importance": 4,
            "estimated_cost": 50000,
            "crew_required": 2,
            "equipment_required": 1
        }

    def test_score_stays_stable_when_new_issue_is_added(self):
        original = process_issues(pd.DataFrame([self.issue]))

        new_issue = self.issue.copy()
        new_issue.update({
            "issue_id": "I002",
            "severity": 5,
            "population_affected": 5000,
            "recurrence": 10,
            "duration_days": 60
        })

        combined = process_issues(
            pd.DataFrame([self.issue, new_issue])
        )

        original_score = original.iloc[0]["population_score"]
        combined_score = combined.loc[
            combined["issue_id"] == "I001",
            "population_score"
        ].iloc[0]

        self.assertEqual(original_score, combined_score)

    def test_normalized_scores_stay_between_zero_and_100(self):
        result = process_issues(pd.DataFrame([self.issue]))

        score_columns = [
            "severity_score",
            "population_score",
            "recurrence_score",
            "duration_score",
            "geographic_score"
        ]

        for column in score_columns:
            self.assertTrue(result[column].between(0, 100).all())


if __name__ == "__main__":
    unittest.main(verbosity=2)
