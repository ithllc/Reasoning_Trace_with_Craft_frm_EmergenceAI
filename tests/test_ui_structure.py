import unittest
from pathlib import Path


HTML = (Path(__file__).resolve().parents[1] / "ui" / "static" / "index.html").read_text()


class UIStructureTests(unittest.TestCase):
    def test_primary_information_architecture_has_four_tabs(self):
        self.assertEqual(4, HTML.count('<button id="tab-'))
        for label in ("Overview", "Build &amp; Run", "Quality &amp; Cost", "Data &amp; History"):
            self.assertIn(label, HTML)
        self.assertIn("function tabKeys", HTML)
        self.assertIn("aria-selected", HTML)

    def test_guidance_is_unified(self):
        self.assertIn("Ask EmergeGPT", HTML)
        self.assertIn("Find sources", HTML)
        self.assertIn("Synthesized answer", HTML)
        self.assertNotIn("Documentation knowledge", HTML)
        self.assertNotIn('id="docsQuery"', HTML)
        self.assertIn("document.getElementById('voiceQuestion')", HTML)

    def test_large_catalogs_are_collapsed_but_selectors_remain_visible(self):
        self.assertIn("View full teacher and student catalogs", HTML)
        self.assertIn('id="teacherModel"', HTML)
        self.assertIn('id="pipelineStudent"', HTML)
        self.assertIn('id="pipelineRuns"', HTML)
        self.assertIn("<details>", HTML)

    def test_evaluations_notifications_and_harness_boundary_are_operable(self):
        for marker in ("evaluationDefinition", "recommendEvaluations", "importEvaluation",
                       "evaluationRuns", "notificationChannel", "alertState", "Pause", "Run now"):
            self.assertIn(marker, HTML)
        self.assertIn("Policy and approval remain deterministic", HTML)


if __name__ == "__main__":
    unittest.main()
