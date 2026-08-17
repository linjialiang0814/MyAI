import json
from pathlib import Path
import unittest

from app.experiments.rag_ablation import build_rag_prompt, score_rag_citations


CASE = {
    "gold_file_aliases": ["gold"],
    "gold_content_anchors": ["answer-bearing fact"],
}
EVIDENCE = [
    {"label": "C1", "file_alias": "gold", "content": "The answer-bearing fact is ALPHA."},
    {"label": "C2", "file_alias": "noise", "content": "A plausible but unsupported distractor."},
]


class ExperimentCitationScoringTest(unittest.TestCase):
    def test_correct_generated_citation_is_distinct_from_support_hit(self):
        result = score_rag_citations(CASE, EVIDENCE, "ALPHA [C1]")

        self.assertTrue(result["support_hit_at_k"])
        self.assertTrue(result["generated_citation_hit"])
        self.assertEqual(result["generated_citation_precision"], 1.0)
        self.assertFalse(result["invalid_citation"])

    def test_frozen_aster_cases_accept_objective_overlap_chunks(self):
        dataset = json.loads(
            (Path(__file__).resolve().parents[1] / "experiments" / "datasets" / "thesis_core_v1.json").read_text(
                encoding="utf-8"
            )
        )
        cases = {item["id"]: item for item in dataset["rag_cases"]}
        overlap_evidence = {
            "rag_aster_code": "The exact code ZXQ9000 must never be shortened.",
            "rag_aster_rollback": "ROL-771 is used only after a failed production change.",
            "rag_aster_stop_condition": "If the probe is degraded, the run stops before any migration.",
        }

        for case_id, content in overlap_evidence.items():
            with self.subTest(case_id=case_id):
                result = score_rag_citations(
                    cases[case_id],
                    [{"label": "C1", "file_alias": "aster_release", "content": content}],
                    "supported [C1]",
                )
                self.assertTrue(result["support_hit_at_k"])
                self.assertTrue(result["generated_citation_hit"])

    def test_support_hit_does_not_credit_an_answer_without_citation(self):
        result = score_rag_citations(CASE, EVIDENCE, "ALPHA")

        self.assertTrue(result["support_hit_at_k"])
        self.assertFalse(result["generated_citation_hit"])
        self.assertEqual(result["generated_citation_precision"], 0.0)

    def test_wrong_known_citation_is_not_a_hit(self):
        result = score_rag_citations(CASE, EVIDENCE, "ALPHA [C2]")

        self.assertFalse(result["generated_citation_hit"])
        self.assertEqual(result["generated_citation_precision"], 0.0)
        self.assertFalse(result["invalid_citation"])

    def test_unknown_label_counts_in_precision_denominator(self):
        result = score_rag_citations(CASE, EVIDENCE, "ALPHA [C1] [C9]")

        self.assertTrue(result["generated_citation_hit"])
        self.assertEqual(result["generated_citation_precision"], 0.5)
        self.assertEqual(result["invalid_citation_labels"], ["C9"])

    def test_no_answer_unknown_label_is_citation_hallucination(self):
        case = {"gold_file_aliases": [], "gold_content_anchors": []}

        result = score_rag_citations(case, [], "UNKNOWN [C9]")

        self.assertTrue(result["no_answer_citation_hallucination"])
        self.assertEqual(result["generated_citation_precision"], 0.0)
        self.assertEqual(result["invalid_citation_labels"], ["C9"])
        self.assertIsNone(result["support_hit_at_k"])
        self.assertIsNone(result["support_recall_at_k"])
        self.assertIsNone(result["support_precision_at_k"])

    def test_multi_document_support_recall_uses_gold_groups(self):
        case = {
            "gold_file_aliases": ["protocol", "hardware"],
            "gold_evidence": [
                {"file_alias": "protocol", "anchors": ["seed 42"], "match": "all"},
                {"file_alias": "hardware", "anchors": ["RTX 3050"], "match": "all"},
            ],
        }
        evidence = [{"label": "C1", "file_alias": "protocol", "content": "seed 42"}]

        result = score_rag_citations(case, evidence, "42 [C1]")

        self.assertEqual(result["support_recall_at_k"], 0.5)
        self.assertEqual(result["support_precision_at_k"], 1.0)

    def test_prompt_uses_neutral_sources_and_does_not_force_c1(self):
        prompt = build_rag_prompt({"query": "question"}, EVIDENCE)

        self.assertNotIn("(gold)", prompt)
        self.assertLess(prompt.index("SOURCES:"), prompt.index("QUESTION:"))
        self.assertIn("bracketed label copied from the source", prompt)
        self.assertNotIn("<short answer>", prompt)
        self.assertNotIn("[C1]", prompt.split("QUESTION:", 1)[1])

    def test_frozen_reranker_case_accepts_the_second_authoritative_chunk(self):
        dataset = json.loads(
            (Path(__file__).resolve().parents[1] / "experiments" / "datasets" / "thesis_core_v1.json").read_text(
                encoding="utf-8"
            )
        )
        case = next(item for item in dataset["rag_cases"] if item["id"] == "rag_rerank_weights")
        evidence = [
            {
                "label": "C1",
                "file_alias": "rag_design",
                "content": "The current deterministic rule remains 0.72, 0.20, and 0.08.",
            }
        ]

        result = score_rag_citations(case, evidence, "0.72, 0.20, and 0.08 [C1]")

        self.assertTrue(result["support_hit_at_k"])
        self.assertTrue(result["generated_citation_hit"])

    def test_frozen_hardware_memory_support_requires_both_facts(self):
        dataset = json.loads(
            (Path(__file__).resolve().parents[1] / "experiments" / "datasets" / "thesis_core_v1.json").read_text(
                encoding="utf-8"
            )
        )
        case = next(item for item in dataset["rag_cases"] if item["id"] == "rag_hardware_memory")

        partial = score_rag_citations(
            case,
            [{"label": "C1", "file_alias": "hardware", "content": "15.8 GiB of system RAM"}],
            "15.8 GiB [C1]",
        )
        complete = score_rag_citations(
            case,
            [
                {
                    "label": "C1",
                    "file_alias": "hardware",
                    "content": "15.8 GiB of system RAM and 4096 MiB VRAM",
                }
            ],
            "15.8 GiB and 4096 MiB [C1]",
        )

        self.assertFalse(partial["support_hit_at_k"])
        self.assertTrue(complete["support_hit_at_k"])


if __name__ == "__main__":
    unittest.main()
