import unittest

from app.memory.evaluation.governance_report import render_markdown, run_governance_report


class MemoryGovernanceReportTest(unittest.TestCase):
    def test_governance_report_includes_expected_actual_delta(self):
        report = run_governance_report()

        self.assertGreaterEqual(report["summary"]["total"], 5)
        self.assertEqual(report["summary"]["failed"], 0)
        self.assertEqual(report["summary"]["executed_coverage"]["write_cases"], 2)
        self.assertEqual(report["summary"]["executed_coverage"]["calibration_cases"], 4)
        self.assertEqual(sum(report["summary"]["executed_coverage"].values()), report["summary"]["total"])
        self.assertEqual(report["summary"]["fixture_inventory"]["sensitive_cases"], 2)
        self.assertEqual(report["summary"]["fixture_inventory"]["multi_candidate_cases"], 2)
        self.assertEqual(
            report["summary"]["coverage_by_section"],
            report["summary"]["fixture_inventory"],
        )
        self.assertNotIn("sensitive_cases", report["summary"]["executed_coverage"])

        by_id = {case["id"]: case for case in report["cases"]}
        major = by_id["explicit_major_is_up_calibrated"]
        self.assertEqual(major["actual"]["review_status"], "accepted")
        self.assertGreaterEqual(major["actual"]["calibrated_confidence"], 0.94)
        self.assertGreaterEqual(major["delta"]["min_margin"], 0)

        implied = by_id["llm_implied_preference_is_down_calibrated"]
        self.assertEqual(implied["actual"]["review_status"], "pending")
        self.assertLessEqual(implied["actual"]["calibrated_confidence"], 0.65)
        self.assertGreaterEqual(implied["delta"]["max_margin"], 0)
        self.assertIn("weak_signal", implied["actual"]["confidence_calibration_factors"])

    def test_markdown_report_renders_table(self):
        report = run_governance_report()

        rendered = render_markdown(report)

        self.assertIn("# Memory Confidence Calibration Report", rendered)
        self.assertIn("executed coverage: calibration_cases=4, write_cases=2", rendered)
        self.assertIn("fixture inventory:", rendered)
        self.assertIn("| case | section | pass | raw | actual | expected | delta | status | factors |", rendered)
        self.assertIn("explicit_major_is_up_calibrated", rendered)


if __name__ == "__main__":
    unittest.main()
