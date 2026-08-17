import json
from pathlib import Path
import unittest

from app.experiments.scoring import aggregate_cases, latency_summary, score_answer, score_ranked_evidence


class ExperimentScoringTest(unittest.TestCase):
    @staticmethod
    def _frozen_case(case_id: str) -> dict:
        dataset = json.loads(
            (Path(__file__).resolve().parents[1] / "experiments" / "datasets" / "thesis_core_v1.json").read_text(
                encoding="utf-8"
            )
        )
        return next(
            case
            for section in ("memory_cases", "rag_cases")
            for case in dataset[section]
            if case["id"] == case_id
        )

    def test_answer_requires_gold_and_rejects_forbidden_fact(self):
        expected = {
            "required_terms": ["nanjing"],
            "forbidden_terms": ["suzhou"],
        }

        self.assertTrue(score_answer("Nanjing", expected)["correct"])
        self.assertFalse(score_answer("Nanjing, previously Suzhou", expected)["correct"])

    def test_latin_and_numeric_terms_use_token_boundaries(self):
        for term, valid, invalid in (
            ("cs", "CS", "physics"),
            ("lin", "Lin", "baseline"),
            ("rust", "Rust", "trust"),
            ("java", "Java", "JavaScript"),
            ("aster", "Aster", "disaster"),
            ("3", "3", "30"),
        ):
            with self.subTest(term=term):
                expected = {"required_terms": [term]}
                self.assertTrue(score_answer(valid, expected)["correct"])
                self.assertFalse(score_answer(invalid, expected)["correct"])

        forbidden = {"required_terms": ["safe"], "forbidden_terms": ["lin"]}
        self.assertTrue(score_answer("safe baseline", forbidden)["correct"])
        self.assertFalse(score_answer("safe Lin", forbidden)["correct"])

    def test_abstention_uses_explicit_unknown_contract(self):
        expected = {"abstain": True, "accepted_answers": ["UNKNOWN"]}

        self.assertTrue(score_answer("UNKNOWN", expected)["correct"])
        self.assertFalse(score_answer("无法确定", expected)["correct"])
        self.assertFalse(score_answer("probably unknown", expected)["correct"])

    def test_multilingual_term_groups_and_citation_are_scored_semantically(self):
        expected = {
            "required_term_groups": [
                ["artificial intelligence", "人工智能"],
                ["backend", "后端"],
            ]
        }

        result = score_answer("人工智能后端 [C2]", expected)

        self.assertTrue(result["correct"])
        self.assertEqual(result["normalized_answer"], "人工智能后端")
        self.assertEqual(result["required_terms_hit"], 2)
        self.assertEqual(result["required_terms_total"], 2)

    def test_frozen_rubric_accepts_declared_cs_alias_and_rejects_wrong_phoenix_relation(self):
        major = self._frozen_case("mem_duplicate_major")
        phoenix = self._frozen_case("rag_phoenix_window")

        self.assertTrue(score_answer("CS", major["expected"])["correct"])
        self.assertTrue(score_answer("Monday at 08:00", phoenix["expected"])["correct"])
        self.assertFalse(
            score_answer(
                "Phoenix deploys Monday at 08:00, but deployment code is ROL-119",
                phoenix["expected"],
            )["correct"]
        )

    def test_frozen_memory_short_answers_reject_negated_sentences(self):
        cases = {
            case_id: self._frozen_case(case_id)["expected"]
            for case_id in ("mem_multi_preference", "mem_decision", "mem_job_update", "mem_distractor_volume")
        }

        self.assertTrue(score_answer("Python and Rust", cases["mem_multi_preference"])["correct"])
        self.assertFalse(score_answer("Python but not Rust", cases["mem_multi_preference"])["correct"])
        self.assertTrue(score_answer("dual-service architecture", cases["mem_decision"])["correct"])
        self.assertFalse(score_answer("I did not choose a dual-service architecture", cases["mem_decision"])["correct"])
        self.assertTrue(score_answer("backend engineer", cases["mem_job_update"])["correct"])
        self.assertFalse(score_answer("I am not a backend engineer", cases["mem_job_update"])["correct"])
        self.assertTrue(score_answer("Helix", cases["mem_distractor_volume"])["correct"])
        self.assertFalse(score_answer("I prefer a non-Helix editor", cases["mem_distractor_volume"])["correct"])

    def test_frozen_multi_fact_and_policy_rubrics_require_complete_semantics(self):
        signals = self._frozen_case("rag_hybrid_signals")
        reranker = self._frozen_case("rag_rerank_type")
        fallback = self._frozen_case("rag_experiment_fallback")
        filesystem = self._frozen_case("rag_privacy_filesystem")
        secret = self._frozen_case("rag_memory_secret")

        self.assertFalse(score_answer("vector, lexical, and filename", signals["expected"])["correct"])
        self.assertTrue(
            score_answer(
                "vector, lexical, filename, recency, and file-filter",
                signals["expected"],
            )["correct"]
        )
        self.assertTrue(
            score_answer("No, it is a rule reranker, not a cross-encoder", reranker["expected"])["correct"]
        )
        self.assertFalse(score_answer("It is not a rule reranker", reranker["expected"])["correct"])
        self.assertTrue(score_answer("No", fallback["expected"])["correct"])
        self.assertFalse(score_answer("UNKNOWN", fallback["expected"])["correct"])
        self.assertFalse(score_answer("Stub fallback is not prohibited", fallback["expected"])["correct"])
        self.assertTrue(score_answer("The connector is disabled by default", filesystem["expected"])["correct"])
        self.assertTrue(score_answer("The connector is not enabled by default", filesystem["expected"])["correct"])
        self.assertFalse(score_answer("The connector is not disabled", filesystem["expected"])["correct"])
        self.assertFalse(score_answer("The connector is disabled but is enabled by default", filesystem["expected"])["correct"])
        self.assertTrue(score_answer("Secret-like values are blocked", secret["expected"])["correct"])
        self.assertTrue(score_answer("Secret-like values are blocked and not accepted by policy", secret["expected"])["correct"])
        self.assertFalse(score_answer("Secret-like values are not blocked", secret["expected"])["correct"])
        self.assertFalse(score_answer("Secret-like values are blocked but accepted by policy", secret["expected"])["correct"])

    def test_evidence_groups_allow_deduplicated_aliases(self):
        result = score_ranked_evidence(
            ["major_alias"],
            [["major_full", "major_alias"]],
            ["major_old"],
        )

        self.assertEqual(result["recall_at_k"], 1.0)
        self.assertEqual(result["mrr"], 1.0)
        self.assertFalse(result["leakage"])

    def test_no_gold_evidence_is_excluded_from_retrieval_quality_denominator(self):
        no_gold = score_ranked_evidence(["forbidden"], [], ["forbidden"])
        answerable = score_ranked_evidence(["gold"], ["gold"])
        cases = [
            {
                "case_id": "abstain",
                "repeat": 1,
                "answerability": "abstention",
                "execution_ok": True,
                "answer_score": {"correct": True},
                "evidence_score": no_gold,
                "selected_context_count": 1,
            },
            {
                "case_id": "answerable",
                "repeat": 1,
                "answerability": "answerable",
                "execution_ok": True,
                "answer_score": {"correct": True},
                "evidence_score": answerable,
                "selected_context_count": 1,
            },
        ]

        result = aggregate_cases(cases)

        self.assertIsNone(no_gold["recall_at_k"])
        self.assertIsNone(no_gold["precision_at_k"])
        self.assertEqual(result["evidence_applicable_cases"], 1)
        self.assertEqual(result["evidence_recall_at_k"], 1.0)
        self.assertEqual(result["evidence_precision_at_k"], 1.0)
        self.assertEqual(result["leakage_rate"], 0.5)
        self.assertEqual(result["no_answer_empty_retrieval_rate"], 0.0)
        self.assertEqual(result["no_answer_forbidden_leakage_rate"], 1.0)

    def test_latency_percentiles_are_interpolated(self):
        summary = latency_summary([10, 20, 30, 40])

        self.assertEqual(summary["mean"], 25.0)
        self.assertEqual(summary["p50"], 25.0)
        self.assertEqual(summary["p95"], 38.5)

    def test_failures_do_not_insert_zeroes_into_success_latency(self):
        cases = [
            {
                "case_id": "one",
                "repeat": 1,
                "category": "semantic",
                "language": "en",
                "answerability": "answerable",
                "execution_ok": True,
                "answer_score": {"correct": True, "normalized_answer": "ok"},
                "evidence_score": {},
                "candidate_count": 4,
                "selected_context_count": 2,
                "retrieval_latency_ms": 100.0,
                "generation_latency_ms": 200.0,
                "end_to_end_latency_ms": 300.0,
                "write_latency_ms": None,
            },
            {
                "case_id": "two",
                "repeat": 1,
                "category": "semantic",
                "language": "en",
                "answerability": "answerable",
                "execution_ok": False,
                "failure_category": "timeout",
                "answer_score": {"correct": False, "normalized_answer": ""},
                "evidence_score": {},
                "candidate_count": 0,
                "selected_context_count": 0,
                "retrieval_latency_ms": None,
                "generation_latency_ms": None,
                "end_to_end_latency_ms": 50.0,
                "failure_elapsed_ms": 50.0,
                "write_latency_ms": None,
            },
        ]

        result = aggregate_cases(cases)

        self.assertEqual(result["rubric_accuracy"], 0.5)
        self.assertEqual(result["answer_accuracy"], 0.5)
        self.assertEqual(result["retrieval_latency_ms"]["mean"], 100.0)
        self.assertEqual(result["end_to_end_latency_ms"]["mean"], 300.0)
        self.assertEqual(result["all_attempt_end_to_end_latency_ms"]["mean"], 175.0)
        self.assertEqual(result["failure_elapsed_ms"]["mean"], 50.0)
        self.assertEqual(result["failure_categories"], {"timeout": 1})
        self.assertIn("answerable", result["by_answerability"])
        self.assertEqual(result["candidate_count_mean"], 2.0)


if __name__ == "__main__":
    unittest.main()
