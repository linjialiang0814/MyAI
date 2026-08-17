import os
import shutil
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

os.environ["MYAI_CHAT_PROVIDER"] = "stub"
os.environ["MYAI_TASK_PROVIDER"] = "stub"
os.environ["MYAI_EMBEDDING_PROVIDER"] = "stub"
os.environ["MYAI_LLM_PROVIDER"] = "stub"
os.environ["MYAI_MEMORY_LLM_EXTRACTOR_ENABLED"] = "false"

from fastapi.testclient import TestClient

from app.main import app
from app.task.config.task_config import TaskConfig
from app.task.mcp import GitReadOnlyMCPClient, MCPServerConfig, MCPToolRegistryLoader, ReadOnlyFilesystemMCPClient
from app.task.plan.executor import ToolExecutor
from app.task.plan.planner import ToolPlanner
from app.task.plan.planner import ToolPlan
from app.task.plan.planner import ToolStep
from app.task.plan.recovery import RecoveryPlanner
from app.task.plan.validation import ToolValidation
from app.task.service.task_service import TaskService
from app.task.stats.statistics import StatsManager
from app.task.tool.tool import Tool, ToolPolicy, ToolResult
from app.task.tool.tool_registry import ToolRegistry
from app.task.tools.calculator import CalculatorTool
from app.task.tools.datetime_tool import DateTimeTool
from app.task.tools.file_summary import FileSummaryTool
from app.task.tools.knowledge_admin import KnowledgeAdminTool
from app.task.tools.memory_admin import MemoryAdminTool
from app.task.tools.system_info import SystemInfoTool
from app.task.tools.text_stats import TextStatsTool
from app.task.tools.weather_tool import WeatherTool
from app.task.tools.web_search import WebSearchTool
from app.task.workflow.registry import build_default_workflow_registry
from app.memory.governance import governance_response_fields, is_high_risk_secret, normalize_governance_metadata
from app.memory.retrieval.policy import MemoryPolicy
from app.memory.retrieval.retriever import RetrievedMemory
from app.memory.embedding.stub_embedding import StubEmbedding
from app.memory.mem_service import MemoryService
from app.memory.model.mem_item import MemoryItem
from app.memory.settings import MemorySettingsStore
from app.memory.store.in_mem_store import MemoryStore
from app.knowledge.service import KnowledgeService


class FakePlannerLLM:
    def generate(self, prompt: str) -> str:
        return """
        {
          "steps": [
            {
              "step_id": "step1",
              "description": "Count words in the text",
              "tool_name": "text_stats",
              "tool_args": {"text": "hello world from myai"},
              "output_key": "word_count",
              "extract_path": "data.word_count"
            },
            {
              "step_id": "step2",
              "description": "Estimate reading time",
              "tool_name": "calculator",
              "tool_args": {"expression": "{word_count} / 200"},
              "output_key": "reading_minutes",
              "extract_path": "data.value"
            }
          ],
          "final_response": "Words={word_count}, reading_minutes={reading_minutes}",
          "rationale": "Need two chained tools."
        }
        """


class FakeNoToolPlannerLLM:
    def __init__(self):
        self.calls = 0

    def generate(self, prompt: str) -> str:
        self.calls += 1
        return '{"need_tool": false, "tool_name": "", "tool_args": {}, "steps": [], "rationale": "No tool needed."}'


