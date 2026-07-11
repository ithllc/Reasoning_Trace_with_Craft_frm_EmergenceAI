import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ui import voice_server


class VoiceServerTests(unittest.TestCase):
    def config(self, directory):
        return {
            "api_key": "test", "base_url": "https://example.invalid/v1", "model": "test-model",
            "max_usd": 75.0, "input_per_million": 1.0, "output_per_million": 2.0,
            "max_output_tokens": 20, "dashboard_url": "http://dashboard.invalid",
            "ledger": Path(directory) / "ledger.json",
        }

    def test_missing_pricing_fails_closed_before_network(self):
        with tempfile.TemporaryDirectory() as directory:
            config = self.config(directory)
            config["input_per_million"] = 0
            with patch.object(voice_server, "read_json_url") as network:
                with self.assertRaisesRegex(RuntimeError, "disabled"):
                    voice_server.ask("What is training loss?", config)
                network.assert_not_called()

    def test_budget_ceiling_blocks_request(self):
        with tempfile.TemporaryDirectory() as directory:
            config = self.config(directory)
            config["max_usd"] = 0.000001
            config["ledger"].write_text(json.dumps({"spent_usd": 0, "requests": 0}))
            with patch.object(voice_server, "read_json_url", return_value={"jobs": []}) as network:
                with self.assertRaisesRegex(RuntimeError, "Budget ceiling"):
                    voice_server.ask("Explain the jobs", config)
                self.assertEqual(network.call_count, 1)  # dashboard only; no inference call

    def test_grounded_answer_records_actual_usage(self):
        with tempfile.TemporaryDirectory() as directory:
            config = self.config(directory)
            responses = [
                {"training_result": {"status": "succeeded"}},
                {"usage": {"prompt_tokens": 100, "completion_tokens": 10},
                 "choices": [{"message": {"content": "The run succeeded."}}]},
            ]
            with patch.object(voice_server, "read_json_url", side_effect=responses) as network:
                result = voice_server.ask("Did training succeed?", config)
            self.assertEqual(result["answer"], "The run succeeded.")
            self.assertEqual(network.call_count, 2)
            ledger = json.loads(config["ledger"].read_text())
            self.assertEqual(ledger["requests"], 1)
            self.assertAlmostEqual(ledger["spent_usd"], 0.00012)

    def test_project_knowledge_is_whitelisted_and_includes_run_records(self):
        knowledge = voice_server.project_knowledge()
        self.assertIn("README.md", knowledge)
        self.assertIn("docs/architecture.md", knowledge)
        self.assertIn("config/pipeline.json", knowledge)
        self.assertTrue(any(path.startswith("evals/results/") for path in knowledge))
        self.assertFalse(any(path.endswith(".env") for path in knowledge))


if __name__ == "__main__":
    unittest.main()
