
import unittest
import pandas as pd

from src.scoring import calculate_priority


class TestPriorityScoring(unittest.TestCase):
    def setUp(self):
        self.issues = pd.DataFrame(
            [
                {
                    "issue_id": "A",
                    "severity_score": 100,
                    "population_score": 100,
                    "recurrence_score": 100,
                    "duration_score": 100,
                    "geographic_score": 100,
                    "estimated_cost": 10000,
                    "crew_required": 1,
                    "equipment_required": 1,
                },
                {
                    "issue_id": "B",
                    "severity_score": 50,
                    "population_score": 50,
                    "recurrence_score": 50,
                    "duration_score": 50,
                    "geographic_score": 50,
                    "estimated_cost": 50000,
                    "crew_required": 3,
                    "equipment_required": 2,
                },
            ]
        )

    def test_scores_are_between_zero_and_100(self):
        result = calculate_priority(self.issues)
        self.assertTrue(
            result["priority_score"].between(0, 100).all()
        )

    def test_all_high_factors_produce_higher_urgency(self):
        result = calculate_priority(self.issues)
        issue_a = result[result["issue_id"] == "A"].iloc[0]
        issue_b = result[result["issue_id"] == "B"].iloc[0]
        self.assertGreater(
            issue_a["urgency_score"],
            issue_b["urgency_score"],
        )

    def test_resource_fields_are_required(self):
        incomplete = self.issues.drop(columns=["estimated_cost"])
        with self.assertRaises(ValueError):
            calculate_priority(incomplete)

    def test_negative_resource_values_are_rejected(self):
        invalid = self.issues.copy()
        invalid.loc[0, "estimated_cost"] = -1
        with self.assertRaises(ValueError):
            calculate_priority(invalid)


if __name__ == "__main__":
    unittest.main()

