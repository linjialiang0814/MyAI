import copy
import json
from pathlib import Path
import unittest

from app.experiments.schema import _validate_dataset, _validate_spec


BASE_DIR = Path(__file__).resolve().parents[1]
SPEC_PATH = BASE_DIR / "experiments" / "specs" / "thesis_core_v1.json"
DATASET_PATH = BASE_DIR / "experiments" / "datasets" / "thesis_core_v1.json"


class ExperimentSchemaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
        cls.dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))

    def test_frozen_execution_and_retrieval_fields_are_enforced(self):
        mutations = (
            ("temperature", lambda value: value["model"].update(temperature=0.2)),
            ("seed", lambda value: value["model"].update(seed=7)),
            ("model retries", lambda value: value["model"].update(max_retries=1)),
            ("embedding dimensions", lambda value: value["embedding"].update(dimensions=768)),
            ("model timeout nan", lambda value: value["model"].update(timeout_seconds=float("nan"))),
            ("embedding timeout inf", lambda value: value["embedding"].update(timeout_seconds=float("inf"))),
            ("reranker", lambda value: value["retrieval"].update(reranker="unknown")),
            ("missing hardware", lambda value: value["hardware"].pop("nvidia_driver")),
        )
        for label, mutate in mutations:
            with self.subTest(label=label):
                payload = copy.deepcopy(self.spec)
                mutate(payload)
                with self.assertRaises(ValueError):
                    _validate_spec(payload)

    def test_safe_experiment_slug_and_exact_artifact_formats_are_required(self):
        unsafe = copy.deepcopy(self.spec)
        unsafe["experiment_id"] = "../../escape"
        with self.assertRaisesRegex(ValueError, "safe lowercase slug"):
            _validate_spec(unsafe)

        incomplete = copy.deepcopy(self.spec)
        incomplete["artifacts"]["formats"] = ["json"]
        with self.assertRaisesRegex(ValueError, "artifacts.formats"):
            _validate_spec(incomplete)

    def test_dataset_semantics_reject_duplicate_ids_unknown_alias_and_missing_language(self):
        duplicate = copy.deepcopy(self.dataset)
        duplicate["rag_cases"][0]["id"] = duplicate["memory_cases"][0]["id"]
        with self.assertRaisesRegex(ValueError, "case ids"):
            _validate_dataset(duplicate)

        unknown = copy.deepcopy(self.dataset)
        unknown["rag_cases"][0]["gold_file_aliases"] = ["missing"]
        with self.assertRaisesRegex(ValueError, "unknown file alias"):
            _validate_dataset(unknown)

        language = copy.deepcopy(self.dataset)
        language["rag_cases"][0].pop("language")
        with self.assertRaisesRegex(ValueError, "requires language"):
            _validate_dataset(language)

        rubric = copy.deepcopy(self.dataset)
        rubric["rag_cases"][0]["expected"] = {"required_term_groups": [[]]}
        with self.assertRaisesRegex(ValueError, "invalid required_term_groups"):
            _validate_dataset(rubric)

    def test_dataset_contains_real_multichunk_and_multidocument_cases(self):
        long_documents = [item for item in self.dataset["rag_documents"] if len(item["content"]) > 700]
        multi_document = [item for item in self.dataset["rag_cases"] if item.get("gold_evidence")]

        self.assertGreaterEqual(len(long_documents), 4)
        self.assertGreaterEqual(len(multi_document), 1)


if __name__ == "__main__":
    unittest.main()
