import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("pipeline", ROOT / "scripts" / "pipeline.py")
pipeline = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(pipeline)


class PipelineTests(unittest.TestCase):
    def test_valid_training_rows(self):
        rows = [{"messages": [{"role": "user", "content": "x"}, {"role": "assistant", "content": "y"}]}]
        self.assertEqual([], pipeline.validate_training_rows(rows))

    def test_secret_marker_is_rejected(self):
        rows = [{"messages": [{"role": "user", "content": "x"}, {"role": "assistant", "content": "Bearer secret"}]}]
        self.assertTrue(pipeline.validate_training_rows(rows))

    def test_jsonl_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data.jsonl"
            value = [{"messages": [{"role": "user", "content": "hello"}, {"role": "assistant", "content": "world"}]}]
            pipeline.write_jsonl(path, value)
            self.assertEqual(value, pipeline.read_jsonl(path))

    def test_dotenv_does_not_override_environment(self):
        import os
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text("PIPELINE_TEST_VALUE=file\nSECOND_VALUE=loaded\n", encoding="utf-8")
            os.environ["PIPELINE_TEST_VALUE"] = "process"
            os.environ.pop("SECOND_VALUE", None)
            pipeline.load_dotenv(path)
            self.assertEqual("process", os.environ["PIPELINE_TEST_VALUE"])
            self.assertEqual("loaded", os.environ["SECOND_VALUE"])

    def test_compact_catalog_keeps_grounding_fields(self):
        snapshot = {"selected_connection": "github", "schemas": [{
            "schema": {"metadata": {"name": "GITHUB", "fully_qualified_name": "github.db.schema", "description": "d"}},
            "tables": [{"metadata": {
                "name": "repos", "fully_qualified_name": "github.db.schema.repos",
                "description": "repos", "children": [{
                    "name": "repo_name", "fully_qualified_name": "github.db.schema.repos.repo_name",
                    "data_type": "VARCHAR", "description": "name",
                }],
            }}],
        }]}
        compact = pipeline.compact_catalog(snapshot)
        self.assertEqual("github", compact["connection"])
        self.assertEqual("repo_name", compact["schemas"][0]["tables"][0]["columns"][0]["name"])


if __name__ == "__main__":
    unittest.main()
