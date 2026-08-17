import json
import os
import re
import hashlib
from functools import wraps
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import threading
from typing import Any, Dict, List
from uuid import uuid4

import numpy as np

from app.knowledge.chunker import chunk_text_with_spans
from app.knowledge.parser import extract_text
from app.memory.embedding.factory import create_embedding_client
from app.model.config import load_llm_settings
from app.runtime.chroma_client import create_chroma_client


DEFAULT_RETRIEVAL_STRATEGY = "hybrid_rerank"
SUPPORTED_RETRIEVAL_STRATEGIES = frozenset({"vector", "hybrid", DEFAULT_RETRIEVAL_STRATEGY})
HYBRID_FUSION_VERSION = "hybrid_weighted_v1"
LIGHTWEIGHT_RERANKER_VERSION = "lightweight_rule_v1"


def _user_synchronized(method):
    @wraps(method)
    def locked(self, user_id: str, *args, **kwargs):
        with self._lock_for_user(user_id):
            return method(self, user_id, *args, **kwargs)

    return locked


class KnowledgeService:
    def __init__(
        self,
        persist_dir: str | None = None,
        base_dir: str | None = None,
        embedding_client=None,
        collection_name: str | None = None,
        chroma_client=None,
        embedding_provider: str | None = None,
        embedding_model_id: str | None = None,
        chunk_size_chars: int = 700,
        chunk_overlap_chars: int = 100,
        candidate_multiplier: int = 6,
        selection_context_budget_tokens: int | None = None,
        reranker_version: str = LIGHTWEIGHT_RERANKER_VERSION,
    ):
        if int(chunk_size_chars) < 1:
            raise ValueError("chunk_size_chars must be >= 1")
        if int(chunk_overlap_chars) < 0 or int(chunk_overlap_chars) >= int(chunk_size_chars):
            raise ValueError("chunk_overlap_chars must be >= 0 and smaller than chunk_size_chars")
        if int(candidate_multiplier) < 1:
            raise ValueError("candidate_multiplier must be >= 1")
        if selection_context_budget_tokens is not None and int(selection_context_budget_tokens) < 1:
            raise ValueError("selection_context_budget_tokens must be >= 1")
        if reranker_version != LIGHTWEIGHT_RERANKER_VERSION:
            raise ValueError(f"Unsupported reranker_version: {reranker_version!r}")
        needs_settings = any(
            value is None
            for value in (embedding_client, collection_name, embedding_provider, embedding_model_id)
        )
        self.settings = load_llm_settings() if needs_settings else None
        self.embedding_client = embedding_client if embedding_client is not None else create_embedding_client()
        self.embedding_provider = (
            embedding_provider if embedding_provider is not None else self.settings.embedding_provider
        )
        self.embedding_model_id = (
            embedding_model_id if embedding_model_id is not None else self.settings.embedding_model_id
        )
        self.chunk_size_chars = int(chunk_size_chars)
        self.chunk_overlap_chars = int(chunk_overlap_chars)
        self.candidate_multiplier = int(candidate_multiplier)
        self.selection_context_budget_tokens = (
            int(selection_context_budget_tokens) if selection_context_budget_tokens is not None else None
        )
        self.reranker_version = reranker_version
        resolved_base_dir = base_dir or os.getenv("MYAI_KNOWLEDGE_DATA_DIR", "./knowledge_data")
        self.base_path = Path(resolved_base_dir)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.client = chroma_client if chroma_client is not None else create_chroma_client(persist_dir)
        self.collection = self.client.get_or_create_collection(
            name=collection_name if collection_name is not None else self.settings.knowledge_collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        self._locks_guard = threading.Lock()
        self._user_locks: dict[str, threading.RLock] = {}

    @_user_synchronized
    def upload_file(self, user_id: str, filename: str, content: bytes) -> Dict[str, Any]:
        safe_name = self._sanitize_filename(filename)
        file_type = Path(safe_name).suffix.lower().lstrip(".")
        content_hash = hashlib.sha256(content).hexdigest()
        existing = self._find_by_hash(user_id, content_hash)
        if existing is not None:
            public_entry = self._public_file_entry(existing)
            public_entry["ingestion_report"] = {
                "status": "duplicate",
                "warnings": ["duplicate content hash; existing file reused"],
                "duplicate_of_file_id": existing["file_id"],
                "parser": self._parser_name(file_type),
                "parser_version": "1",
                "chunk_count": existing.get("chunk_count", 0),
                "text_length": existing.get("text_length", 0),
            }
            return public_entry

        text = extract_text(safe_name, content)
        chunks = chunk_text_with_spans(
            text,
            chunk_size=self.chunk_size_chars,
            overlap=self.chunk_overlap_chars,
        )
        warnings: list[str] = []
        if len(text.strip()) < 20:
            warnings.append("extracted text is very short")
        if not chunks:
            raise ValueError("No readable text could be extracted from the uploaded file")

        file_id = str(uuid4())
        uploaded_at = datetime.now(timezone.utc).isoformat()
        document_profile = self._build_document_profile(text, safe_name, file_type)
        summary = document_profile["short_summary"]
        user_dir = self.base_path / user_id
        user_dir.mkdir(parents=True, exist_ok=True)
        stored_path = user_dir / f"{file_id}_{safe_name}"
        self._write_bytes_atomic(stored_path, content)

        ids: List[str] = []
        embeddings: List[List[float]] = []
        metadatas: List[Dict[str, Any]] = []
        for idx, chunk in enumerate(chunks):
            chunk_id = f"{file_id}_{idx}"
            ids.append(chunk_id)
            embeddings.append(self.embedding_client.embed(chunk.content).astype(np.float32).tolist())
            metadatas.append(
                {
                    "user_id": user_id,
                    "file_id": file_id,
                    "file_name": safe_name,
                    "file_type": file_type,
                    "chunk_index": idx,
                    "char_start": chunk.char_start,
                    "char_end": chunk.char_end,
                    "page_start": "",
                    "page_end": "",
                    "section_title": "",
                    "token_estimate": chunk.token_estimate,
                    "uploaded_at": uploaded_at,
                    "source": "knowledge_base",
                    "content_hash": content_hash,
                    "embedding_provider": self.embedding_provider,
                    "embedding_model": self.embedding_model_id,
                }
            )

        self.collection.add(ids=ids, embeddings=embeddings, documents=[chunk.content for chunk in chunks], metadatas=metadatas)

        ingestion_report = {
            "status": "indexed",
            "warnings": warnings,
            "parser": self._parser_name(file_type),
            "parser_version": "1",
            "chunk_count": len(chunks),
            "text_length": len(text),
            "embedding_provider": self.embedding_provider,
            "embedding_model": self.embedding_model_id,
        }

        entry = {
            "file_id": file_id,
            "file_name": safe_name,
            "file_type": file_type,
            "size_bytes": len(content),
            "content_hash": content_hash,
            "chunk_count": len(chunks),
            "uploaded_at": uploaded_at,
            "summary": summary,
            "document_profile": document_profile,
            "path": str(stored_path),
            "chunk_ids": ids,
            "parser": ingestion_report["parser"],
            "parser_version": ingestion_report["parser_version"],
            "text_length": len(text),
            "embedding_provider": self.embedding_provider,
            "embedding_model": self.embedding_model_id,
            "ingestion_status": ingestion_report["status"],
            "ingestion_warnings": warnings,
        }
        index = self._load_index(user_id)
        index.append(entry)
        self._save_index(user_id, index)
        public_entry = self._public_file_entry(entry)
        public_entry["ingestion_report"] = ingestion_report
        return public_entry

    @_user_synchronized
    def list_files(self, user_id: str) -> List[Dict[str, Any]]:
        index = self._load_index(user_id)
        index.sort(key=lambda item: item["uploaded_at"], reverse=True)
        return [self._public_file_entry(item) for item in index]

    @_user_synchronized
    def get_file_entry(self, user_id: str, file_id: str | None = None, file_name: str | None = None) -> Dict[str, Any] | None:
        normalized_name = (file_name or "").strip().lower()
        for item in self._load_index(user_id):
            if file_id and item["file_id"] == file_id:
                return item
            if normalized_name and item["file_name"].lower() == normalized_name:
                return item
        return None

    @_user_synchronized
    def get_file_text(self, user_id: str, file_id: str | None = None, file_name: str | None = None) -> str | None:
        entry = self.get_file_entry(user_id, file_id=file_id, file_name=file_name)
        if entry is None:
            return None
        file_path = Path(entry["path"])
        if not file_path.exists():
            return None
        return extract_text(entry["file_name"], file_path.read_bytes())

    @_user_synchronized
    def delete_file(self, user_id: str, file_id: str) -> bool:
        index = self._load_index(user_id)
        remaining: List[Dict[str, Any]] = []
        target = None
        for item in index:
            if item["file_id"] == file_id:
                target = item
            else:
                remaining.append(item)
        if target is None:
            return False

        self.collection.delete(ids=target.get("chunk_ids", []))
        file_path = Path(target["path"])
        if file_path.exists():
            file_path.unlink()
        self._save_index(user_id, remaining)
        return True

    @_user_synchronized
    def maintain(
        self,
        user_id: str,
        *,
        dry_run: bool = True,
        file_id: str | None = None,
        rebuild: bool = False,
    ) -> Dict[str, Any]:
        index = self._load_index(user_id)
        selected_index = [item for item in index if not file_id or item.get("file_id") == file_id]
        expected_ids = {
            chunk_id
            for item in selected_index
            for chunk_id in item.get("chunk_ids", [])
        }
        indexed_file_ids = {item.get("file_id") for item in selected_index}
        vector_state = self._vector_state(user_id)
        vector_ids = set(vector_state["ids"])
        orphan_chunk_ids = sorted(
            chunk_id
            for chunk_id, metadata in vector_state["metadata_by_id"].items()
            if (not file_id or metadata.get("file_id") == file_id)
            and (metadata.get("file_id") not in indexed_file_ids or chunk_id not in expected_ids)
        )
        duplicate_groups = self._duplicate_content_groups(selected_index)
        file_reports: List[Dict[str, Any]] = []
        totals = {
            "files_checked": len(selected_index),
            "missing_chunks": 0,
            "reindexed_files": 0,
            "orphan_chunks": len(orphan_chunk_ids),
            "orphan_chunks_deleted": 0,
            "duplicate_groups": len(duplicate_groups),
            "missing_stored_files": 0,
        }

        changed = False
        updated_entries = {item.get("file_id"): dict(item) for item in index}
        for item in selected_index:
            report, repaired_entry = self._maintain_file_entry(
                user_id,
                item,
                vector_ids,
                dry_run=dry_run,
                rebuild=rebuild,
            )
            file_reports.append(report)
            totals["missing_chunks"] += len(report["missing_chunk_ids"])
            if report["stored_file_status"] == "missing":
                totals["missing_stored_files"] += 1
            if report["action"] == "reindexed":
                totals["reindexed_files"] += 1
                changed = True
            if repaired_entry is not None:
                updated_entries[item["file_id"]] = repaired_entry

        if orphan_chunk_ids and not dry_run:
            self.collection.delete(ids=orphan_chunk_ids)
            totals["orphan_chunks_deleted"] = len(orphan_chunk_ids)
            changed = True

        if changed:
            self._save_index(user_id, [updated_entries[item["file_id"]] for item in index if item.get("file_id") in updated_entries])

        status = "healthy"
        if totals["missing_chunks"] or totals["orphan_chunks"] or totals["missing_stored_files"] or totals["duplicate_groups"]:
            status = "needs_repair" if dry_run else "repaired"
        if totals["missing_stored_files"] and not dry_run:
            status = "partial_repair"

        actions = [
            {
                "type": "delete_orphan_chunks",
                "status": "planned" if dry_run else "completed",
                "chunk_ids": orphan_chunk_ids,
                "count": len(orphan_chunk_ids),
            }
        ] if orphan_chunk_ids else []
        actions.extend(report["planned_actions"][0] for report in file_reports if report["planned_actions"])

        return {
            "user_id": user_id,
            "dry_run": dry_run,
            "file_id": file_id or "",
            "rebuild": rebuild,
            "status": status,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "summary": totals,
            "files": file_reports,
            "orphan_chunk_ids": orphan_chunk_ids,
            "duplicate_groups": duplicate_groups,
            "actions": actions,
        }

    @_user_synchronized
    def query(
        self,
        user_id: str,
        query: str,
        top_k: int = 3,
        file_id: str | None = None,
        retrieval_strategy: str = DEFAULT_RETRIEVAL_STRATEGY,
    ) -> List[Dict[str, Any]]:
        if not query.strip():
            return []
        strategy = self._validate_retrieval_strategy(retrieval_strategy)
        candidates = self._retrieve_candidates(
            user_id,
            query,
            top_k=top_k,
            file_id=file_id,
            retrieval_strategy=strategy,
        )
        hits = [
            self._build_query_hit(
                candidate,
                query=query,
                file_filter_enabled=file_id is not None,
                retrieval_strategy=strategy,
            )
            for candidate in candidates.values()
        ]
        ranking_field = "vector_score" if strategy == "vector" else "retrieval_score"
        hits.sort(key=lambda item: item[ranking_field], reverse=True)
        for rank, hit in enumerate(hits, start=1):
            hit["candidate_rank"] = rank
        if strategy != DEFAULT_RETRIEVAL_STRATEGY:
            return self._select_unreranked_hits(hits, top_k=top_k, ranking_field=ranking_field)
        return self._select_final_hits(hits, top_k=top_k)

    @_user_synchronized
    def answer_document_question(self, user_id: str, file_id: str, question: str, top_k: int = 3) -> Dict[str, Any]:
        entry = self.get_file_entry(user_id, file_id=file_id)
        if entry is None:
            raise ValueError("Knowledge file not found")
        clean_question = question.strip()
        if not clean_question:
            return {
                "file_id": file_id,
                "file_name": entry.get("file_name", ""),
                "question": question,
                "answer": "Please ask a question about the selected document.",
                "answer_status": "empty_question",
                "evidence_count": 0,
                "citations": [],
                "hits": [],
            }

        hits = self.query(user_id, clean_question, top_k=top_k, file_id=file_id)
        evidence = [hit for hit in hits if self._hit_has_answer_evidence(hit)]
        if not evidence:
            return {
                "file_id": file_id,
                "file_name": entry.get("file_name", ""),
                "question": clean_question,
                "answer": "Not enough evidence was found in the selected document.",
                "answer_status": "not_enough_evidence",
                "evidence_count": 0,
                "citations": [],
                "hits": [],
            }

        answer = self._compose_document_answer(clean_question, evidence)
        return {
            "file_id": file_id,
            "file_name": entry.get("file_name", ""),
            "question": clean_question,
            "answer": answer,
            "answer_status": "answered",
            "evidence_count": len(evidence),
            "citations": [hit.get("citation", {}) for hit in evidence],
            "hits": evidence,
        }

    def _maintain_file_entry(
        self,
        user_id: str,
        entry: Dict[str, Any],
        vector_ids: set[str],
        *,
        dry_run: bool,
        rebuild: bool,
    ) -> tuple[Dict[str, Any], Dict[str, Any] | None]:
        chunk_ids = list(entry.get("chunk_ids", []))
        missing_chunk_ids = [chunk_id for chunk_id in chunk_ids if chunk_id not in vector_ids]
        file_path = Path(entry.get("path", ""))
        stored_file_exists = file_path.exists()
        planned_actions: List[Dict[str, Any]] = []
        repaired_entry = None
        action = "none"
        if rebuild or missing_chunk_ids:
            if stored_file_exists:
                action_type = "rebuild_file_index" if rebuild else "reindex_missing_chunks"
                planned_actions.append(
                    {
                        "type": action_type,
                        "status": "planned" if dry_run else "completed",
                        "file_id": entry.get("file_id", ""),
                        "missing_chunk_ids": missing_chunk_ids,
                    }
                )
                action = "would_reindex" if dry_run else "reindexed"
                if not dry_run:
                    repaired_entry = self._reindex_file_entry(user_id, entry, delete_existing=rebuild)
            else:
                planned_actions.append(
                    {
                        "type": "cannot_reindex_missing_stored_file",
                        "status": "blocked",
                        "file_id": entry.get("file_id", ""),
                    }
                )
                action = "blocked"

        health = "healthy"
        if not stored_file_exists:
            health = "missing_stored_file"
        elif missing_chunk_ids or rebuild:
            health = "needs_reindex" if dry_run else "reindexed"

        report = {
            "file_id": entry.get("file_id", ""),
            "file_name": entry.get("file_name", ""),
            "stored_file_status": "present" if stored_file_exists else "missing",
            "expected_chunk_count": len(chunk_ids),
            "actual_chunk_count": len([chunk_id for chunk_id in chunk_ids if chunk_id in vector_ids]),
            "missing_chunk_ids": missing_chunk_ids,
            "health": health,
            "action": action,
            "planned_actions": planned_actions,
        }
        return report, repaired_entry

    def _reindex_file_entry(self, user_id: str, entry: Dict[str, Any], *, delete_existing: bool) -> Dict[str, Any]:
        file_path = Path(entry["path"])
        content = file_path.read_bytes()
        text = extract_text(entry["file_name"], content)
        chunks = chunk_text_with_spans(text)
        if not chunks:
            raise ValueError("No readable text could be extracted from the stored file")

        file_id = entry["file_id"]
        uploaded_at = entry.get("uploaded_at") or datetime.now(timezone.utc).isoformat()
        file_type = entry.get("file_type") or Path(entry["file_name"]).suffix.lower().lstrip(".")
        content_hash = entry.get("content_hash") or hashlib.sha256(content).hexdigest()
        if delete_existing:
            self.collection.delete(ids=entry.get("chunk_ids", []))

        ids, documents, embeddings, metadatas = self._build_chunk_records(
            user_id=user_id,
            file_id=file_id,
            file_name=entry["file_name"],
            file_type=file_type,
            content_hash=content_hash,
            uploaded_at=uploaded_at,
            chunks=chunks,
        )
        existing_ids = set(self.collection.get(ids=ids, include=["metadatas"]).get("ids", []))
        add_positions = [idx for idx, chunk_id in enumerate(ids) if chunk_id not in existing_ids]
        if add_positions:
            self.collection.add(
                ids=[ids[idx] for idx in add_positions],
                documents=[documents[idx] for idx in add_positions],
                embeddings=[embeddings[idx] for idx in add_positions],
                metadatas=[metadatas[idx] for idx in add_positions],
            )

        repaired = dict(entry)
        document_profile = self._build_document_profile(text, entry["file_name"], file_type)
        repaired.update(
            {
                "file_type": file_type,
                "content_hash": content_hash,
                "chunk_count": len(ids),
                "summary": document_profile["short_summary"],
                "document_profile": document_profile,
                "chunk_ids": ids,
                "parser": self._parser_name(file_type),
                "parser_version": "1",
                "text_length": len(text),
                "embedding_provider": self.embedding_provider,
                "embedding_model": self.embedding_model_id,
                "ingestion_status": "indexed",
                "ingestion_warnings": [],
            }
        )
        return repaired

    def _build_chunk_records(
        self,
        *,
        user_id: str,
        file_id: str,
        file_name: str,
        file_type: str,
        content_hash: str,
        uploaded_at: str,
        chunks,
    ) -> tuple[List[str], List[str], List[List[float]], List[Dict[str, Any]]]:
        ids: List[str] = []
        documents: List[str] = []
        embeddings: List[List[float]] = []
        metadatas: List[Dict[str, Any]] = []
        for idx, chunk in enumerate(chunks):
            chunk_id = f"{file_id}_{idx}"
            ids.append(chunk_id)
            documents.append(chunk.content)
            embeddings.append(self.embedding_client.embed(chunk.content).astype(np.float32).tolist())
            metadatas.append(
                {
                    "user_id": user_id,
                    "file_id": file_id,
                    "file_name": file_name,
                    "file_type": file_type,
                    "chunk_index": idx,
                    "char_start": chunk.char_start,
                    "char_end": chunk.char_end,
                    "page_start": "",
                    "page_end": "",
                    "section_title": "",
                    "token_estimate": chunk.token_estimate,
                    "uploaded_at": uploaded_at,
                    "source": "knowledge_base",
                    "content_hash": content_hash,
                }
            )
        return ids, documents, embeddings, metadatas

    def _vector_state(self, user_id: str) -> Dict[str, Any]:
        stored = self.collection.get(where={"user_id": user_id}, include=["metadatas"])
        ids = stored.get("ids", [])
        metadatas = stored.get("metadatas", [])
        return {
            "ids": ids,
            "metadata_by_id": {
                ids[idx]: dict(metadatas[idx] or {})
                for idx in range(len(ids))
            },
        }

    @staticmethod
    def _duplicate_content_groups(index: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        by_hash: Dict[str, List[Dict[str, Any]]] = {}
        for item in index:
            content_hash = str(item.get("content_hash", "") or "")
            if content_hash:
                by_hash.setdefault(content_hash, []).append(item)
        groups = []
        for content_hash, items in by_hash.items():
            if len(items) > 1:
                groups.append(
                    {
                        "content_hash": content_hash,
                        "file_ids": [item.get("file_id", "") for item in items],
                        "file_names": [item.get("file_name", "") for item in items],
                        "count": len(items),
                    }
                )
        return groups

    def _retrieve_candidates(
        self,
        user_id: str,
        query: str,
        *,
        top_k: int,
        file_id: str | None = None,
        retrieval_strategy: str = DEFAULT_RETRIEVAL_STRATEGY,
    ) -> Dict[str, Dict[str, Any]]:
        if file_id:
            where: Dict[str, Any] = {
                "$and": [
                    {"user_id": user_id},
                    {"file_id": file_id},
                ]
            }
        else:
            where = {"user_id": user_id}
        candidate_multiplier = int(getattr(self, "candidate_multiplier", 6))
        candidate_limit = max(top_k * candidate_multiplier, top_k + candidate_multiplier)
        candidates: Dict[str, Dict[str, Any]] = {}
        self._merge_candidates(candidates, self._vector_candidates(query, where, candidate_limit))
        if retrieval_strategy != "vector":
            self._merge_candidates(candidates, self._keyword_candidates(user_id, query, file_id=file_id))
        return candidates

    def _vector_candidates(self, query: str, where: Dict[str, Any], top_k: int) -> List[Dict[str, Any]]:
        query_vector = self.embedding_client.embed(query).astype(np.float32).tolist()
        results = self.collection.query(
            query_embeddings=[query_vector],
            n_results=top_k,
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        candidates: List[Dict[str, Any]] = []
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]
        ids = results.get("ids", [[]])[0]

        for idx in range(len(ids)):
            candidates.append(
                {
                    "chunk_id": ids[idx],
                    "content": documents[idx],
                    "metadata": dict(metadatas[idx] or {}),
                    "vector_score": round(1.0 - float(distances[idx]), 4),
                    "keyword_score": 0.0,
                    "retrieval_sources": {"vector"},
                }
            )
        return candidates

    def _keyword_candidates(self, user_id: str, query: str, file_id: str | None = None) -> List[Dict[str, Any]]:
        chunk_ids: List[str] = []
        for item in self._load_index(user_id):
            if file_id and item.get("file_id") != file_id:
                continue
            chunk_ids.extend(item.get("chunk_ids", []))
        if not chunk_ids:
            return []

        stored = self.collection.get(ids=chunk_ids, include=["documents", "metadatas"])
        ids = stored.get("ids", [])
        documents = stored.get("documents", [])
        metadatas = stored.get("metadatas", [])
        candidates: List[Dict[str, Any]] = []
        for idx in range(len(ids)):
            metadata = dict(metadatas[idx] or {})
            content = documents[idx] or ""
            keyword_score = self._keyword_score(query, content, str(metadata.get("file_name", "") or ""))
            if keyword_score <= 0:
                continue
            candidates.append(
                {
                    "chunk_id": ids[idx],
                    "content": content,
                    "metadata": metadata,
                    "vector_score": 0.0,
                    "keyword_score": keyword_score,
                    "retrieval_sources": {"keyword"},
                }
            )
        return candidates

    @staticmethod
    def _merge_candidates(target: Dict[str, Dict[str, Any]], candidates: List[Dict[str, Any]]) -> None:
        for candidate in candidates:
            chunk_id = candidate["chunk_id"]
            existing = target.get(chunk_id)
            if existing is None:
                target[chunk_id] = candidate
                continue
            existing["vector_score"] = max(existing.get("vector_score", 0.0), candidate.get("vector_score", 0.0))
            existing["keyword_score"] = max(existing.get("keyword_score", 0.0), candidate.get("keyword_score", 0.0))
            existing.setdefault("retrieval_sources", set()).update(candidate.get("retrieval_sources", set()))

    def _build_query_hit(
        self,
        candidate: Dict[str, Any],
        *,
        query: str,
        file_filter_enabled: bool,
        retrieval_strategy: str = DEFAULT_RETRIEVAL_STRATEGY,
    ) -> Dict[str, Any]:
        metadata = dict(candidate.get("metadata") or {})
        content = str(candidate.get("content") or "")
        vector_score = float(candidate.get("vector_score", 0.0) or 0.0)
        keyword_score = float(candidate.get("keyword_score", 0.0) or 0.0)
        filename_score = self._filename_score(query, str(metadata.get("file_name", "") or ""))
        recency_score = self._recency_score(str(metadata.get("uploaded_at", "") or ""))
        file_filter_score = 1.0 if file_filter_enabled else 0.0
        rerank_applied = retrieval_strategy == DEFAULT_RETRIEVAL_STRATEGY
        fusion_version = "none" if retrieval_strategy == "vector" else HYBRID_FUSION_VERSION
        if retrieval_strategy == "vector":
            retrieval_score = round(vector_score, 4)
        else:
            retrieval_score = self._fusion_score(
                vector_score=vector_score,
                keyword_score=keyword_score,
                filename_score=filename_score,
                recency_score=recency_score,
                file_filter_score=file_filter_score,
            )
        citation = self._build_citation(
            chunk_id=candidate["chunk_id"],
            metadata=metadata,
            content=content,
            score=retrieval_score,
        )
        retrieval_sources = sorted(candidate.get("retrieval_sources", set()))
        retrieval_mode = "+".join(retrieval_sources) if retrieval_sources else "unknown"
        explanation = {
            "mode": retrieval_mode,
            "selected_by": retrieval_sources,
            "vector_score": vector_score,
            "keyword_score": keyword_score,
            "filename_score": filename_score,
            "recency_score": recency_score,
            "file_filter_score": file_filter_score,
            "retrieval_score": retrieval_score,
            "retrieval_strategy": retrieval_strategy,
            "rerank_applied": rerank_applied,
            "reranker_version": (
                getattr(self, "reranker_version", LIGHTWEIGHT_RERANKER_VERSION)
                if rerank_applied
                else "none"
            ),
            "fusion_version": fusion_version,
            "reason": self._retrieval_reason(retrieval_sources, keyword_score, filename_score),
        }
        query_coverage = self._query_term_coverage(query, content, str(metadata.get("file_name", "") or ""))
        length_quality = self._chunk_length_quality(int(metadata.get("token_estimate", 0) or 0))
        rerank_score = self._rerank_score(
            retrieval_score=retrieval_score,
            query_coverage=query_coverage,
            length_quality=length_quality,
            duplicate_penalty=0.0,
            diversity_penalty=0.0,
        )
        return {
            "chunk_id": candidate["chunk_id"],
            "file_id": metadata.get("file_id", ""),
            "file_name": metadata.get("file_name", ""),
            "chunk_index": metadata.get("chunk_index", 0),
            "char_start": int(metadata.get("char_start", 0) or 0),
            "char_end": int(metadata.get("char_end", 0) or 0),
            "page_start": metadata.get("page_start", ""),
            "page_end": metadata.get("page_end", ""),
            "section_title": metadata.get("section_title", ""),
            "token_estimate": int(metadata.get("token_estimate", 0) or 0),
            "content": content,
            "score": retrieval_score,
            "citation_id": citation["citation_id"],
            "snippet": citation["snippet"],
            "citation": citation,
            "retrieval_mode": retrieval_mode,
            "retrieval_score": retrieval_score,
            "retrieval_strategy": retrieval_strategy,
            "rerank_applied": rerank_applied,
            "reranker_version": (
                getattr(self, "reranker_version", LIGHTWEIGHT_RERANKER_VERSION)
                if rerank_applied
                else "none"
            ),
            "fusion_version": fusion_version,
            "vector_score": vector_score,
            "keyword_score": keyword_score,
            "filename_score": filename_score,
            "recency_score": recency_score,
            "file_filter_score": file_filter_score,
            "retrieval_explanation": explanation,
            "candidate_rank": 0,
            "final_rank": 0,
            "rerank_score": rerank_score,
            "query_coverage": query_coverage,
            "length_quality": length_quality,
            "duplicate_penalty": 0.0,
            "diversity_penalty": 0.0,
            "selection_status": "candidate",
            "selection_reason": "",
            "selection_explanation": {},
        }

    def _select_unreranked_hits(
        self,
        hits: List[Dict[str, Any]],
        *,
        top_k: int,
        ranking_field: str,
    ) -> List[Dict[str, Any]]:
        selection_limit = max(0, top_k)
        max_context_tokens = self._selection_context_budget(selection_limit)
        selected: List[Dict[str, Any]] = []
        used_tokens = 0
        for source_hit in hits:
            if len(selected) >= selection_limit:
                break
            hit = dict(source_hit)
            token_estimate = int(hit.get("token_estimate", 0) or 0)
            if used_tokens + token_estimate > max_context_tokens and used_tokens > 0:
                continue
            selected.append(hit)
            used_tokens += token_estimate
        filtered_count = max(0, len(hits) - len(selected))
        for rank, hit in enumerate(selected, start=1):
            hit["final_rank"] = rank
            hit["selection_status"] = "selected"
            hit["selection_reason"] = f"selected by {ranking_field} without rerank"
            hit["rerank_score"] = 0.0
            hit["selection_explanation"] = {
                "candidate_count": len(hits),
                "selected_count": len(selected),
                "filtered_count": filtered_count,
                "candidate_rank": hit.get("candidate_rank", 0),
                "final_rank": rank,
                "max_context_tokens": max_context_tokens,
                "used_context_tokens": used_tokens,
                "ranking_field": ranking_field,
                "ranking_score": hit.get(ranking_field, 0.0),
                "rerank_applied": False,
                "reason": hit["selection_reason"],
            }
        return selected

    def _select_final_hits(self, hits: List[Dict[str, Any]], *, top_k: int) -> List[Dict[str, Any]]:
        max_context_tokens = self._selection_context_budget(top_k)
        max_chunks_per_file = max(1, (top_k + 1) // 2)
        selected: List[Dict[str, Any]] = []
        file_counts: Dict[str, int] = {}
        seen_fingerprints: set[str] = set()
        used_tokens = 0
        remaining = [dict(hit) for hit in hits]

        while remaining and len(selected) < top_k:
            scored = [self._apply_selection_policy(hit, file_counts, seen_fingerprints) for hit in remaining]
            scored.sort(key=lambda item: item["rerank_score"], reverse=True)
            chosen = self._choose_next_hit(scored, used_tokens, max_context_tokens, max_chunks_per_file, file_counts)
            if chosen is None:
                chosen = self._choose_next_hit(
                    scored,
                    used_tokens,
                    max_context_tokens,
                    max_chunks_per_file,
                    file_counts,
                    relax_diversity=True,
                )
            if chosen is None:
                break
            self._mark_selected(chosen, selected, file_counts, seen_fingerprints)
            used_tokens += int(chosen.get("token_estimate", 0) or 0)
            remaining = [hit for hit in remaining if hit["chunk_id"] != chosen["chunk_id"]]

        selected_ids = {hit["chunk_id"] for hit in selected}
        filtered_count = len([hit for hit in hits if hit["chunk_id"] not in selected_ids])
        for rank, hit in enumerate(selected, start=1):
            hit["final_rank"] = rank
            hit["selection_status"] = "selected"
            hit["selection_reason"] = hit.get("selection_reason") or "selected by rerank policy"
            hit["selection_explanation"] = {
                "candidate_count": len(hits),
                "selected_count": len(selected),
                "filtered_count": filtered_count,
                "max_context_tokens": max_context_tokens,
                "used_context_tokens": used_tokens,
                "max_chunks_per_file": max_chunks_per_file,
                "candidate_rank": hit.get("candidate_rank", 0),
                "final_rank": rank,
                "rerank_score": hit.get("rerank_score", 0.0),
                "query_coverage": hit.get("query_coverage", 0.0),
                "length_quality": hit.get("length_quality", 0.0),
                "duplicate_penalty": hit.get("duplicate_penalty", 0.0),
                "diversity_penalty": hit.get("diversity_penalty", 0.0),
                "reason": hit["selection_reason"],
            }
        return selected

    def _selection_context_budget(self, top_k: int) -> int:
        configured = getattr(self, "selection_context_budget_tokens", None)
        return int(configured) if configured is not None else max(300, max(0, int(top_k)) * 450)

    @staticmethod
    def _hit_has_answer_evidence(hit: Dict[str, Any]) -> bool:
        return (
            float(hit.get("query_coverage", 0.0) or 0.0) >= 0.35
            or float(hit.get("keyword_score", 0.0) or 0.0) >= 0.35
        )

    def _compose_document_answer(self, question: str, hits: List[Dict[str, Any]]) -> str:
        passages: List[str] = []
        for hit in hits:
            passage = self._best_answer_passage(question, str(hit.get("content", "") or ""))
            if passage and passage not in passages:
                citation_id = hit.get("citation_id") or hit.get("chunk_id", "")
                passages.append(f"[{citation_id}] {passage}")
        if not passages:
            return "Relevant evidence was found, but no concise answer passage could be extracted."
        return " ".join(passages)

    def _best_answer_passage(self, question: str, content: str) -> str:
        sentences = self._sentences(content) or [content]
        query_terms = set(self._tokenize_for_keyword(question))
        best_sentence = ""
        best_score = -1.0
        for idx, sentence in enumerate(sentences):
            compact = self._compact_text(sentence)
            if not compact:
                continue
            searchable = compact.lower()
            overlap = sum(1 for term in query_terms if term in searchable)
            score = overlap + min(1.0, len(compact) / 120) - idx * 0.01
            if score > best_score:
                best_score = score
                best_sentence = compact
        if len(best_sentence) > 260:
            return best_sentence[:257] + "..."
        return best_sentence

    @staticmethod
    def _choose_next_hit(
        scored: List[Dict[str, Any]],
        used_tokens: int,
        max_context_tokens: int,
        max_chunks_per_file: int,
        file_counts: Dict[str, int],
        *,
        relax_diversity: bool = False,
    ) -> Dict[str, Any] | None:
        for hit in scored:
            token_estimate = int(hit.get("token_estimate", 0) or 0)
            file_id = str(hit.get("file_id", "") or "")
            if used_tokens + token_estimate > max_context_tokens and used_tokens > 0:
                continue
            if not relax_diversity and file_counts.get(file_id, 0) >= max_chunks_per_file and len(file_counts) > 0:
                continue
            if relax_diversity and file_counts.get(file_id, 0) >= max_chunks_per_file:
                hit["selection_reason"] = "selected after relaxing same-file diversity policy"
            return hit
        return None

    def _apply_selection_policy(
        self,
        hit: Dict[str, Any],
        file_counts: Dict[str, int],
        seen_fingerprints: set[str],
    ) -> Dict[str, Any]:
        prepared = dict(hit)
        file_id = str(prepared.get("file_id", "") or "")
        duplicate_penalty = 0.18 if self._content_fingerprint(str(prepared.get("content", "") or "")) in seen_fingerprints else 0.0
        diversity_penalty = min(0.25, file_counts.get(file_id, 0) * 0.12)
        prepared["duplicate_penalty"] = duplicate_penalty
        prepared["diversity_penalty"] = diversity_penalty
        prepared["rerank_score"] = self._rerank_score(
            retrieval_score=float(prepared.get("retrieval_score", 0.0) or 0.0),
            query_coverage=float(prepared.get("query_coverage", 0.0) or 0.0),
            length_quality=float(prepared.get("length_quality", 0.0) or 0.0),
            duplicate_penalty=duplicate_penalty,
            diversity_penalty=diversity_penalty,
        )
        return prepared

    def _mark_selected(
        self,
        hit: Dict[str, Any],
        selected: List[Dict[str, Any]],
        file_counts: Dict[str, int],
        seen_fingerprints: set[str],
    ) -> None:
        selected.append(hit)
        file_id = str(hit.get("file_id", "") or "")
        file_counts[file_id] = file_counts.get(file_id, 0) + 1
        seen_fingerprints.add(self._content_fingerprint(str(hit.get("content", "") or "")))

    def _query_term_coverage(self, query: str, content: str, file_name: str) -> float:
        query_terms = set(self._tokenize_for_keyword(query))
        if not query_terms:
            return 0.0
        searchable = f"{file_name}\n{content}".lower()
        matched = {term for term in query_terms if term in searchable}
        return round(len(matched) / len(query_terms), 4)

    @staticmethod
    def _chunk_length_quality(token_estimate: int) -> float:
        if token_estimate <= 0:
            return 0.0
        if 40 <= token_estimate <= 220:
            return 1.0
        if token_estimate < 40:
            return round(max(0.25, token_estimate / 40), 4)
        return round(max(0.35, 1 - ((token_estimate - 220) / 500)), 4)

    @staticmethod
    def _rerank_score(
        *,
        retrieval_score: float,
        query_coverage: float,
        length_quality: float,
        duplicate_penalty: float,
        diversity_penalty: float,
    ) -> float:
        score = (
            retrieval_score * 0.72
            + query_coverage * 0.20
            + length_quality * 0.08
            - duplicate_penalty
            - diversity_penalty
        )
        return round(max(0.0, score), 4)

    @staticmethod
    def _content_fingerprint(content: str) -> str:
        compact = re.sub(r"\s+", "", content.lower())
        return compact[:180]

    def _build_document_profile(self, text: str, file_name: str, file_type: str) -> Dict[str, Any]:
        compact = self._compact_text(text)
        paragraphs = self._paragraphs(text)
        sentences = self._sentences(text)
        keywords = self._extract_profile_keywords(text)
        outline = self._build_outline(paragraphs)
        important_passages = self._important_passages(sentences, keywords)
        language = self._detect_language(text)
        title = self._infer_title(file_name, paragraphs)
        short_summary = self._build_profile_summary(compact, important_passages)
        topics = keywords[:5]
        return {
            "profile_version": "1",
            "title": title,
            "short_summary": short_summary,
            "outline": outline,
            "keywords": keywords,
            "detected_topics": topics,
            "important_passages": important_passages,
            "possible_questions": self._possible_questions(title, topics),
            "document_language": language,
            "stats": {
                "character_count": len(text),
                "paragraph_count": len(paragraphs),
                "sentence_count": len(sentences),
                "estimated_tokens": max(1, len(compact) // 4) if compact else 0,
                "file_type": file_type,
            },
            "summary_method": "deterministic_extractive",
        }

    def _legacy_document_profile(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        summary = entry.get("summary", "")
        return {
            "profile_version": "legacy",
            "title": entry.get("file_name", ""),
            "short_summary": summary,
            "outline": [],
            "keywords": [],
            "detected_topics": [],
            "important_passages": [summary] if summary else [],
            "possible_questions": [],
            "document_language": "unknown",
            "stats": {
                "character_count": int(entry.get("text_length", 0) or 0),
                "paragraph_count": 0,
                "sentence_count": 0,
                "estimated_tokens": 0,
                "file_type": entry.get("file_type", ""),
            },
            "summary_method": "legacy_truncated",
        }

    @staticmethod
    def _compact_text(text: str) -> str:
        return " ".join(text.replace("\r", "\n").split())

    @staticmethod
    def _paragraphs(text: str) -> List[str]:
        return [part.strip() for part in re.split(r"\n\s*\n", text.replace("\r", "\n")) if part.strip()]

    @staticmethod
    def _sentences(text: str) -> List[str]:
        parts = re.split(r"(?<=[.!?])\s+|[。！？]\s*|\n+", text.replace("\r", "\n"))
        return [part.strip() for part in parts if part.strip()]

    def _extract_profile_keywords(self, text: str, max_items: int = 8) -> List[str]:
        chinese_terms = re.findall(r"[\u4e00-\u9fff]{2,}", text)
        english_terms = re.findall(r"[A-Za-z][A-Za-z0-9_\-]{2,}", text.lower())
        stopwords = {
            "the",
            "and",
            "for",
            "with",
            "from",
            "this",
            "that",
            "是一个",
            "以及",
            "用于",
            "如何",
        }
        terms = [term for term in chinese_terms + english_terms if term not in stopwords]
        if not terms:
            return []
        return [term for term, _ in Counter(terms).most_common(max_items)]

    def _build_outline(self, paragraphs: List[str], max_items: int = 6) -> List[Dict[str, Any]]:
        outline: List[Dict[str, Any]] = []
        for idx, paragraph in enumerate(paragraphs[:max_items], start=1):
            heading = self._compact_text(paragraph)
            if len(heading) > 80:
                heading = heading[:77] + "..."
            outline.append(
                {
                    "level": 1,
                    "title": heading,
                    "position": idx,
                }
            )
        return outline

    def _important_passages(self, sentences: List[str], keywords: List[str], max_items: int = 3) -> List[str]:
        if not sentences:
            return []
        scored: List[tuple[float, int, str]] = []
        for idx, sentence in enumerate(sentences):
            compact = self._compact_text(sentence)
            if not compact:
                continue
            searchable = compact.lower()
            keyword_hits = sum(1 for keyword in keywords if keyword and keyword in searchable)
            length_score = min(1.0, len(compact) / 120)
            scored.append((keyword_hits + length_score, idx, compact))
        scored.sort(key=lambda item: (-item[0], item[1]))
        passages = [item[2] for item in scored[:max_items]]
        return [passage[:220] + "..." if len(passage) > 220 else passage for passage in passages]

    @staticmethod
    def _detect_language(text: str) -> str:
        chinese_count = len(re.findall(r"[\u4e00-\u9fff]", text))
        english_count = len(re.findall(r"[A-Za-z]", text))
        if chinese_count and english_count:
            return "mixed" if min(chinese_count, english_count) / max(chinese_count, english_count) > 0.15 else ("zh" if chinese_count > english_count else "en")
        if chinese_count:
            return "zh"
        if english_count:
            return "en"
        return "unknown"

    def _infer_title(self, file_name: str, paragraphs: List[str]) -> str:
        if paragraphs:
            first = self._compact_text(paragraphs[0])
            if 4 <= len(first) <= 80:
                return first
        return Path(file_name).stem or file_name

    def _build_profile_summary(self, compact: str, important_passages: List[str]) -> str:
        if important_passages:
            return self._build_summary(" ".join(important_passages), max_length=220)
        return self._build_summary(compact, max_length=220)

    @staticmethod
    def _possible_questions(title: str, topics: List[str], max_items: int = 4) -> List[str]:
        seeds = topics[:max_items] or ([title] if title else [])
        return [f"What does the document say about {topic}?" for topic in seeds[:max_items]]

    @_user_synchronized
    def retrieve_for_chat(self, user_id: str, query: str, top_k: int = 3) -> List[str]:
        payload = self.retrieve_for_chat_with_citations(user_id, query, top_k=top_k)
        return payload["snippets"]

    @_user_synchronized
    def retrieve_for_chat_with_citations(self, user_id: str, query: str, top_k: int = 3) -> Dict[str, Any]:
        hits = self.query(user_id, query, top_k=top_k)
        snippets = [
            f"[{hit.get('citation_id') or hit.get('chunk_id')}] {hit.get('file_name', '')}: {hit.get('content', '')}"
            for hit in hits
        ]
        citations = []
        retrieval_explanations = []
        for hit in hits:
            citation = dict(hit.get("citation") or {})
            citation["citation_id"] = hit.get("citation_id", citation.get("citation_id", ""))
            citation["snippet"] = hit.get("snippet", citation.get("snippet", ""))
            citation["selection_status"] = hit.get("selection_status", "")
            citation["final_rank"] = hit.get("final_rank", 0)
            citation["rerank_score"] = hit.get("rerank_score", 0.0)
            citations.append(citation)
            retrieval_explanations.append(
                {
                    "citation_id": hit.get("citation_id", ""),
                    "chunk_id": hit.get("chunk_id", ""),
                    "file_id": hit.get("file_id", ""),
                    "file_name": hit.get("file_name", ""),
                    "selected": hit.get("selection_status") == "selected",
                    "reason": hit.get("selection_reason", ""),
                    "retrieval_mode": hit.get("retrieval_mode", ""),
                    "retrieval_score": hit.get("retrieval_score", 0.0),
                    "rerank_score": hit.get("rerank_score", 0.0),
                    "final_rank": hit.get("final_rank", 0),
                    "candidate_rank": hit.get("candidate_rank", 0),
                    "snippet": hit.get("snippet", ""),
                    "factors": {
                        "vector_score": hit.get("vector_score", 0.0),
                        "keyword_score": hit.get("keyword_score", 0.0),
                        "filename_score": hit.get("filename_score", 0.0),
                        "recency_score": hit.get("recency_score", 0.0),
                        "query_coverage": hit.get("query_coverage", 0.0),
                        "length_quality": hit.get("length_quality", 0.0),
                        "duplicate_penalty": hit.get("duplicate_penalty", 0.0),
                        "diversity_penalty": hit.get("diversity_penalty", 0.0),
                    },
                }
            )
        return {
            "snippets": snippets,
            "citations": citations,
            "hits": hits,
            "retrieval_explanations": retrieval_explanations,
        }

    def _load_index(self, user_id: str) -> List[Dict[str, Any]]:
        index_path = self.base_path / user_id / "index.json"
        if not index_path.exists():
            return []
        return json.loads(index_path.read_text(encoding="utf-8"))

    def _find_by_hash(self, user_id: str, content_hash: str) -> Dict[str, Any] | None:
        for item in self._load_index(user_id):
            if item.get("content_hash") == content_hash:
                return item
        return None

    def _build_citation(
        self,
        *,
        chunk_id: str,
        metadata: Dict[str, Any],
        content: str,
        score: float,
    ) -> Dict[str, Any]:
        file_id = str(metadata.get("file_id", "") or "")
        chunk_index = int(metadata.get("chunk_index", 0) or 0)
        char_start = int(metadata.get("char_start", 0) or 0)
        char_end = int(metadata.get("char_end", 0) or 0)
        citation_id = f"{file_id}#chunk-{chunk_index}" if file_id else chunk_id
        return {
            "citation_id": citation_id,
            "chunk_id": chunk_id,
            "file_id": file_id,
            "file_name": metadata.get("file_name", ""),
            "chunk_index": chunk_index,
            "char_start": char_start,
            "char_end": char_end,
            "page_start": metadata.get("page_start", ""),
            "page_end": metadata.get("page_end", ""),
            "section_title": metadata.get("section_title", ""),
            "token_estimate": int(metadata.get("token_estimate", 0) or 0),
            "content_hash": metadata.get("content_hash", ""),
            "score": score,
            "snippet": self._build_snippet(content),
        }

    def _keyword_score(self, query: str, content: str, file_name: str) -> float:
        query_terms = self._tokenize_for_keyword(query)
        if not query_terms:
            return 0.0
        searchable = f"{file_name}\n{content}".lower()
        searchable_terms = set(self._tokenize_for_keyword(searchable))
        matched_terms = {term for term in query_terms if term in searchable_terms or term in searchable}
        if not matched_terms:
            return 0.0
        overlap_score = len(matched_terms) / len(set(query_terms))
        compact_query = re.sub(r"\s+", "", query.lower())
        compact_searchable = re.sub(r"\s+", "", searchable)
        phrase_boost = 0.25 if len(compact_query) >= 3 and compact_query in compact_searchable else 0.0
        return round(min(1.0, overlap_score + phrase_boost), 4)

    def _filename_score(self, query: str, file_name: str) -> float:
        query_terms = set(self._tokenize_for_keyword(query))
        if not query_terms:
            return 0.0
        file_terms = set(self._tokenize_for_keyword(file_name))
        if not file_terms:
            return 0.0
        return round(len(query_terms & file_terms) / len(query_terms), 4)

    @staticmethod
    def _recency_score(uploaded_at: str) -> float:
        if not uploaded_at:
            return 0.0
        try:
            uploaded = datetime.fromisoformat(uploaded_at.replace("Z", "+00:00"))
            if uploaded.tzinfo is None:
                uploaded = uploaded.replace(tzinfo=timezone.utc)
        except ValueError:
            return 0.0
        age_days = max(0.0, (datetime.now(timezone.utc) - uploaded).total_seconds() / 86400)
        return round(1 / (1 + age_days / 30), 4)

    @staticmethod
    def _fusion_score(
        *,
        vector_score: float,
        keyword_score: float,
        filename_score: float,
        recency_score: float,
        file_filter_score: float,
    ) -> float:
        strong_signal = max(vector_score, keyword_score)
        score = (
            strong_signal
            + keyword_score * 0.12
            + filename_score * 0.05
            + recency_score * 0.03
            + file_filter_score * 0.02
        )
        return round(min(1.5, max(0.0, score)), 4)

    @staticmethod
    def _validate_retrieval_strategy(retrieval_strategy: str) -> str:
        normalized = str(retrieval_strategy or "").strip().lower()
        if normalized not in SUPPORTED_RETRIEVAL_STRATEGIES:
            supported = ", ".join(sorted(SUPPORTED_RETRIEVAL_STRATEGIES))
            raise ValueError(f"Unsupported retrieval strategy: {retrieval_strategy!r}. Expected one of: {supported}")
        return normalized

    @staticmethod
    def _retrieval_reason(retrieval_sources: List[str], keyword_score: float, filename_score: float) -> str:
        if "vector" in retrieval_sources and "keyword" in retrieval_sources:
            return "selected by both vector similarity and keyword match"
        if "keyword" in retrieval_sources:
            if filename_score > 0:
                return "selected by keyword match with filename boost"
            if keyword_score >= 0.8:
                return "selected by strong keyword match"
            return "selected by keyword overlap"
        if "vector" in retrieval_sources:
            return "selected by vector similarity"
        return "selected by retrieval fallback"

    @staticmethod
    def _tokenize_for_keyword(text: str) -> List[str]:
        return re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]", text.lower())

    @staticmethod
    def _build_snippet(content: str, max_length: int = 220) -> str:
        compact = " ".join(content.replace("\r", "\n").split())
        if len(compact) <= max_length:
            return compact
        return compact[: max_length - 3] + "..."

    def _save_index(self, user_id: str, index: List[Dict[str, Any]]) -> None:
        user_dir = self.base_path / user_id
        user_dir.mkdir(parents=True, exist_ok=True)
        index_path = user_dir / "index.json"
        payload = json.dumps(index, ensure_ascii=False, indent=2) + "\n"
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="\n",
                delete=False,
                dir=user_dir,
                prefix="index-",
                suffix=".tmp",
            ) as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
                temporary_path = Path(handle.name)
            os.replace(temporary_path, index_path)
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink(missing_ok=True)

    def _write_bytes_atomic(self, path: Path, content: bytes) -> None:
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                delete=False,
                dir=path.parent,
                prefix=f"{path.name}-",
                suffix=".tmp",
            ) as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
                temporary_path = Path(handle.name)
            os.replace(temporary_path, path)
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink(missing_ok=True)

    def _lock_for_user(self, user_id: str) -> threading.RLock:
        normalized = str(user_id or "").strip()
        if not normalized:
            raise ValueError("user_id cannot be blank")
        if not hasattr(self, "_locks_guard"):
            self._locks_guard = threading.Lock()
            self._user_locks = {}
        with self._locks_guard:
            lock = self._user_locks.get(normalized)
            if lock is None:
                lock = threading.RLock()
                self._user_locks[normalized] = lock
            return lock

    @staticmethod
    def _sanitize_filename(filename: str) -> str:
        base = os.path.basename(filename)
        safe = re.sub(r"[^A-Za-z0-9._\-\u4e00-\u9fff]", "_", base)
        return safe or "uploaded_file"

    def _public_file_entry(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "file_id": entry["file_id"],
            "file_name": entry["file_name"],
            "file_type": entry["file_type"],
            "size_bytes": int(entry.get("size_bytes", 0) or 0),
            "content_hash": entry.get("content_hash", ""),
            "chunk_count": entry["chunk_count"],
            "uploaded_at": entry["uploaded_at"],
            "summary": entry.get("summary", ""),
            "document_profile": entry.get("document_profile", self._legacy_document_profile(entry)),
            "parser": entry.get("parser", ""),
            "parser_version": entry.get("parser_version", ""),
            "text_length": int(entry.get("text_length", 0) or 0),
            "embedding_provider": entry.get("embedding_provider", ""),
            "embedding_model": entry.get("embedding_model", ""),
            "ingestion_status": entry.get("ingestion_status", "indexed"),
            "ingestion_warnings": entry.get("ingestion_warnings", []),
        }

    @staticmethod
    def _build_summary(text: str, max_length: int = 120) -> str:
        compact = " ".join(text.replace("\r", "\n").split())
        if not compact:
            return "暂无摘要"
        if len(compact) <= max_length:
            return compact
        return compact[: max_length - 3] + "..."

    @staticmethod
    def _parser_name(file_type: str) -> str:
        return {
            "txt": "plain_text",
            "pdf": "pypdf",
            "docx": "python_docx",
        }.get(file_type, "unknown")
