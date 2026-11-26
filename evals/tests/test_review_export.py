import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agent"))
from export_review import review_rows, safe_cell


class ReviewExportTests(unittest.TestCase):
    def test_model_output_cannot_become_spreadsheet_formula(self):
        self.assertTrue(safe_cell(' =HYPERLINK("example")').startswith("'"))
        self.assertEqual(safe_cell("normal answer"), "normal answer")

    def test_human_scores_are_blank_and_failure_flags_preserved(self):
        report = {
            "variant": "test",
            "cases": [
                {
                    "id": "one",
                    "repeat": 1,
                    "turns": [
                        {
                            "turn": 1,
                            "message": "test",
                            "reply": "",
                            "operational_error": True,
                            "quality_pass": None,
                            "format_pass": None,
                            "facts_pass": None,
                            "fact_errors": [],
                        }
                    ],
                }
            ],
        }
        row = next(review_rows(report))
        for name in ["correctness_0_2", "grounding_0_2", "usefulness_0_2", "safety_0_2"]:
            self.assertEqual(row[name], "")
        self.assertEqual(row["operational_failure"], "True")
        self.assertEqual(row["automated_quality_pass"], "")


if __name__ == "__main__":
    unittest.main()
