import hashlib
import json
from functools import wraps
from threading import RLock

from app.context.context import ConversationContext
from app.knowledge.service import KnowledgeService
from app.memory.mem_service import MemoryService
from app.model.base import BaseLLM
from app.prompt.prompt_builder import PromptBuilder
from app.runtime.agent_store import AgentRunStore
from app.runtime.agent_trace import AgentRun, start_step
from app.runtime.error_model import AppError, ErrorCode, ErrorInfo, classify_exception
from app.runtime.resilience import Deadline
from app.task.service.task_service import TaskService


def _conversation_synchronized(method):
    @wraps(method)
    def locked(self, user_id: str, message: str, *args, **kwargs):
        conversation_id = kwargs.get("conversation_id")
        if conversation_id is None and args:
            conversation_id = args[0]
        deadline = kwargs.pop("_deadline", None) or Deadline.after(self.chat_deadline_seconds)
        conversation_lock = self._conversation_lock(user_id, conversation_id)
        if not conversation_lock.acquire(timeout=max(0.0, deadline.remaining_seconds())):
            raise AppError(
                ErrorInfo(
                    code=ErrorCode.OPERATION_TIMEOUT,
                    message="The operation deadline was exceeded.",
                    retryable=True,
                    operation="chat.conversation_lock",
                )
            )
        try:
            kwargs["_deadline"] = deadline
            return method(self, user_id, message, *args, **kwargs)
        finally:
            conversation_lock.release()

    return locked


class ChatResult:
    def __init__(self, reply: str, trace: AgentRun):
        self.reply = reply
        self.trace = trace


