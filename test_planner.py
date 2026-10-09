
import unittest
import pandas as pd

from src.planner import plan_interventions


class TestInterventionPlanner(unittest.TestCase):

    def setUp(self):
        self.issues = pd.DataFrame([
            {
                "issue_id": "A",
                "priority_score": 80,
                "estimated_cost": 50000,
                "crew_required": 2,
                "equipment_required": 1,
            },
            {
                "issue_id": "B",
                "priority_score": 70,
                "estimated_cost": 30000,
                "crew_required": 2,
                "equipment_required": 1,
            },
            {
                "issue_id": "C",
                "priority_score": 60,
                "estimated_cost": 20000,
                "crew_required": 1,
                "equipment_required": 1,
            },
        ])

    def test_budget_is_never_exceeded(self):
        plan = plan_interventions(self.issues, 50000, 10, 10)
        selected = plan[plan["selected_for_intervention"]]
        self.assertLessEqual(selected["estimated_cost"].sum(), 50000)

    def test_crew_limit_is_never_exceeded(self):
        plan = plan_interventions(self.issues, 200000, 2, 10)
        selected = plan[plan["selected_for_intervention"]]
        self.assertLessEqual(selected["crew_required"].sum(), 2)

    def test_equipment_limit_is_never_exceeded(self):
        plan = plan_interventions(self.issues, 200000, 10, 1)
        selected = plan[plan["selected_for_intervention"]]
        self.assertLessEqual(selected["equipment_required"].sum(), 1)

    def test_finds_highest_value_feasible_combination(self):
        plan = plan_interventions(self.issues, 50000, 2, 1)
        selected = plan[plan["selected_for_intervention"]]
        self.assertEqual(selected["issue_id"].tolist(), ["A"])
        self.assertEqual(selected["priority_score"].sum(), 80)

    def test_negative_budget_is_rejected(self):
        with self.assertRaises(ValueError):
            plan_interventions(self.issues, -1, 2, 1)

    def test_more_resources_never_reduce_optimal_priority(self):
        baseline = plan_interventions(self.issues, 50000, 2, 1)
        more_budget = plan_interventions(self.issues, 80000, 2, 1)
        more_crews = plan_interventions(self.issues, 50000, 3, 1)
        more_equipment = plan_interventions(self.issues, 50000, 2, 2)

        baseline_score = baseline.loc[
            baseline["selected_for_intervention"], "priority_score"
        ].sum()

        budget_score = more_budget.loc[
            more_budget["selected_for_intervention"], "priority_score"
        ].sum()

        crew_score = more_crews.loc[
            more_crews["selected_for_intervention"], "priority_score"
        ].sum()

        equipment_score = more_equipment.loc[
            more_equipment["selected_for_intervention"], "priority_score"
        ].sum()

        self.assertGreaterEqual(budget_score, baseline_score)
        self.assertGreaterEqual(crew_score, baseline_score)
        self.assertGreaterEqual(equipment_score, baseline_score)


if __name__ == "__main__":
    unittest.main()