class FakeResponse:
    def __init__(self, payload, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class FakeMissingToolPlanner:
    def plan(self, content: str, short_context: list[str] | None = None):
        return ToolPlan(
            need_tool=True,
            tool_name="missing_tool",
            tool_args={},
            source="test",
            rationale="Force a failed runtime step.",
        )


class FakeToolPlanner:
    def __init__(self, tool_name: str, tool_args: dict | None = None):
        self.tool_name = tool_name
        self.tool_args = tool_args or {}

    def plan(self, content: str, short_context: list[str] | None = None):
        return ToolPlan(
            need_tool=True,
            tool_name=self.tool_name,
            tool_args=self.tool_args,
            source="test",
            rationale=f"Force {self.tool_name}.",
        )


class FakeMultiStepPlanner:
    def __init__(self, steps: list[ToolStep]):
        self.steps = steps

    def plan(self, content: str, short_context: list[str] | None = None):
        return ToolPlan(
            need_tool=True,
            steps=self.steps,
            source="test",
            rationale="Force a multi-step background plan.",
        )


class CapturingNoToolPlanner:
    def __init__(self):
        self.short_context: list[str] = []

    def plan(self, content: str, short_context: list[str] | None = None):
        self.short_context = list(short_context or [])
        return ToolPlan(
            need_tool=False,
            source="test",
            rationale="Capture memory-aware planning context.",
        )


class FlakyRetryTool(Tool):
    name = "flaky_retry"
    description = "Fail once with a transient error, then succeed."
    idempotent = True
    policy = ToolPolicy(risk_level="network", timeout_seconds=1.0, retry_count=1)

    def __init__(self):
        self.calls = 0

    def run(self, **kwargs):
        self.calls += 1
        if self.calls == 1:
            return ToolResult(success=False, error="temporary network timeout")
        return ToolResult(success=True, data={"calls": self.calls})


class SlowTimeoutTool(Tool):
    name = "slow_timeout"
    description = "Sleep longer than its policy timeout."
    policy = ToolPolicy(risk_level="safe", timeout_seconds=0.01, retry_count=0)

    def run(self, **kwargs):
        time.sleep(0.2)
        return ToolResult(success=True, data={"finished": True})


class SlowSuccessTool(Tool):
    name = "slow_success"
    description = "Sleep briefly and then succeed."
    policy = ToolPolicy(risk_level="safe", timeout_seconds=1.0, retry_count=0)

    def run(self, **kwargs):
        time.sleep(0.1)
        return ToolResult(success=True, data={"finished": True})


class MyAITestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client_context = TestClient(app)
        cls.client = cls.client_context.__enter__()
        cls.runtime = app.state.runtime

    @classmethod
    def tearDownClass(cls):
        cls.client_context.__exit__(None, None, None)

    def test_chat_endpoint_returns_reply(self):
        response = self.client.post(
            "/chat",
            json={"user_id": "u-chat", "message": "my major is computer science"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("reply", payload)
        self.assertIn("[StubLLM Safe Fallback]", payload["reply"])
        self.assertIn("run_id", payload)
        self.assertIn("trace", payload)
        self.assertEqual(payload["trace"]["status"], "completed")
        self.assertTrue(payload["trace"]["steps"])
        self.assertEqual(payload["trace"]["steps"][0]["name"], "context.load_history")

    def test_chat_trace_includes_memory_citations(self):
        write_resp = self.client.post(
            "/memory/write",
            json={"user_id": "u-chat-citations", "content": "我的专业是人工智能"},
        )
        self.assertEqual(write_resp.status_code, 200)
        self.assertTrue(write_resp.json()["written"])

        response = self.client.post(
            "/chat",
            json={"user_id": "u-chat-citations", "message": "你的专业是什么"},
        )

        self.assertEqual(response.status_code, 200)
        trace = response.json()["trace"]
        memory_steps = [step for step in trace["steps"] if step["name"] == "memory.retrieve"]
        self.assertEqual(len(memory_steps), 1)
        citations = memory_steps[0]["metadata"].get("citations", [])
        self.assertTrue(citations)
        self.assertEqual(citations[0]["content"], "我的专业是人工智能")
        explanations = memory_steps[0]["metadata"].get("retrieval_explanations", [])
        self.assertTrue(explanations)
        self.assertTrue(any(item["selected"] for item in explanations))
        self.assertIn("reason", explanations[0])

    def test_chat_trace_includes_knowledge_citations(self):
        user_id = f"u-chat-knowledge-{uuid4()}"
        upload_resp = self.client.post(
            "/knowledge/upload",
            data={"user_id": user_id},
            files={
                "file": (
                    "chat_knowledge.txt",
                    "项目 Atlas 的关键结论是需要先完成知识引用审计。",
                    "text/plain",
                )
            },
        )
        self.assertEqual(upload_resp.status_code, 200)

        response = self.client.post(
            "/chat",
            json={"user_id": user_id, "message": "Atlas 的关键结论是什么？"},
        )

        self.assertEqual(response.status_code, 200)
        trace = response.json()["trace"]
        knowledge_steps = [step for step in trace["steps"] if step["name"] == "knowledge.retrieve"]
        self.assertEqual(len(knowledge_steps), 1)
        metadata = knowledge_steps[0]["metadata"]
        citations = metadata.get("citations", [])
        self.assertTrue(citations)
        self.assertEqual(citations[0]["file_id"], upload_resp.json()["file_id"])
        self.assertTrue(citations[0]["citation_id"])
        self.assertIn("Atlas", citations[0]["snippet"])
        snippets = metadata.get("snippets", [])
        self.assertTrue(snippets)
        self.assertIn(citations[0]["citation_id"], snippets[0])
        explanations = metadata.get("retrieval_explanations", [])
        self.assertTrue(explanations)
        self.assertTrue(any(item["selected"] for item in explanations))
        self.assertEqual(metadata["hits"][0]["citation_id"], citations[0]["citation_id"])

    def test_knowledge_maintenance_repairs_missing_chunks_and_orphans(self):
        user_id = f"u-knowledge-maintenance-{uuid4()}"
        upload_resp = self.client.post(
            "/knowledge/upload",
            data={"user_id": user_id},
            files={
                "file": (
                    "maintenance.txt",
                    "Alpha maintenance finding. Beta maintenance finding. Gamma maintenance finding.",
                    "text/plain",
                )
            },
        )
        self.assertEqual(upload_resp.status_code, 200)
        file_id = upload_resp.json()["file_id"]
        entry = self.runtime.knowledge_service.get_file_entry(user_id, file_id=file_id)
        self.assertIsNotNone(entry)
        chunk_ids = entry["chunk_ids"]
        self.assertTrue(chunk_ids)

        self.runtime.knowledge_service.collection.delete(ids=[chunk_ids[0]])
        orphan_id = f"{file_id}_orphan"
        orphan_embedding = self.runtime.knowledge_service.embedding_client.embed("orphan maintenance chunk").astype("float32").tolist()
        self.runtime.knowledge_service.collection.add(
            ids=[orphan_id],
            documents=["orphan maintenance chunk"],
            embeddings=[orphan_embedding],
            metadatas=[
                {
                    "user_id": user_id,
                    "file_id": file_id,
                    "file_name": "maintenance.txt",
                    "chunk_index": 99,
                    "source": "knowledge_base",
                }
            ],
        )

        dry_run_resp = self.client.post(
            "/knowledge/maintenance",
            json={"user_id": user_id, "dry_run": True},
        )
        self.assertEqual(dry_run_resp.status_code, 200)
        dry_run = dry_run_resp.json()
        self.assertEqual(dry_run["status"], "needs_repair")
        self.assertEqual(dry_run["summary"]["missing_chunks"], 1)
        self.assertEqual(dry_run["summary"]["orphan_chunks"], 1)
        self.assertIn(orphan_id, dry_run["orphan_chunk_ids"])
        self.assertEqual(dry_run["files"][0]["action"], "would_reindex")

        repair_resp = self.client.post(
            "/knowledge/maintenance",
            json={"user_id": user_id, "dry_run": False},
        )
        self.assertEqual(repair_resp.status_code, 200)
        repair = repair_resp.json()
        self.assertEqual(repair["status"], "repaired")
        self.assertEqual(repair["summary"]["reindexed_files"], 1)
        self.assertEqual(repair["summary"]["orphan_chunks_deleted"], 1)

        repaired_chunks = self.runtime.knowledge_service.collection.get(ids=chunk_ids, include=["metadatas"]).get("ids", [])
        self.assertEqual(set(repaired_chunks), set(chunk_ids))
        orphan_chunks = self.runtime.knowledge_service.collection.get(ids=[orphan_id], include=["metadatas"]).get("ids", [])
        self.assertEqual(orphan_chunks, [])

        query_resp = self.client.post(
            "/knowledge/query",
            json={"user_id": user_id, "query": "Alpha maintenance", "top_k": 1},
        )
        self.assertEqual(query_resp.status_code, 200)
        self.assertTrue(query_resp.json()["hits"])

    def test_memory_write_and_query(self):
        write_resp = self.client.post(
            "/memory/write",
            json={"user_id": "u-memory", "content": "我的专业是人工智能"},
        )
        self.assertEqual(write_resp.status_code, 200)
        self.assertTrue(write_resp.json()["written"])

        query_resp = self.client.post(
            "/memory/query",
            json={"user_id": "u-memory", "content": "你的专业是什么"},
        )
        self.assertEqual(query_resp.status_code, 200)
        payload = query_resp.json()
        self.assertIn("memories", payload)
        self.assertIn("我的专业是人工智能", payload["memories"])

    def test_memory_write_supports_multiple_candidates(self):
        self.runtime.memory_service.memory_store.clear_user_memories("u-memory-multi")

        write_resp = self.client.post(
            "/memory/write",
            json={"user_id": "u-memory-multi", "content": "my major is CS and I like Python"},
        )

        self.assertEqual(write_resp.status_code, 200)
        payload = write_resp.json()
        self.assertTrue(payload["written"])
        self.assertEqual(payload["candidate_count"], 2)
        self.assertEqual(payload["written_count"], 2)
        self.assertEqual(len(payload["results"]), 2)
        batch_ids = {result["governance"]["extraction_batch_id"] for result in payload["results"]}
        self.assertEqual(len(batch_ids), 1)
        self.assertEqual(
            {result["governance"]["candidate_index"] for result in payload["results"]},
            {1, 2},
        )

        list_resp = self.client.get("/memory/list/u-memory-multi")
        self.assertEqual(list_resp.status_code, 200)
        memories = list_resp.json()["memories"]
        values = {memory["mem_type"]: memory["content"] for memory in memories}
        self.assertIn("fact", values)
        self.assertIn("preference", values)
        self.assertTrue(all(memory["multi_candidate"] for memory in memories))
        self.assertEqual({memory["candidate_count"] for memory in memories}, {2})

    def test_memory_list_and_delete(self):
        write_resp = self.client.post(
            "/memory/write",
            json={"user_id": "u-memory-manage", "content": "我喜欢羽毛球"},
        )
        self.assertEqual(write_resp.status_code, 200)
        memory_id = write_resp.json().get("memory_id")
        self.assertIsNotNone(memory_id)

        list_resp = self.client.get("/memory/list/u-memory-manage")
        self.assertEqual(list_resp.status_code, 200)
        list_payload = list_resp.json()
        self.assertTrue(list_payload["memories"])
        self.assertEqual(list_payload["memories"][0]["memory_id"], memory_id)
        self.assertEqual(list_payload["memories"][0]["mem_type"], "preference")
        self.assertEqual(list_payload["memories"][0]["source"], "user_explicit")
        self.assertEqual(list_payload["memories"][0]["scope"], "global")
        self.assertEqual(list_payload["memories"][0]["review_status"], "accepted")
        self.assertIn(list_payload["memories"][0]["sensitivity"], ["personal", "normal"])
        self.assertIsNotNone(list_payload["memories"][0]["confidence"])
        self.assertTrue(list_payload["memories"][0]["extraction_reason"])

        delete_resp = self.client.delete(f"/memory/u-memory-manage/{memory_id}")
        self.assertEqual(delete_resp.status_code, 200)
        self.assertTrue(delete_resp.json()["deleted"])

        list_after_delete = self.client.get("/memory/list/u-memory-manage")
        self.assertEqual(list_after_delete.status_code, 200)
        self.assertEqual(list_after_delete.json()["memories"], [])

    def test_knowledge_upload_and_query(self):
        user_id = f"u-knowledge-{uuid4()}"
        upload_resp = self.client.post(
            "/knowledge/upload",
            data={"user_id": user_id},
            files={
                "file": (
                    "study_notes.txt",
                    "机器学习是一门研究如何让计算机从数据中学习的学科。",
                    "text/plain",
                )
            },
        )
        self.assertEqual(upload_resp.status_code, 200)
        upload_payload = upload_resp.json()
        self.assertEqual(upload_payload["file_type"], "txt")
        self.assertIn("机器学习", upload_payload["summary"])
        self.assertEqual(upload_payload["ingestion_status"], "indexed")
        self.assertEqual(upload_payload["ingestion_report"]["status"], "indexed")
        self.assertEqual(upload_payload["size_bytes"], len("机器学习是一门研究如何让计算机从数据中学习的学科。".encode("utf-8")))
        self.assertTrue(upload_payload["content_hash"])
        self.assertGreater(upload_payload["text_length"], 0)
        profile = upload_payload["document_profile"]
        self.assertEqual(profile["profile_version"], "1")
        self.assertIn("机器学习", profile["short_summary"])
        self.assertTrue(profile["keywords"])
        self.assertTrue(profile["important_passages"])
        self.assertTrue(profile["possible_questions"])
        self.assertIn(profile["document_language"], {"zh", "mixed"})
        self.assertGreater(profile["stats"]["character_count"], 0)

        query_resp = self.client.post(
            "/knowledge/query",
            json={"user_id": user_id, "query": "什么是机器学习", "top_k": 3},
        )
        self.assertEqual(query_resp.status_code, 200)
        query_payload = query_resp.json()
        self.assertTrue(query_payload["hits"])
        hit = query_payload["hits"][0]
        self.assertIn("机器学习", hit["content"])
        self.assertIn("机器学习", hit["snippet"])
        self.assertTrue(hit["citation_id"])
        self.assertEqual(hit["citation"]["citation_id"], hit["citation_id"])
        self.assertEqual(hit["citation"]["chunk_id"], hit["chunk_id"])
        self.assertEqual(hit["citation"]["file_id"], upload_payload["file_id"])
        self.assertEqual(hit["citation"]["file_name"], upload_payload["file_name"])
        self.assertIn("机器学习", hit["citation"]["snippet"])
        self.assertIn("char_start", hit)
        self.assertGreater(hit["char_end"], hit["char_start"])
        self.assertGreater(hit["token_estimate"], 0)
        self.assertEqual(hit["citation"]["char_start"], hit["char_start"])
        self.assertEqual(hit["citation"]["char_end"], hit["char_end"])
        self.assertEqual(hit["citation"]["token_estimate"], hit["token_estimate"])
        self.assertEqual(hit["citation"]["score"], hit["score"])
        self.assertTrue(hit["retrieval_mode"])
        self.assertGreater(hit["retrieval_score"], 0)
        self.assertIn("retrieval_score", hit["retrieval_explanation"])
        self.assertIn("keyword_score", hit["retrieval_explanation"])
        self.assertIn("vector_score", hit["retrieval_explanation"])
        self.assertEqual(hit["selection_status"], "selected")
        self.assertEqual(hit["final_rank"], 1)
        self.assertGreater(hit["rerank_score"], 0)
        self.assertIn("candidate_count", hit["selection_explanation"])
        self.assertIn("max_context_tokens", hit["selection_explanation"])
        self.assertIn("query_coverage", hit["selection_explanation"])

        file_query_resp = self.client.post(
            "/knowledge/query",
            json={
                "user_id": user_id,
                "query": "什么是机器学习",
                "top_k": 3,
                "file_id": upload_payload["file_id"],
            },
        )
        self.assertEqual(file_query_resp.status_code, 200)
        file_query_payload = file_query_resp.json()
        self.assertTrue(file_query_payload["hits"])
        self.assertEqual(file_query_payload["hits"][0]["file_id"], upload_payload["file_id"])

        list_resp = self.client.get(f"/knowledge/files/{user_id}")
        self.assertEqual(list_resp.status_code, 200)
        listed = list_resp.json()[0]
        self.assertEqual(listed["content_hash"], upload_payload["content_hash"])
        self.assertEqual(listed["ingestion_status"], "indexed")
        self.assertEqual(listed["document_profile"]["short_summary"], profile["short_summary"])

    def test_knowledge_duplicate_upload_is_reported(self):
        user_id = f"u-knowledge-duplicate-{uuid4()}"
        content = "重复文件内容，用于检测 content hash。"
        first_resp = self.client.post(
            "/knowledge/upload",
            data={"user_id": user_id},
            files={"file": ("dup.txt", content, "text/plain")},
        )
        self.assertEqual(first_resp.status_code, 200)
        first_payload = first_resp.json()

        duplicate_resp = self.client.post(
            "/knowledge/upload",
            data={"user_id": user_id},
            files={"file": ("dup-copy.txt", content, "text/plain")},
        )
        self.assertEqual(duplicate_resp.status_code, 200)
        duplicate_payload = duplicate_resp.json()
        self.assertEqual(duplicate_payload["file_id"], first_payload["file_id"])
        self.assertEqual(duplicate_payload["ingestion_report"]["status"], "duplicate")
        self.assertEqual(duplicate_payload["ingestion_report"]["duplicate_of_file_id"], first_payload["file_id"])
        self.assertEqual(duplicate_payload["document_profile"]["short_summary"], first_payload["document_profile"]["short_summary"])

        list_resp = self.client.get(f"/knowledge/files/{user_id}")
        self.assertEqual(len(list_resp.json()), 1)

    def test_knowledge_hybrid_retrieval_uses_keyword_fallback(self):
        user_id = f"u-knowledge-hybrid-{uuid4()}"
        for idx in range(5):
            upload_resp = self.client.post(
                "/knowledge/upload",
                data={"user_id": user_id},
                files={
                    "file": (
                        f"background_{idx}.txt",
                        f"普通背景文档 {idx}，用于制造向量候选池噪声。",
                        "text/plain",
                    )
                },
            )
            self.assertEqual(upload_resp.status_code, 200)

        exact_resp = self.client.post(
            "/knowledge/upload",
            data={"user_id": user_id},
            files={
                "file": (
                    "hybrid_keyword_note.txt",
                    "项目代号 ZXQ9000 的部署窗口是周五晚上。",
                    "text/plain",
                )
            },
        )
        self.assertEqual(exact_resp.status_code, 200)
        exact_payload = exact_resp.json()

        query_resp = self.client.post(
            "/knowledge/query",
            json={"user_id": user_id, "query": "ZXQ9000", "top_k": 1},
        )
        self.assertEqual(query_resp.status_code, 200)
        hits = query_resp.json()["hits"]
        self.assertEqual(len(hits), 1)
        top_hit = hits[0]
        self.assertEqual(top_hit["file_id"], exact_payload["file_id"])
        self.assertIn("keyword", top_hit["retrieval_mode"])
        self.assertGreater(top_hit["keyword_score"], 0)
        self.assertGreater(top_hit["retrieval_score"], 0)
        self.assertIn("selected_by", top_hit["retrieval_explanation"])

    def test_knowledge_rerank_policy_keeps_file_diversity(self):
        user_id = f"u-knowledge-rerank-{uuid4()}"
        repeated_paragraph = "ALPHA_POLICY 同文件长段落，用于测试同文件 chunk 多样性。" * 18
        primary_content = "\n\n".join([repeated_paragraph for _ in range(4)])
        primary_resp = self.client.post(
            "/knowledge/upload",
            data={"user_id": user_id},
            files={"file": ("alpha_primary.txt", primary_content, "text/plain")},
        )
        self.assertEqual(primary_resp.status_code, 200)
        secondary_resp = self.client.post(
            "/knowledge/upload",
            data={"user_id": user_id},
            files={"file": ("alpha_secondary.txt", "ALPHA_POLICY 另一个文件中的补充证据。", "text/plain")},
        )
        self.assertEqual(secondary_resp.status_code, 200)

        query_resp = self.client.post(
            "/knowledge/query",
            json={"user_id": user_id, "query": "ALPHA_POLICY", "top_k": 2},
        )
        self.assertEqual(query_resp.status_code, 200)
        hits = query_resp.json()["hits"]
        self.assertEqual(len(hits), 2)
        self.assertEqual([hit["final_rank"] for hit in hits], [1, 2])
        self.assertEqual({hit["file_id"] for hit in hits}, {primary_resp.json()["file_id"], secondary_resp.json()["file_id"]})
        self.assertTrue(all(hit["selection_status"] == "selected" for hit in hits))
        self.assertTrue(all(hit["selection_explanation"]["max_chunks_per_file"] == 1 for hit in hits))

    def test_knowledge_document_qa_is_file_scoped_and_cited(self):
        user_id = f"u-knowledge-qa-{uuid4()}"
        selected_resp = self.client.post(
            "/knowledge/upload",
            data={"user_id": user_id},
            files={"file": ("selected_doc.txt", "项目 Phoenix 的上线窗口是周五晚上。", "text/plain")},
        )
        self.assertEqual(selected_resp.status_code, 200)
        other_resp = self.client.post(
            "/knowledge/upload",
            data={"user_id": user_id},
            files={"file": ("other_doc.txt", "项目 Phoenix 的上线窗口是周一早上。", "text/plain")},
        )
        self.assertEqual(other_resp.status_code, 200)

        qa_resp = self.client.post(
            "/knowledge/qa",
            json={
                "user_id": user_id,
                "file_id": selected_resp.json()["file_id"],
                "question": "Phoenix 的上线窗口是什么时候？",
                "top_k": 3,
            },
        )
        self.assertEqual(qa_resp.status_code, 200)
        payload = qa_resp.json()
        self.assertEqual(payload["answer_status"], "answered")
        self.assertEqual(payload["file_id"], selected_resp.json()["file_id"])
        self.assertGreater(payload["evidence_count"], 0)
        self.assertTrue(payload["citations"])
        self.assertTrue(payload["hits"])
        self.assertTrue(all(hit["file_id"] == selected_resp.json()["file_id"] for hit in payload["hits"]))
        self.assertIn("周五", payload["answer"])
        self.assertNotIn("周一", payload["answer"])

    def test_knowledge_document_qa_reports_not_enough_evidence(self):
        user_id = f"u-knowledge-qa-miss-{uuid4()}"
        upload_resp = self.client.post(
            "/knowledge/upload",
            data={"user_id": user_id},
            files={"file": ("ml_doc.txt", "机器学习是一门研究如何让计算机从数据中学习的学科。", "text/plain")},
        )
        self.assertEqual(upload_resp.status_code, 200)

        qa_resp = self.client.post(
            "/knowledge/qa",
            json={
                "user_id": user_id,
                "file_id": upload_resp.json()["file_id"],
                "question": "火星基地的预算是多少？",
                "top_k": 3,
            },
        )
        self.assertEqual(qa_resp.status_code, 200)
        payload = qa_resp.json()
        self.assertEqual(payload["answer_status"], "not_enough_evidence")
        self.assertEqual(payload["evidence_count"], 0)
        self.assertEqual(payload["hits"], [])

    def test_task_endpoint_runs_tool(self):
        response = self.client.post(
            "/task",
            json={"user_id": "u-task", "content": "calculate 2+3*4"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["plan"]["tool_name"], "calculator")
        self.assertEqual(payload["result"]["steps"][0]["result"]["data"]["value"], 14)

    def test_task_endpoint_runs_multi_step_chain(self):
        response = self.client.post(
            "/task",
            json={"user_id": "u-task-chain", "content": "先获取现在时间，再计算距离晚上8点还有多久"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual(len(payload["plan"]["steps"]), 2)
        self.assertEqual(payload["plan"]["steps"][0]["tool_name"], "datetime_info")
        self.assertEqual(payload["plan"]["steps"][1]["tool_name"], "calculator")
        self.assertEqual(len(payload["result"]["steps"]), 2)
        self.assertIn("current_hour", payload["result"]["context"])
        self.assertIn("remaining_hours", payload["result"]["context"])
        self.assertIn("remaining", payload["result"]["summary"].lower())

    def test_task_endpoint_runs_text_stats_reading_time_chain(self):
        response = self.client.post(
            "/task",
            json={"user_id": "u-task-reading", "content": "统计阅读时间：hello world from myai"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual(len(payload["plan"]["steps"]), 2)
        self.assertEqual(payload["plan"]["steps"][0]["tool_name"], "text_stats")
        self.assertEqual(payload["plan"]["steps"][1]["tool_name"], "calculator")
        self.assertIn("word_count", payload["result"]["context"])
        self.assertIn("reading_minutes", payload["result"]["context"])

    def test_task_endpoint_runs_system_summary_chain(self):
        response = self.client.post(
            "/task",
            json={"user_id": "u-task-system", "content": "请获取系统信息并做一个简短总结"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual(len(payload["plan"]["steps"]), 1)
        self.assertEqual(payload["plan"]["steps"][0]["tool_name"], "system_info")
        self.assertIn("System summary", payload["result"]["summary"])

    @patch("app.task.tools.weather_tool.requests.get")
    def test_task_endpoint_runs_weather_tool(self, mock_get):
        mock_get.side_effect = [
            FakeResponse(
                {
                    "results": [
                        {
                            "name": "Shanghai",
                            "country": "China",
                            "latitude": 31.23,
                            "longitude": 121.47,
                            "timezone": "Asia/Shanghai",
                        }
                    ]
                }
            ),
            FakeResponse(
                {
                    "timezone": "Asia/Shanghai",
                    "current": {
                        "temperature_2m": 25.4,
                        "apparent_temperature": 26.1,
                        "wind_speed_10m": 12.3,
                        "weather_code": 2,
                    },
                }
            ),
        ]

        response = self.client.post(
            "/task",
            json={"user_id": "u-task-weather", "content": "请查询上海天气"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["plan"]["tool_name"], "weather")
        self.assertEqual(payload["result"]["steps"][0]["result"]["data"]["location"], "Shanghai")

    @patch("app.task.tools.web_search.requests.get")
    def test_task_endpoint_runs_web_search_tool(self, mock_get):
        mock_get.return_value = FakeResponse(
            {
                "Heading": "OpenAI",
                "AbstractText": "OpenAI is an AI research and deployment company.",
                "AbstractURL": "https://openai.com",
                "RelatedTopics": [
                    {"Text": "GPT - Generative pre-trained transformer", "FirstURL": "https://example.com/gpt"}
                ],
            }
        )

        response = self.client.post(
            "/task",
            json={"user_id": "u-task-search", "content": "搜索 OpenAI"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["plan"]["tool_name"], "web_search")
        self.assertEqual(payload["result"]["steps"][0]["result"]["data"]["query"], "OpenAI")
        self.assertTrue(payload["result"]["steps"][0]["result"]["data"]["results"])

    def test_task_endpoint_runs_file_summary_tool(self):
        upload_resp = self.client.post(
            "/knowledge/upload",
            data={"user_id": "u-task-file"},
            files={
                "file": (
                    "ml_notes.txt",
                    "机器学习是一门研究如何让计算机从数据中学习的学科。\n监督学习和无监督学习是两类常见方法。",
                    "text/plain",
                )
            },
        )
        self.assertEqual(upload_resp.status_code, 200)

        response = self.client.post(
            "/task",
            json={"user_id": "u-task-file", "content": "请总结文件 ml_notes.txt"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["plan"]["tool_name"], "file_summary")
        summary_data = payload["result"]["steps"][0]["result"]["data"]
        self.assertEqual(summary_data["file_name"], "ml_notes.txt")
        self.assertTrue(summary_data["summary"])
        self.assertTrue(summary_data["highlights"])
        self.assertTrue(summary_data["document_profile"])
        self.assertTrue(summary_data["outline"])
        self.assertTrue(summary_data["keywords"])
        self.assertIn(summary_data["document_language"], {"zh", "mixed"})

    def test_task_endpoint_runs_memory_admin_policy_inspection(self):
        response = self.client.post(
            "/task",
            json={"user_id": "u-memory-admin-task", "content": "memory policy inspection"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["plan"]["tool_name"], "memory_admin")
        self.assertEqual(payload["plan"]["source"], "workflow")
        self.assertEqual(payload["plan"]["workflow"]["name"], "memory_policy_inspection")
        data = payload["result"]["steps"][0]["result"]["data"]
        self.assertEqual(data["operation"], "policy_inspection")
        self.assertGreater(data["slot_count"], 0)
        self.assertIn("confidence_calibration_policy", data)

    def test_task_workflows_endpoint_lists_registry(self):
        response = self.client.get("/task/workflows")

        self.assertEqual(response.status_code, 200)
        workflows = response.json()["workflows"]
        names = {workflow["name"] for workflow in workflows}
        self.assertIn("memory_policy_inspection", names)
        self.assertIn("knowledge_file_summary", names)
        memory_policy = next(workflow for workflow in workflows if workflow["name"] == "memory_policy_inspection")
        self.assertEqual(memory_policy["required_tools"], ["memory_admin"])
        self.assertEqual(memory_policy["steps"][0]["tool_name"], "memory_admin")

    def test_task_runtime_run_can_be_fetched_after_sync_task(self):
        response = self.client.post(
            "/task",
            json={"user_id": "u-task-runtime", "content": "hello"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["task_run_id"])
        self.assertEqual(payload["status"], "succeeded")
        self.assertTrue(payload["success"])
        event_types = [event["type"] for event in payload["events"]]
        self.assertIn("task.created", event_types)
        self.assertIn("task.planning.started", event_types)
        self.assertIn("task.planning.completed", event_types)
        self.assertIn("task.completed", event_types)

        run_response = self.client.get(
            f"/task/runs/{payload['task_run_id']}?user_id=u-task-runtime"
        )
        self.assertEqual(run_response.status_code, 200)
        run = run_response.json()
        self.assertEqual(run["task_run_id"], payload["task_run_id"])
        self.assertEqual(run["status"], "succeeded")
        self.assertEqual(run["content"], "hello")
        self.assertEqual(run["result"], payload["result"])
        self.assertEqual(run["events"], payload["events"])

    def test_task_run_get_and_cancel_reject_non_owner(self):
        response = self.client.post(
            "/task",
            json={"user_id": "u-task-owner", "content": "hello owner"},
        )
        self.assertEqual(response.status_code, 200)
        task_run_id = response.json()["task_run_id"]

        get_response = self.client.get(
            f"/task/runs/{task_run_id}?user_id=u-task-intruder"
        )
        cancel_response = self.client.post(
            f"/task/runs/{task_run_id}/cancel",
            json={"user_id": "u-task-intruder"},
        )

        self.assertEqual(get_response.status_code, 404)
        self.assertEqual(cancel_response.status_code, 404)
        owner_response = self.client.get(
            f"/task/runs/{task_run_id}?user_id=u-task-owner"
        )
        self.assertEqual(owner_response.status_code, 200)
        self.assertEqual(owner_response.json()["user_id"], "u-task-owner")

    def test_task_runtime_marks_missing_tool_step_failed(self):
        registry = ToolRegistry()
        stats = StatsManager(registry=registry, config=TaskConfig())
        service = TaskService(
            rec_planner=FakeMissingToolPlanner(),
            task_executor=ToolExecutor(registry),
            stats=stats,
        )

        decision = service.handle_task("force missing tool", user_id="u-task-runtime-fail")

        self.assertEqual(decision.status, "failed")
        self.assertFalse(decision.success)
        self.assertIn("missing_tool", decision.error)
        run = service.get_run(decision.task_run_id)
        self.assertIsNotNone(run)
        self.assertEqual(run["status"], "failed")
        self.assertEqual(run["steps"][0]["status"], "failed")
        self.assertIn("missing_tool", run["steps"][0]["error"])
        event_types = [event["type"] for event in run["events"]]
        self.assertIn("task.step.started", event_types)
        self.assertIn("task.step.failed", event_types)
        self.assertIn("task.failed", event_types)

    def test_task_planning_uses_memory_context_with_citations(self):
        user_id = "u-task-memory-aware"
        embedding = StubEmbedding()
        memory_store = MemoryStore()
        memory_store.add_item(
            user_id,
            MemoryItem(
                content="User prefers concise task summaries with explicit next steps.",
                vector=embedding.embed("concise task summaries next steps"),
                mem_type="preference",
                metadata={
                    "slot": "task_summary_style",
                    "value": "concise with next steps",
                    "source": "test_fixture",
                    "review_status": "accepted",
                    "is_current": True,
                    "retrieval_enabled": True,
                    "sensitivity": "normal",
                },
            ),
        )
        memory_service = MemoryService(embedding_client=embedding, memory_store=memory_store)
        registry = ToolRegistry()
        stats = StatsManager(registry=registry, config=TaskConfig())
        planner = CapturingNoToolPlanner()
        service = TaskService(
            rec_planner=planner,
            task_executor=ToolExecutor(registry),
            stats=stats,
            memory_service=memory_service,
        )

        decision = service.handle_task("Plan how to summarize this task", user_id=user_id)

        self.assertEqual(decision.status, "succeeded")
        self.assertTrue(any("concise task summaries" in item for item in planner.short_context))
        self.assertTrue(decision.plan["memory_context"]["selected"])
        citation = decision.plan["memory_context"]["selected"][0]
        self.assertEqual(citation["mem_type"], "preference")
        self.assertEqual(citation["slot"], "task_summary_style")
        run = service.get_run(decision.task_run_id)
        event_types = [event["type"] for event in run["events"]]
        self.assertIn("task.memory_retrieval.started", event_types)
        self.assertIn("task.memory_retrieval.completed", event_types)
        completed_event = next(event for event in run["events"] if event["type"] == "task.memory_retrieval.completed")
        self.assertEqual(completed_event["metadata"]["selected_count"], 1)

    def test_task_tool_policy_records_allowed_decision(self):
        registry = ToolRegistry()
        registry.register(CalculatorTool())
        stats = StatsManager(registry=registry, config=TaskConfig())
        service = TaskService(
            rec_planner=FakeToolPlanner("calculator", {"expression": "1 + 2"}),
            task_executor=ToolExecutor(registry),
            stats=stats,
        )

        decision = service.handle_task("calculate 1 + 2", user_id="u-task-policy")

        self.assertEqual(decision.status, "succeeded")
        run = service.get_run(decision.task_run_id)
        event_types = [event["type"] for event in run["events"]]
        self.assertIn("task.tool_policy.allowed", event_types)
        policy_event = next(event for event in run["events"] if event["type"] == "task.tool_policy.allowed")
        self.assertEqual(policy_event["metadata"]["tool_policy"]["risk_level"], "safe")

    def test_task_success_writes_pending_outcome_memory(self):
        user_id = "u-task-outcome-memory"
        embedding = StubEmbedding()
        memory_store = MemoryStore()
        memory_service = MemoryService(embedding_client=embedding, memory_store=memory_store)
        registry = ToolRegistry()
        registry.register(CalculatorTool())
        stats = StatsManager(registry=registry, config=TaskConfig())
        service = TaskService(
            rec_planner=FakeToolPlanner("calculator", {"expression": "2 + 3"}),
            task_executor=ToolExecutor(registry),
            stats=stats,
            memory_service=memory_service,
        )

        decision = service.handle_task("calculate 2 + 3 for my report", user_id=user_id)

        self.assertEqual(decision.status, "succeeded")
        self.assertTrue(decision.result["outcome_memory"]["written"])
        memories = memory_store.get_all(user_id)
        self.assertEqual(len(memories), 1)
        outcome = memories[0]
        self.assertEqual(outcome.metadata["source"], "task_outcome")
        self.assertEqual(outcome.metadata["review_status"], "pending")
        self.assertEqual(outcome.metadata["slot"], "task_workflow")
        source_ref = governance_response_fields(outcome.metadata)["source_ref"]
        self.assertEqual(source_ref["task_run_id"], decision.task_run_id)
        run = service.get_run(decision.task_run_id)
        event_types = [event["type"] for event in run["events"]]
        self.assertIn("task.outcome_memory.started", event_types)
        self.assertIn("task.outcome_memory.completed", event_types)

    def test_task_tool_policy_blocks_confirmation_required_tool(self):
        registry = ToolRegistry()
        registry.register(MemoryAdminTool())
        stats = StatsManager(registry=registry, config=TaskConfig())
        service = TaskService(
            rec_planner=FakeToolPlanner("memory_admin", {"operation": "maintenance"}),
            task_executor=ToolExecutor(registry),
            stats=stats,
        )

        decision = service.handle_task("memory maintenance", user_id="u-task-policy-sensitive")

        self.assertEqual(decision.status, "failed")
        self.assertFalse(decision.success)
        self.assertIn("requires confirmation", decision.error)
        run = service.get_run(decision.task_run_id)
        event_types = [event["type"] for event in run["events"]]
        self.assertIn("task.tool_policy.permission_required", event_types)
        policy_event = next(event for event in run["events"] if event["type"] == "task.tool_policy.permission_required")
        self.assertTrue(policy_event["metadata"]["permission_required"])
        self.assertEqual(policy_event["metadata"]["tool_policy"]["risk_level"], "sensitive")

    def test_task_executor_retries_retryable_tool_failure(self):
        registry = ToolRegistry()
        tool = FlakyRetryTool()
        registry.register(tool)
        stats = StatsManager(registry=registry, config=TaskConfig())
        service = TaskService(
            rec_planner=FakeToolPlanner("flaky_retry"),
            task_executor=ToolExecutor(registry),
            stats=stats,
        )

        decision = service.handle_task("retry flaky tool", user_id="u-task-retry")

        self.assertEqual(decision.status, "succeeded")
        self.assertTrue(decision.success)
        self.assertEqual(tool.calls, 2)
        metadata = decision.result["steps"][0]["result"]["metadata"]
        self.assertEqual(metadata["attempt"], 2)
        self.assertEqual(metadata["recovery_status"], "succeeded_after_retry")
        run = service.get_run(decision.task_run_id)
        event_types = [event["type"] for event in run["events"]]
        self.assertIn("task.step.recovery", event_types)

    def test_task_executor_timeout_produces_recovery_recommendation(self):
        registry = ToolRegistry()
        registry.register(SlowTimeoutTool())
        stats = StatsManager(registry=registry, config=TaskConfig())
        service = TaskService(
            rec_planner=FakeToolPlanner("slow_timeout"),
            task_executor=ToolExecutor(registry),
            stats=stats,
        )
        self.addCleanup(service.close)

        decision = service.handle_task("run slow timeout", user_id="u-task-timeout")

        self.assertEqual(decision.status, "failed")
        self.assertFalse(decision.success)
        metadata = decision.result["steps"][0]["result"]["metadata"]
        self.assertEqual(metadata["recovery_status"], "not_retryable")
        self.assertTrue(metadata["outcome_unknown"])
        self.assertFalse(metadata["retryable"])
        self.assertIn("cannot prove", metadata["retry_suppressed_reason"])
        self.assertIn("timed out", decision.error)
        self.assertIn("tool timed out", metadata["recovery_recommendation"])
        run = service.get_run(decision.task_run_id)
        event_types = [event["type"] for event in run["events"]]
        self.assertIn("task.step.recovery", event_types)
        self.assertIn("task.step.failed", event_types)

    def test_background_task_endpoint_starts_and_can_be_fetched(self):
        response = self.client.post(
            "/task/runs",
            json={"user_id": "u-task-background", "content": "hello background"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["task_run_id"])
        self.assertIn(payload["status"], {"queued", "planning", "running", "succeeded"})

        task_run_id = payload["task_run_id"]
        run = None
        for _ in range(20):
            run_response = self.client.get(
                f"/task/runs/{task_run_id}?user_id=u-task-background"
            )
            self.assertEqual(run_response.status_code, 200)
            run = run_response.json()
            if run["status"] in {"succeeded", "failed", "cancelled"}:
                break
            time.sleep(0.02)

        self.assertIsNotNone(run)
        self.assertEqual(run["task_run_id"], task_run_id)
        self.assertEqual(run["status"], "succeeded")
        event_types = [event["type"] for event in run["events"]]
        self.assertIn("task.queued", event_types)
        self.assertIn("task.completed", event_types)

    def test_task_run_list_endpoint_returns_user_runs(self):
        missing_user_response = self.client.get("/task/runs?limit=5")
        self.assertEqual(missing_user_response.status_code, 422)

        response = self.client.post(
            "/task",
            json={"user_id": "u-task-list", "content": "hello list"},
        )
        self.assertEqual(response.status_code, 200)
        task_run_id = response.json()["task_run_id"]

        list_response = self.client.get("/task/runs?user_id=u-task-list&limit=5")
        self.assertEqual(list_response.status_code, 200)
        runs = list_response.json()["runs"]
        self.assertTrue(runs)
        self.assertEqual(runs[0]["task_run_id"], task_run_id)
        self.assertEqual(runs[0]["content"], "hello list")

    def test_task_tools_endpoint_lists_local_tools(self):
        response = self.client.get("/task/tools")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertGreaterEqual(payload["summary"]["total"], 1)
        self.assertGreaterEqual(payload["summary"]["local"], 1)
        tool_names = {tool["name"] for tool in payload["tools"]}
        self.assertIn("file_summary", tool_names)
        self.assertIn("knowledge_admin", tool_names)
        file_summary = next(tool for tool in payload["tools"] if tool["name"] == "file_summary")
        self.assertEqual(file_summary["source"], "local")
        self.assertIn("policy", file_summary)
        self.assertIn("schema", file_summary)
        self.assertGreaterEqual(payload["summary"]["connectors"], 1)
        connectors = payload["connectors"]
        self.assertFalse(any(connector["server_id"] == "filesystem-readonly" for connector in connectors))
        git = next(connector for connector in connectors if connector["server_id"] == "git-readonly")
        self.assertTrue(git["enabled"])
        self.assertGreaterEqual(git["tool_count"], 3)
        self.assertEqual(git["risk_summary"]["risk_level"], "filesystem/read")

    def test_background_task_can_be_cancelled_between_steps(self):
        registry = ToolRegistry()
        registry.register(SlowSuccessTool())
        registry.register(CalculatorTool())
        stats = StatsManager(registry=registry, config=TaskConfig())
        service = TaskService(
            rec_planner=FakeMultiStepPlanner(
                [
                    ToolStep(
                        step_id="step1",
                        description="Run slow first step",
                        tool_name="slow_success",
                        tool_args={},
                    ),
                    ToolStep(
                        step_id="step2",
                        description="Should not run after cancellation",
                        tool_name="calculator",
                        tool_args={"expression": "1 + 1"},
                    ),
                ]
            ),
            task_executor=ToolExecutor(registry),
            stats=stats,
        )

        started = service.start_background_task("run cancellable task", user_id="u-task-cancel")
        task_run_id = started["task_run_id"]
        for _ in range(30):
            run = service.get_run(task_run_id)
            if run["current_step_id"] == "step1":
                break
            time.sleep(0.01)
        cancelled = service.request_cancel(task_run_id)
        self.assertTrue(cancelled["cancel_requested"])

        run = None
        for _ in range(30):
            run = service.get_run(task_run_id)
            if run["status"] in {"succeeded", "failed", "cancelled"}:
                break
            time.sleep(0.02)

        self.assertIsNotNone(run)
        self.assertEqual(run["status"], "cancelled")
        self.assertEqual(run["steps"][0]["status"], "succeeded")
        self.assertEqual(run["steps"][1]["status"], "queued")
        event_types = [event["type"] for event in run["events"]]
        self.assertIn("task.cancel_requested", event_types)
        self.assertIn("task.cancelled", event_types)

    def test_memory_admin_tool_workflows(self):
        settings_dir = ".memory_settings_test"
        shutil.rmtree(settings_dir, ignore_errors=True)
        try:
            settings_store = MemorySettingsStore(settings_dir)
            service = MemoryService(
                embedding_client=StubEmbedding(),
                memory_store=MemoryStore(),
                settings_store=settings_store,
            )
            tool = MemoryAdminTool(memory_service=service, settings_store=settings_store)
            user_id = "u-memory-admin-tool"
            service.process_user_input(user_id, "I like Python")
            service.process_user_input(user_id, "I like JavaScript")

            maintenance = tool.run(operation="maintenance", user_id=user_id)
            self.assertTrue(maintenance.success)
            self.assertEqual(maintenance.data["operation"], "maintenance")
            self.assertIn("summary", maintenance.data)

            report = tool.run(operation="eval_report")
            self.assertTrue(report.success)
            self.assertEqual(report.data["operation"], "eval_report")
            self.assertGreater(report.data["report"]["summary"]["total"], 0)

            policy = tool.run(operation="policy_inspection", mem_type="preference", slot="preference")
            self.assertTrue(policy.success)
            self.assertEqual(policy.data["slots"][0]["slot"], "preference")

            preview = tool.run(operation="settings_preview", user_id=user_id)
            self.assertTrue(preview.success)
            self.assertEqual(preview.data["status"], "persisted")
            self.assertTrue(preview.data["settings"]["memory_enabled"])

            updated = tool.run(
                operation="update_settings",
                user_id=user_id,
                settings={"auto_write_enabled": False, "default_memory_view": "audit"},
            )
            self.assertTrue(updated.success)
            self.assertFalse(updated.data["settings"]["auto_write_enabled"])
            self.assertEqual(updated.data["settings"]["default_memory_view"], "audit")

            persisted = tool.run(operation="get_settings", user_id=user_id)
            self.assertFalse(persisted.data["settings"]["auto_write_enabled"])
            blocked = service.process_user_input(user_id, "I like Rust")
            self.assertFalse(blocked["written"])
            self.assertEqual(blocked["reason"], "automatic memory write disabled by user settings")
        finally:
            shutil.rmtree(settings_dir, ignore_errors=True)

    def test_knowledge_admin_tool_workflows(self):
        test_dir = f".tmp/knowledge-admin-test-{uuid4()}"
        base_dir = f"{test_dir}/knowledge"
        persist_dir = f"{test_dir}/chroma"
        try:
            service = KnowledgeService(persist_dir=persist_dir, base_dir=base_dir, embedding_client=StubEmbedding())
            user_id = "u-knowledge-admin-tool"
            first = service.upload_file(
                user_id,
                "phoenix.txt",
                "项目 Phoenix 的上线窗口是周五晚上。需要准备回滚方案。".encode("utf-8"),
            )
            second = service.upload_file(
                user_id,
                "atlas.txt",
                "项目 Atlas 的关键结论是先完成知识引用审计。".encode("utf-8"),
            )
            tool = KnowledgeAdminTool(knowledge_service=service)

            qa = tool.run(
                operation="document_qa",
                user_id=user_id,
                file_id=first["file_id"],
                question="Phoenix 的上线窗口是什么时候？",
            )
            self.assertTrue(qa.success)
            self.assertEqual(qa.data["answer_status"], "answered")
            self.assertTrue(qa.data["citations"])

            notes = tool.run(operation="study_notes", user_id=user_id, file_id=first["file_id"])
            self.assertTrue(notes.success)
            self.assertIn("summary", notes.data)
            self.assertTrue(notes.data["citations"])

            cards = tool.run(operation="qa_cards", user_id=user_id, file_id=first["file_id"])
            self.assertTrue(cards.success)
            self.assertGreater(cards.data["card_count"], 0)

            comparison = tool.run(
                operation="compare_documents",
                user_id=user_id,
                file_id=first["file_id"],
                other_file_id=second["file_id"],
            )
            self.assertTrue(comparison.success)
            self.assertEqual(len(comparison.data["files"]), 2)

            maintenance = tool.run(operation="maintenance", user_id=user_id, dry_run=True)
            self.assertTrue(maintenance.success)
            self.assertEqual(maintenance.data["report"]["dry_run"], True)

            report = tool.run(operation="eval_report", report_format="summary")
            self.assertTrue(report.success)
            self.assertEqual(report.data["report"]["summary"]["failed"], 0)
        finally:
            shutil.rmtree(test_dir, ignore_errors=True)

    def test_knowledge_workflows_are_registered_and_executable(self):
        test_dir = f".tmp/knowledge-workflow-test-{uuid4()}"
        base_dir = f"{test_dir}/knowledge"
        persist_dir = f"{test_dir}/chroma"
        try:
            knowledge_service = KnowledgeService(persist_dir=persist_dir, base_dir=base_dir, embedding_client=StubEmbedding())
            upload = knowledge_service.upload_file(
                "u-knowledge-workflow",
                "workflow_doc.txt",
                "Workflow documents can produce study notes and citations for task timelines.".encode("utf-8"),
            )
            registry = ToolRegistry()
            registry.register_many(
                [
                    FileSummaryTool(knowledge_service=knowledge_service),
                    KnowledgeAdminTool(knowledge_service=knowledge_service),
                ]
            )
            stats = StatsManager(registry=registry, config=TaskConfig())
            planner = ToolPlanner(registry=registry, stats=stats, config=TaskConfig(), workflow_registry=build_default_workflow_registry())
            plan = planner.plan("make study notes for workflow_doc.txt")
            self.assertEqual(plan.source, "workflow")
            self.assertEqual(plan.workflow["name"], "knowledge_study_notes")
            self.assertEqual(plan.normalized_steps()[0].tool_name, "knowledge_admin")

            service = TaskService(rec_planner=planner, task_executor=ToolExecutor(registry), stats=stats)
            decision = service.handle_task("make study notes for workflow_doc.txt", user_id="u-knowledge-workflow")
            self.assertTrue(decision.success)
            self.assertEqual(decision.plan["workflow"]["name"], "knowledge_study_notes")
            step = decision.result["steps"][0]
            self.assertEqual(step["tool_name"], "knowledge_admin")
            self.assertEqual(step["result"]["data"]["file_id"], upload["file_id"])
            self.assertTrue(step["result"]["data"]["citations"])
            run = service.get_run(decision.task_run_id)
            self.assertIn("task.step.completed", [event["type"] for event in run["events"]])

            workflows = service.list_workflows()
            workflow_names = {workflow["name"] for workflow in workflows}
            self.assertIn("knowledge_document_qa", workflow_names)
            self.assertIn("knowledge_eval_report", workflow_names)
        finally:
            shutil.rmtree(test_dir, ignore_errors=True)

    def test_mcp_filesystem_workflows_are_registered_and_executable(self):
        root = Path.cwd() / ".tmp" / f"mcp-workflow-test-{uuid4()}"
        try:
            root.mkdir(parents=True, exist_ok=True)
            target = root / "mcp_workflow.txt"
            target.write_text("MCP workflow integration can read project files through a stable workflow.", encoding="utf-8")
            registry = ToolRegistry()
            client = ReadOnlyFilesystemMCPClient({"workspace": root})
            MCPToolRegistryLoader(
                [MCPServerConfig(server_id=client.server_id, name="Filesystem Read-Only", risk_level="filesystem/read")],
                client,
            ).register_into(registry)
            stats = StatsManager(registry=registry, config=TaskConfig())
            planner = ToolPlanner(registry=registry, stats=stats, config=TaskConfig(), workflow_registry=build_default_workflow_registry())

            read_plan = planner.plan("summarize project file mcp_workflow.txt")
            self.assertEqual(read_plan.source, "workflow")
            self.assertEqual(read_plan.workflow["name"], "mcp_filesystem_read_summary")
            self.assertEqual(read_plan.normalized_steps()[0].tool_name, "mcp__filesystem_readonly__read_text")
            self.assertEqual(read_plan.normalized_steps()[0].tool_args["path"], "mcp_workflow.txt")

            portable_demo_plan = planner.plan(
                "读取本地文件 sample-knowledge.txt，并列出 Aurora Lantern 的发布编号、演示时间和回滚编号。"
            )
            self.assertEqual(portable_demo_plan.source, "workflow")
            self.assertEqual(portable_demo_plan.workflow["name"], "mcp_filesystem_read_summary")
            self.assertEqual(
                portable_demo_plan.normalized_steps()[0].tool_name,
                "mcp__filesystem_readonly__read_text",
            )
            self.assertEqual(portable_demo_plan.normalized_steps()[0].tool_args["path"], "sample-knowledge.txt")

            search_plan = planner.plan('search project files "mcp_workflow" in .')
            self.assertEqual(search_plan.source, "workflow")
            self.assertEqual(search_plan.workflow["name"], "mcp_filesystem_search_plan")
            self.assertEqual(search_plan.normalized_steps()[0].tool_name, "mcp__filesystem_readonly__search_names")
            self.assertEqual(search_plan.normalized_steps()[0].tool_args["query"], "mcp_workflow")

            service = TaskService(rec_planner=planner, task_executor=ToolExecutor(registry), stats=stats)
            decision = service.handle_task("summarize project file mcp_workflow.txt", user_id="u-mcp-workflow")
            self.assertTrue(decision.success)
            self.assertEqual(decision.plan["workflow"]["name"], "mcp_filesystem_read_summary")
            self.assertIn("MCP workflow integration", decision.result["summary"])
            run = service.get_run(decision.task_run_id)
            event_types = [event["type"] for event in run["events"]]
            self.assertIn("task.mcp_call.completed", event_types)

            workflows = service.list_workflows()
            workflow_names = {workflow["name"] for workflow in workflows}
            self.assertIn("mcp_filesystem_read_summary", workflow_names)
            self.assertIn("mcp_filesystem_search_plan", workflow_names)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_mcp_git_workflows_are_registered_and_executable(self):
        registry = ToolRegistry()
        client = GitReadOnlyMCPClient(Path.cwd().parent)
        MCPToolRegistryLoader(
            [MCPServerConfig(server_id=client.server_id, name="Git Read-Only", risk_level="filesystem/read")],
            client,
        ).register_into(registry)
        stats = StatsManager(registry=registry, config=TaskConfig())
        planner = ToolPlanner(registry=registry, stats=stats, config=TaskConfig(), workflow_registry=build_default_workflow_registry())

        status_plan = planner.plan("review git status")
        self.assertEqual(status_plan.source, "workflow")
        self.assertEqual(status_plan.workflow["name"], "mcp_git_status_review")
        self.assertEqual(status_plan.normalized_steps()[0].tool_name, "mcp__git_readonly__status")

        log_plan = planner.plan("show recent commits")
        self.assertEqual(log_plan.source, "workflow")
        self.assertEqual(log_plan.workflow["name"], "mcp_git_recent_history")
        self.assertEqual(log_plan.normalized_steps()[0].tool_name, "mcp__git_readonly__log")

        service = TaskService(rec_planner=planner, task_executor=ToolExecutor(registry), stats=stats)
        decision = service.handle_task("review git status", user_id="u-mcp-git-workflow")
        self.assertTrue(decision.success)
        self.assertEqual(decision.plan["workflow"]["name"], "mcp_git_status_review")
        self.assertIn("Git status", decision.result["summary"])
        run = service.get_run(decision.task_run_id)
        self.assertIn("task.mcp_call.completed", [event["type"] for event in run["events"]])

        workflow_names = {workflow["name"] for workflow in service.list_workflows()}
        self.assertIn("mcp_git_status_review", workflow_names)
        self.assertIn("mcp_git_recent_history", workflow_names)

    def test_memory_settings_api_controls_default_memory_policy(self):
        user_id = "u-memory-settings-api"
        try:
            initial = self.client.get(f"/memory/settings/{user_id}")
            self.assertEqual(initial.status_code, 200)
            initial_payload = initial.json()
            self.assertTrue(initial_payload["settings"]["memory_enabled"])
            self.assertTrue(initial_payload["settings"]["auto_write_enabled"])
            self.assertEqual(initial_payload["settings"]["default_memory_view"], "simple")
            self.assertTrue(initial_payload["schema"])

            updated = self.client.patch(
                f"/memory/settings/{user_id}",
                json={"auto_write_enabled": False, "default_memory_view": "audit"},
            )
            self.assertEqual(updated.status_code, 200)
            updated_payload = updated.json()
            self.assertFalse(updated_payload["settings"]["auto_write_enabled"])
            self.assertEqual(updated_payload["settings"]["default_memory_view"], "audit")

            write_response = self.client.post(
                "/memory/write",
                json={"user_id": user_id, "content": "I like Go"},
            )
            self.assertEqual(write_response.status_code, 200)
            write_payload = write_response.json()
            self.assertFalse(write_payload["written"])
            self.assertEqual(write_payload["reason"], "automatic memory write disabled by user settings")
        finally:
            self.runtime.memory_service.settings_store.update(
                user_id,
                {
                    "memory_enabled": True,
                    "auto_write_enabled": True,
                    "sensitive_requires_confirmation": True,
                    "default_memory_view": "simple",
                },
            )

    def test_llm_multi_step_plan_is_parsed(self):
        registry = ToolRegistry()
        registry.register_many(
            [
                SystemInfoTool(),
                CalculatorTool(),
                DateTimeTool(),
                TextStatsTool(),
                WeatherTool(),
                WebSearchTool(),
                FileSummaryTool(),
            ]
        )
        planner = ToolPlanner(
            registry=registry,
            stats=StatsManager(registry=registry, config=TaskConfig()),
            config=TaskConfig(),
            client=FakePlannerLLM(),
        )

        plan = planner.llm_based_plan("estimate reading time", [])

        self.assertIsNotNone(plan)
        self.assertTrue(plan.need_tool)
        self.assertEqual(len(plan.steps), 2)
        self.assertEqual(plan.steps[0].tool_name, "text_stats")
        self.assertEqual(plan.steps[1].tool_args["expression"], "{word_count} / 200")

    def test_llm_no_tool_plan_normalizes_empty_tool_name_without_recovery_retries(self):
        registry = ToolRegistry()
        config = TaskConfig(max_retries=3)
        client = FakeNoToolPlannerLLM()
        planner = ToolPlanner(
            registry=registry,
            stats=StatsManager(registry=registry, config=config),
            config=config,
            client=client,
        )
        validator = ToolValidation(registry)
        recovery_planner = RecoveryPlanner(planner=planner, validator=validator, config=config)

        plan = recovery_planner.plan("answer directly without a tool")

        self.assertEqual(client.calls, 1)
        self.assertFalse(plan.need_tool)
        self.assertIsNone(plan.tool_name)
        self.assertEqual(plan.normalized_steps(), [])
        self.assertTrue(validator.validate_plan(plan).valid)

    def test_memory_governance_metadata_roundtrip(self):
        metadata = normalize_governance_metadata(
            base_metadata={"slot": "major", "value": "computer science"},
            content="my major is computer science",
            mem_type="fact",
            confidence=0.85,
            source="chat_extraction",
            source_ref={"conversation_id": 42, "message_id": "m-1"},
        )

        self.assertEqual(metadata["source"], "chat_extraction")
        self.assertEqual(metadata["source_conversation_id"], "42")
        self.assertEqual(metadata["source_message_id"], "m-1")
        self.assertEqual(metadata["scope"], "global")
        self.assertEqual(metadata["sensitivity"], "personal")
        self.assertEqual(metadata["review_status"], "accepted")
        self.assertEqual(metadata["review_reason"], "accepted by automatic governance policy")
        self.assertTrue(metadata["observed_at"])
        self.assertEqual(metadata["valid_from"], metadata["observed_at"])
        self.assertEqual(metadata["valid_to"], "")
        self.assertEqual(metadata["is_current"], True)

        response_fields = governance_response_fields(metadata)
        self.assertEqual(response_fields["source_ref"]["conversation_id"], "42")
        self.assertEqual(response_fields["source_ref"]["message_id"], "m-1")
        self.assertEqual(response_fields["extraction_reason"], "matched fact memory slot 'major'")
        self.assertEqual(response_fields["is_current"], True)

    def test_memory_governance_auto_pending_classification(self):
        sensitive_metadata = normalize_governance_metadata(
            base_metadata={"slot": "secret", "value": "password"},
            content="my password is 123456",
            mem_type="fact",
            confidence=0.95,
            source="chat_extraction",
            importance=5,
        )
        self.assertEqual(sensitive_metadata["sensitivity"], "sensitive")
        self.assertEqual(sensitive_metadata["sensitive_category"], "secret")
        self.assertEqual(sensitive_metadata["review_status"], "rejected")
        self.assertIn("secret", sensitive_metadata["review_reason"])

        password_manager_metadata = normalize_governance_metadata(
            base_metadata={"slot": "job", "value": "password manager"},
            content="my job is password manager",
            mem_type="fact",
            confidence=0.95,
            source="chat_extraction",
            importance=5,
        )
        self.assertFalse(is_high_risk_secret("my job is password manager"))
        self.assertEqual(password_manager_metadata["sensitivity"], "personal")
        self.assertEqual(password_manager_metadata["sensitive_category"], "none")
        self.assertEqual(password_manager_metadata["review_status"], "accepted")

        personal_sensitive_metadata = normalize_governance_metadata(
            base_metadata={"slot": "document", "value": "id card"},
            content="my id card expires next month",
            mem_type="fact",
            confidence=0.95,
            source="chat_extraction",
            importance=5,
        )
        self.assertEqual(personal_sensitive_metadata["sensitivity"], "sensitive")
        self.assertEqual(personal_sensitive_metadata["sensitive_category"], "personal_sensitive")
        self.assertEqual(personal_sensitive_metadata["review_status"], "pending")

        low_confidence_metadata = normalize_governance_metadata(
            base_metadata={"slot": "opinion", "value": "maybe useful"},
            content="I think maybe this is useful",
            mem_type="opinion",
            confidence=0.55,
            source="chat_extraction",
            importance=4,
        )
        self.assertEqual(low_confidence_metadata["review_status"], "pending")
        self.assertIn("confidence", low_confidence_metadata["review_reason"])
        self.assertEqual(low_confidence_metadata["raw_confidence"], 0.55)
        self.assertLess(low_confidence_metadata["calibrated_confidence"], low_confidence_metadata["raw_confidence"])
        self.assertIn("slot:opinion", low_confidence_metadata["confidence_calibration_factors"])

        calibrated_metadata = normalize_governance_metadata(
            base_metadata={
                "slot": "preference",
                "value": "concise answers",
                "extraction_method": "llm",
                "extraction_reason": "user implied response style preference",
            },
            content="I prefer concise answers",
            mem_type="preference",
            confidence=0.78,
            source="chat_extraction",
            importance=4,
        )
        self.assertEqual(calibrated_metadata["confidence"], 0.78)
        self.assertLess(calibrated_metadata["calibrated_confidence"], 0.78)
        self.assertIn("method:llm", calibrated_metadata["confidence_calibration_factors"])

    def test_memory_retrieval_governance_policy(self):
        memories = [
            RetrievedMemory(
                memory_id="accepted",
                content="accepted memory",
                similarity=0.82,
                mem_type="fact",
                mem_status="active",
                score=0.9,
                importance=5,
                confidence=0.9,
                review_status="accepted",
                sensitivity="personal",
            ),
            RetrievedMemory(
                memory_id="pending",
                content="pending memory",
                similarity=0.99,
                mem_type="fact",
                mem_status="active",
                score=1.0,
                importance=10,
                confidence=1.0,
                review_status="pending",
            ),
            RetrievedMemory(
                memory_id="rejected",
                content="rejected memory",
                similarity=0.99,
                mem_type="fact",
                mem_status="active",
                score=1.0,
                importance=10,
                confidence=1.0,
                review_status="rejected",
            ),
            RetrievedMemory(
                memory_id="sensitive",
                content="sensitive memory",
                similarity=0.99,
                mem_type="fact",
                mem_status="active",
                score=1.0,
                importance=10,
                confidence=1.0,
                sensitivity="sensitive",
            ),
            RetrievedMemory(
                memory_id="conversation-mismatch",
                content="conversation mismatch",
                similarity=0.98,
                mem_type="fact",
                mem_status="active",
                score=1.0,
                importance=10,
                confidence=1.0,
                scope="conversation",
                source_conversation_id="7",
            ),
            RetrievedMemory(
                memory_id="low-confidence",
                content="low confidence memory",
                similarity=0.90,
                mem_type="fact",
                mem_status="active",
                score=0.9,
                importance=5,
                confidence=0.4,
            ),
        ]

        selected = MemoryPolicy.filter_memories(memories, conversation_id=42)
        selected_ids = [memory.memory_id for memory in selected]

        self.assertIn("accepted", selected_ids)
        self.assertIn("low-confidence", selected_ids)
        self.assertNotIn("pending", selected_ids)
        self.assertNotIn("rejected", selected_ids)
        self.assertNotIn("sensitive", selected_ids)
        self.assertNotIn("conversation-mismatch", selected_ids)

        decisions = MemoryPolicy.explain_memories(memories, conversation_id=42)
        by_id = {decision.memory.memory_id: decision for decision in decisions}
        self.assertTrue(by_id["accepted"].selected)
        self.assertEqual(by_id["accepted"].reason, "selected by retrieval score")
        self.assertGreater(by_id["accepted"].final_score, 0)
        self.assertEqual(by_id["accepted"].factors["confidence"], 0.9)
        self.assertEqual(by_id["accepted"].factors["raw_confidence"], 1.0)
        self.assertFalse(by_id["pending"].selected)
        self.assertIn("pending", by_id["pending"].reason)
        self.assertFalse(by_id["rejected"].selected)
        self.assertIn("rejected", by_id["rejected"].reason)
        self.assertFalse(by_id["sensitive"].selected)
        self.assertIn("sensitive", by_id["sensitive"].reason)
        self.assertFalse(by_id["conversation-mismatch"].selected)
        self.assertIn("scope", by_id["conversation-mismatch"].reason)

    def test_memory_retrieval_uses_slot_retrieval_weight(self):
        memories = [
            RetrievedMemory(
                memory_id="generic",
                content="generic fact",
                similarity=0.80,
                mem_type="fact",
                mem_status="active",
                score=0.8,
                importance=5,
                confidence=0.9,
                slot="identity",
                retrieval_weight=1.0,
            ),
            RetrievedMemory(
                memory_id="weighted",
                content="important preference",
                similarity=0.78,
                mem_type="preference",
                mem_status="active",
                score=0.8,
                importance=5,
                confidence=0.9,
                slot="preference",
                retrieval_weight=1.2,
            ),
        ]

        decisions = MemoryPolicy.explain_memories(memories)
        by_id = {decision.memory.memory_id: decision for decision in decisions}

        self.assertGreater(by_id["weighted"].final_score, by_id["generic"].final_score)
        self.assertEqual(by_id["weighted"].factors["slot_weight"], 1.2)
        self.assertEqual(by_id["weighted"].factors["retrieval_weight"], 1.2)

    def test_memory_retrieval_uses_freshness_for_time_sensitive_memories(self):
        recent = datetime.now(timezone.utc).isoformat()
        old = (datetime.now(timezone.utc) - timedelta(days=900)).isoformat()
        memories = [
            RetrievedMemory(
                memory_id="old-decision",
                content="old decision",
                similarity=0.82,
                mem_type="decision",
                mem_status="active",
                score=0.8,
                importance=5,
                confidence=0.9,
                source="chat_extraction",
                observed_at=old,
            ),
            RetrievedMemory(
                memory_id="recent-decision",
                content="recent decision",
                similarity=0.76,
                mem_type="decision",
                mem_status="active",
                score=0.8,
                importance=5,
                confidence=0.9,
                source="chat_extraction",
                observed_at=recent,
            ),
        ]

        decisions = MemoryPolicy.explain_memories(memories)
        by_id = {decision.memory.memory_id: decision for decision in decisions}

        self.assertGreater(by_id["recent-decision"].final_score, by_id["old-decision"].final_score)
        self.assertGreater(
            by_id["recent-decision"].factors["freshness_weight"],
            by_id["old-decision"].factors["freshness_weight"],
        )
        self.assertIn("freshness_age_days", by_id["recent-decision"].factors)

    def test_memory_retrieval_uses_source_weight(self):
        memories = [
            RetrievedMemory(
                memory_id="unknown-source",
                content="unknown source memory",
                similarity=0.80,
                mem_type="fact",
                mem_status="active",
                score=0.8,
                importance=5,
                confidence=0.9,
                source="",
            ),
            RetrievedMemory(
                memory_id="explicit-source",
                content="explicit source memory",
                similarity=0.80,
                mem_type="fact",
                mem_status="active",
                score=0.8,
                importance=5,
                confidence=0.9,
                source="user_explicit",
            ),
        ]

        decisions = MemoryPolicy.explain_memories(memories)
        by_id = {decision.memory.memory_id: decision for decision in decisions}

        self.assertGreater(by_id["explicit-source"].final_score, by_id["unknown-source"].final_score)
        self.assertEqual(by_id["explicit-source"].factors["source_weight"], 1.08)
        self.assertEqual(by_id["unknown-source"].factors["source_weight"], 0.92)

    def test_memory_retrieval_downranks_non_current_memory(self):
        memories = [
            RetrievedMemory(
                memory_id="historical",
                content="historical but active memory",
                similarity=0.85,
                mem_type="fact",
                mem_status="active",
                score=0.8,
                importance=5,
                confidence=0.9,
                is_current=False,
            ),
            RetrievedMemory(
                memory_id="current",
                content="current memory",
                similarity=0.76,
                mem_type="fact",
                mem_status="active",
                score=0.8,
                importance=5,
                confidence=0.9,
                is_current=True,
            ),
        ]

        decisions = MemoryPolicy.explain_memories(memories)
        by_id = {decision.memory.memory_id: decision for decision in decisions}

        self.assertGreater(by_id["current"].final_score, by_id["historical"].final_score)
        self.assertEqual(by_id["historical"].factors["current_weight"], 0.55)
        self.assertFalse(by_id["historical"].factors["is_current"])

    def test_memory_retrieval_allows_matching_conversation_scope(self):
        memories = [
            RetrievedMemory(
                memory_id="conversation-match",
                content="conversation memory",
                similarity=0.82,
                mem_type="fact",
                mem_status="active",
                score=0.9,
                importance=5,
                confidence=0.9,
                scope="conversation",
                source_conversation_id="42",
            )
        ]

        selected = MemoryPolicy.filter_memories(memories, conversation_id=42)

        self.assertEqual([memory.memory_id for memory in selected], ["conversation-match"])

    def test_memory_confirmation_queue_accept_and_reject(self):
        self.runtime.memory_service.memory_store.clear_user_memories("u-memory-review")
        write_resp = self.client.post(
            "/memory/write",
            json={"user_id": "u-memory-review", "content": "I like review queues"},
        )
        self.assertEqual(write_resp.status_code, 200)
        memory_id = write_resp.json().get("memory_id")
        self.assertIsNotNone(memory_id)

        memory = self.runtime.memory_service.memory_store.get_by_id("u-memory-review", memory_id)
        memory.metadata["review_status"] = "pending"
        self.runtime.memory_service.memory_store.update_memory("u-memory-review", memory)

        pending_resp = self.client.get("/memory/pending/u-memory-review")
        self.assertEqual(pending_resp.status_code, 200)
        pending_payload = pending_resp.json()
        self.assertEqual(len(pending_payload["memories"]), 1)
        self.assertEqual(pending_payload["memories"][0]["review_status"], "pending")

        edit_resp = self.client.patch(
            f"/memory/u-memory-review/{memory_id}",
            json={
                "content": "I like review queues after careful review",
                "mem_type": "preference",
                "scope": "global",
                "sensitivity": "personal",
            },
        )
        self.assertEqual(edit_resp.status_code, 200)
        edited_payload = edit_resp.json()
        self.assertEqual(edited_payload["content"], "I like review queues after careful review")
        self.assertEqual(edited_payload["mem_type"], "preference")
        self.assertEqual(edited_payload["review_status"], "pending")
        self.assertTrue(edited_payload["edited_before_accept"])
        self.assertEqual(edited_payload["original_content"], "I like review queues")

        accept_resp = self.client.post(f"/memory/u-memory-review/{memory_id}/accept")
        self.assertEqual(accept_resp.status_code, 200)
        self.assertEqual(accept_resp.json()["review_status"], "accepted")
        self.assertEqual(accept_resp.json()["content"], "I like review queues after careful review")

        pending_after_accept = self.client.get("/memory/pending/u-memory-review")
        self.assertEqual(pending_after_accept.status_code, 200)
        self.assertEqual(pending_after_accept.json()["memories"], [])

        reject_resp = self.client.post(f"/memory/u-memory-review/{memory_id}/reject")
        self.assertEqual(reject_resp.status_code, 200)
        self.assertEqual(reject_resp.json()["review_status"], "rejected")

    def test_secret_memory_cannot_be_accepted_after_edit(self):
        self.runtime.memory_service.memory_store.clear_user_memories("u-memory-secret-review")
        write_resp = self.client.post(
            "/memory/write",
            json={"user_id": "u-memory-secret-review", "content": "I like review queues"},
        )
        self.assertEqual(write_resp.status_code, 200)
        memory_id = write_resp.json().get("memory_id")

        memory = self.runtime.memory_service.memory_store.get_by_id("u-memory-secret-review", memory_id)
        memory.metadata["review_status"] = "pending"
        self.runtime.memory_service.memory_store.update_memory("u-memory-secret-review", memory)

        edit_resp = self.client.patch(
            f"/memory/u-memory-secret-review/{memory_id}",
            json={"content": "my password is 123456"},
        )
        self.assertEqual(edit_resp.status_code, 200)
        self.assertEqual(edit_resp.json()["review_status"], "rejected")
        self.assertEqual(edit_resp.json()["sensitive_category"], "secret")

        accept_resp = self.client.post(f"/memory/u-memory-secret-review/{memory_id}/accept")
        self.assertEqual(accept_resp.status_code, 400)

    def test_user_memory_control_metadata_and_retrieval_filter(self):
        self.runtime.memory_service.memory_store.clear_user_memories("u-memory-control")
        write_resp = self.client.post(
            "/memory/write",
            json={"user_id": "u-memory-control", "content": "I like user memory control"},
        )
        self.assertEqual(write_resp.status_code, 200)
        memory_id = write_resp.json().get("memory_id")
        self.assertIsNotNone(memory_id)

        control_resp = self.client.patch(
            f"/memory/u-memory-control/{memory_id}",
            json={
                "retrieval_enabled": False,
                "user_hidden": True,
                "pinned": True,
                "is_current": False,
                "user_control_reason": "disabled by user test",
            },
        )
        self.assertEqual(control_resp.status_code, 200)
        payload = control_resp.json()
        self.assertFalse(payload["retrieval_enabled"])
        self.assertTrue(payload["user_hidden"])
        self.assertTrue(payload["pinned"])
        self.assertFalse(payload["is_current"])
        self.assertEqual(payload["user_control_reason"], "disabled by user test")

        memory = self.runtime.memory_service.memory_store.get_by_id("u-memory-control", memory_id)
        retrieved = RetrievedMemory(
            memory_id=memory.memory_id,
            content=memory.content,
            similarity=0.9,
            mem_type=memory.mem_type,
            mem_status=memory.status,
            score=memory.score,
            retrieval_enabled=False,
        )
        self.assertEqual(MemoryPolicy.filter_memories([retrieved]), [])

        list_resp = self.client.get("/memory/list/u-memory-control")
        self.assertEqual(list_resp.status_code, 200)
        listed = list_resp.json()["memories"][0]
        self.assertFalse(listed["retrieval_enabled"])
        self.assertTrue(listed["user_hidden"])




if __name__ == "__main__":
    unittest.main()