class AgentService:
    def __init__(
        self,
        *,
        memory_service: MemoryService,
        knowledge_service: KnowledgeService,
        task_service: TaskService,
        chat_llm: BaseLLM,
        context_manager: ConversationContext | None = None,
        prompt_builder: PromptBuilder | None = None,
        run_store: AgentRunStore | None = None,
        maintenance_scheduler=None,
        chat_deadline_seconds: float = 150.0,
    ) -> None:
        self.memory_service = memory_service
        self.knowledge_service = knowledge_service
        self.task_service = task_service
        self.chat_llm = chat_llm
        self.context_manager = context_manager or ConversationContext(max_turns=6)
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.run_store = run_store or AgentRunStore()
        self.maintenance_scheduler = maintenance_scheduler
        self.chat_deadline_seconds = float(chat_deadline_seconds)
        self._conversation_lock_stripes = [RLock() for _ in range(128)]

    @_conversation_synchronized
    def generate_reply(
        self,
        user_id: str,
        message: str,
        conversation_id: int | None = None,
        history: list[dict[str, str]] | None = None,
        idempotency_key: str | None = None,
        _deadline: Deadline | None = None,
    ) -> ChatResult:
        deadline = _deadline or Deadline.after(self.chat_deadline_seconds)
        request_hash = self._request_hash(
            user_id=user_id,
            message=message,
            conversation_id=conversation_id,
            history=history,
        )
        if idempotency_key:
            trace, created = self.run_store.create_or_get(
                user_id,
                conversation_id,
                kind="chat",
                idempotency_key=idempotency_key,
                request_hash=request_hash,
            )
            if not created:
                reply = str((trace.response or {}).get("reply") or "")
                if trace.status == "completed" and reply:
                    return ChatResult(reply=reply, trace=trace)
                raise AppError(
                    ErrorInfo(
                        code=ErrorCode.CONFLICT,
                        message="An equivalent chat request is already in progress or did not complete.",
                        retryable=trace.status == "running",
                        operation="chat.generate",
                        details={"run_id": trace.run_id, "status": trace.status},
                    )
                )
        else:
            trace = self.run_store.create(user_id, conversation_id, kind="chat")
        context_key = f"{user_id}:{conversation_id}" if conversation_id is not None else user_id
        current_operation = "context.load_history"

        try:
            deadline.raise_if_expired(operation=current_operation)
            step_started_at, step_started_perf = start_step()
            context = self.context_manager.load_history(context_key, history)
            trace.add_step(
                name="context.load_history",
                status="completed",
                started_at=step_started_at,
                started_perf=step_started_perf,
                input_summary=f"history_items={len(history or [])}",
                output_summary=f"context_items={len(context)}",
            )
            self.run_store.save(trace)

            current_operation = "task.handle"
            deadline.raise_if_expired(operation=current_operation)
            step_started_at, step_started_perf = start_step()
            task_decision = self.task_service.handle_task(
                message,
                user_id=user_id,
                conversation_id=conversation_id,
                agent_run_id=trace.run_id,
                idempotency_key=(
                    self._child_task_idempotency_key(idempotency_key, trace.run_id)
                    if idempotency_key
                    else None
                ),
                idempotency_scope="chat_child",
                deadline=deadline,
            )
            deadline.raise_if_expired(operation=current_operation)
            task_result = task_decision.result or {}
            trace.add_step(
                name="task.handle",
                status="completed" if task_result.get("success", False) else "failed",
                started_at=step_started_at,
                started_perf=step_started_perf,
                input_summary="detect and execute task plan if needed",
                output_summary=f"need_tool={bool((task_decision.plan or {}).get('need_tool'))}",
                metadata={
                    "task_run_id": task_decision.task_run_id,
                    "plan": task_decision.plan,
                    "result": task_decision.result,
                    "success": task_decision.success,
                    "error": task_decision.error,
                },
            )
            self.run_store.save(trace)

            current_operation = "memory.write"
            deadline.raise_if_expired(operation=current_operation)
            step_started_at, step_started_perf = start_step()
            memory_write_result = self.memory_service.try_process_user_input(
                user_id,
                message,
                conversation_id=conversation_id,
                source="chat_extraction",
            )
            deadline.raise_if_expired(operation=current_operation)
            trace.add_step(
                name="memory.write",
                status="completed",
                started_at=step_started_at,
                started_perf=step_started_perf,
                input_summary="extract and persist candidate memory",
                output_summary=f"written={memory_write_result.get('written')}",
                metadata=memory_write_result,
            )
            self.run_store.save(trace)

            current_operation = "memory.retrieve"
            deadline.raise_if_expired(operation=current_operation)
            step_started_at, step_started_perf = start_step()
            selected_memories, retrieval_explanations = self.memory_service.try_retrieve_for_context_with_explanation(
                user_id,
                message,
                conversation_id=conversation_id,
            )
            deadline.raise_if_expired(operation=current_operation)
            trace.add_step(
                name="memory.retrieve",
                status="completed",
                started_at=step_started_at,
                started_perf=step_started_perf,
                input_summary="retrieve memories for prompt context",
                output_summary=f"memories={len(selected_memories)}",
                metadata={
                    "memories": [
                        {
                            "memory_id": memory.memory_id,
                            "mem_type": memory.mem_type,
                            "similarity": round(memory.similarity, 4),
                            "final_score": round(memory.final_score, 4),
                            "confidence": round(memory.confidence, 4),
                            "scope": memory.scope,
                            "sensitivity": memory.sensitivity,
                            "review_status": memory.review_status,
                            "source": memory.source,
                            "content": memory.content,
                        }
                        for memory in selected_memories
                    ],
                    "retrieval_explanations": retrieval_explanations,
                    "citations": [
                        {
                            "memory_id": memory.memory_id,
                            "content": memory.content,
                            "mem_type": memory.mem_type,
                            "source": memory.source,
                            "confidence": round(memory.confidence, 4),
                            "scope": memory.scope,
                        }
                        for memory in selected_memories
                    ],
                },
            )
            self.run_store.save(trace)

            current_operation = "knowledge.retrieve"
            deadline.raise_if_expired(operation=current_operation)
            step_started_at, step_started_perf = start_step()
            knowledge_context = self.knowledge_service.retrieve_for_chat_with_citations(user_id, message, top_k=3)
            deadline.raise_if_expired(operation=current_operation)
            selected_knowledge = knowledge_context["snippets"]
            trace.add_step(
                name="knowledge.retrieve",
                status="completed",
                started_at=step_started_at,
                started_perf=step_started_perf,
                input_summary="retrieve knowledge snippets for prompt context",
                output_summary=f"snippets={len(selected_knowledge)}",
                metadata={
                    "snippets": selected_knowledge,
                    "citations": knowledge_context["citations"],
                    "retrieval_explanations": knowledge_context["retrieval_explanations"],
                    "hits": knowledge_context["hits"],
                },
            )
            self.run_store.save(trace)

            current_operation = "memory.maintenance.schedule"
            deadline.raise_if_expired(operation=current_operation)
            step_started_at, step_started_perf = start_step()
            if self.maintenance_scheduler is None:
                maintenance_report = {
                    "scheduled": False,
                    "reason": "memory maintenance scheduler disabled",
                }
                maintenance_status = "completed"
            else:
                try:
                    maintenance_report = self.maintenance_scheduler.schedule(user_id)
                    maintenance_report["scheduled"] = True
                    maintenance_status = "completed"
                except Exception as exc:
                    maintenance_error = classify_exception(
                        exc,
                        operation="memory.maintenance.schedule",
                    )
                    maintenance_report = {
                        "scheduled": False,
                        "error": maintenance_error.to_dict(),
                    }
                    maintenance_status = "failed"
            trace.add_step(
                name="memory.maintenance.schedule",
                status=maintenance_status,
                started_at=step_started_at,
                started_perf=step_started_perf,
                input_summary="schedule maintenance outside the chat hot path",
                output_summary=f"scheduled={self.maintenance_scheduler is not None}",
                metadata=maintenance_report,
            )
            self.run_store.save(trace)

            current_operation = "prompt.build"
            deadline.raise_if_expired(operation=current_operation)
            step_started_at, step_started_perf = start_step()
            prompt = self.prompt_builder.build_prompt(
                task_result=task_decision.result,
                memories=selected_memories,
                message=message,
                context=context,
                knowledge_snippets=selected_knowledge,
            )
            trace.add_step(
                name="prompt.build",
                status="completed",
                started_at=step_started_at,
                started_perf=step_started_perf,
                input_summary="compose task, memory, knowledge, and chat context",
                output_summary=f"prompt_chars={len(prompt)}",
            )
            self.run_store.save(trace)

            current_operation = "llm.generate"
            deadline.raise_if_expired(operation=current_operation)
            step_started_at, step_started_perf = start_step()
            response = self.chat_llm.generate(prompt)
            deadline.raise_if_expired(operation=current_operation)
            if not str(response or "").strip():
                raise RuntimeError("model returned an empty response")
            trace.add_step(
                name="llm.generate",
                status="completed",
                started_at=step_started_at,
                started_perf=step_started_perf,
                input_summary="generate assistant reply",
                output_summary=f"reply_chars={len(response)}",
            )
            self.run_store.save(trace)

            current_operation = "context.update"
            deadline.raise_if_expired(operation=current_operation)
            step_started_at, step_started_perf = start_step()
            self.context_manager.add_user_message(context_key, message)
            self.context_manager.add_assistant_message(context_key, response)
            trace.add_step(
                name="context.update",
                status="completed",
                started_at=step_started_at,
                started_perf=step_started_perf,
                input_summary="append user and assistant messages",
            )
            self.run_store.save_response(trace, {"reply": response}, status="completed")
            return ChatResult(reply=response, trace=trace)
        except AppError as exc:
            info = self._with_run_id(exc.info, trace.run_id)
            self.run_store.save_response(
                trace,
                {"error": info.to_dict()},
                status="failed",
                error_code=info.code.value,
                error_message=info.message,
                retryable=info.retryable,
            )
            raise AppError(info, cause=exc.cause or exc) from exc
        except Exception as exc:
            info = self._with_run_id(
                classify_exception(exc, operation=current_operation),
                trace.run_id,
            )
            self.run_store.save_response(
                trace,
                {"error": info.to_dict()},
                status="failed",
                error_code=info.code.value,
                error_message=info.message,
                retryable=info.retryable,
            )
            raise AppError(info, cause=exc) from exc

    @staticmethod
    def _with_run_id(info: ErrorInfo, run_id: str) -> ErrorInfo:
        return ErrorInfo(
            code=info.code,
            message=info.message,
            retryable=info.retryable,
            category=info.category,
            operation=info.operation,
            dependency=info.dependency,
            details={**dict(info.details), "run_id": run_id},
        )

    @staticmethod
    def _request_hash(
        *,
        user_id: str,
        message: str,
        conversation_id: int | None,
        history: list[dict[str, str]] | None,
    ) -> str:
        normalized_history = [
            {
                "role": str(item.get("role") or ""),
                "content": str(item.get("content") or ""),
            }
            for item in (history or [])
        ]
        payload = json.dumps(
            {
                "conversation_id": conversation_id,
                "history": normalized_history,
                "message": message,
                "user_id": user_id,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    @staticmethod
    def _child_task_idempotency_key(parent_key: str, agent_run_id: str) -> str:
        digest = hashlib.sha256(
            f"{parent_key}\0{agent_run_id}".encode("utf-8")
        ).hexdigest()
        return f"chat-child:{digest}"

    def _conversation_lock(self, user_id: str, conversation_id: int | None) -> RLock:
        key = f"{user_id}:{conversation_id if conversation_id is not None else 'new'}"
        digest = hashlib.sha256(key.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % len(self._conversation_lock_stripes)
        return self._conversation_lock_stripes[index]
