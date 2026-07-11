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


if __name__ == "__main__":
    unittest.main()

