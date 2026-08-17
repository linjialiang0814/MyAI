from concurrent.futures import Future, ThreadPoolExecutor, wait
import hashlib
import json
import re
from threading import Lock
import time
from typing import Any

from app.runtime.error_model import AppError, ErrorCode, ErrorInfo, classify_exception
from app.runtime.resilience import Deadline
from app.task.plan.executor import ToolExecutor
from app.task.plan.recovery import RecoveryPlanner
from app.task.runtime import TaskRun
from app.task.runtime import TaskRunStore
from app.task.stats.record import DecisionRecord
from app.task.stats.statistics import StatsManager


class TaskService:
    def __init__(
        self,
        rec_planner: RecoveryPlanner,
        task_executor: ToolExecutor,
        stats: StatsManager,
        run_store: TaskRunStore | None = None,
        agent_run_store: Any | None = None,
        memory_service: Any | None = None,
        maintenance_scheduler: Any | None = None,
        max_pending_tasks: int = 100,
        task_deadline_seconds: float = 120.0,
    ):
        self.rec_planner = rec_planner
        self.task_executor = task_executor
        self.stats = stats
        self.run_store = run_store if run_store is not None else TaskRunStore()
        self.agent_run_store = agent_run_store
        self.memory_service = memory_service
        self.maintenance_scheduler = maintenance_scheduler
        self.max_pending_tasks = max(1, int(max_pending_tasks))
        self.task_deadline_seconds = float(task_deadline_seconds)
        self.background_executor = ThreadPoolExecutor(max_workers=2)
        self.background_futures: dict[str, Future] = {}
        self._background_lock = Lock()
        self._closed = False
        self._shutdown_complete = False

    def close(self, timeout_seconds: float = 5.0) -> bool:
        started_at = time.monotonic()
        with self._background_lock:
            self._closed = True
            future_items = list(self.background_futures.items())
            if self._shutdown_complete:
                return True
        futures = []
        for task_run_id, future in future_items:
            run = self.run_store.get(task_run_id)
            if run is not None:
                self.run_store.request_cancel(run)
            if future.cancel() and run is not None:
                self.run_store.cancel(run)
            futures.append(future)
        not_done = set()
        if futures:
            _, not_done = wait(futures, timeout=max(0.0, timeout_seconds))
        if not_done:
            return False
        close_executor = getattr(self.task_executor, "close", None)
        if callable(close_executor):
            remaining = max(0.0, timeout_seconds - (time.monotonic() - started_at))
            if close_executor(timeout_seconds=remaining) is False:
                return False
        with self._background_lock:
            self.background_futures.clear()
            self._shutdown_complete = True
        self.background_executor.shutdown(wait=False, cancel_futures=True)
        return True

    def get_run(self, task_run_id: str, *, user_id: str | None = None) -> dict[str, Any] | None:
        run = self.run_store.get(task_run_id)
        if run and user_id is not None and run.user_id != user_id:
            return None
        return run.to_dict() if run else None

    def list_runs(
        self,
        user_id: str | None = None,
        limit: int = 20,
        *,
        agent_run_id: str | None = None,
    ) -> list[dict[str, Any]]:
        return [
            run.to_dict()
            for run in self.run_store.list_runs(
                user_id=user_id,
                agent_run_id=agent_run_id,
                limit=limit,
            )
        ]

    def list_workflows(self) -> list[dict[str, Any]]:
        if hasattr(self.rec_planner, "list_workflows"):
            return self.rec_planner.list_workflows()
        return []

    def list_tools(self) -> list[dict[str, Any]]:
        registry = self.task_executor.registry
        tools = []
        for tool in registry.list_tools():
            descriptor = getattr(tool, "descriptor", None)
            policy = tool.policy.to_dict() if hasattr(tool.policy, "to_dict") else {}
            schema = tool.schema
            source = "mcp" if descriptor is not None else "local"
            tools.append(
                {
                    "name": tool.name,
                    "description": tool.description,
                    "source": source,
                    "server_id": getattr(descriptor, "server_id", "") if descriptor is not None else "",
                    "external_tool_name": getattr(descriptor, "name", "") if descriptor is not None else "",
                    "status": "available",
                    "health": {"ok": True, "message": "registered"},
                    "policy": policy,
                    "policy_metadata": dict(getattr(descriptor, "policy_metadata", {}) or {}) if descriptor is not None else {},
                    "schema": schema.get("function", {}).get("parameters", {}),
                    "required": schema.get("function", {}).get("parameters", {}).get("required", []),
                    "trigger_words": dict(getattr(tool, "trigger_words", {}) or {}),
                    "negative_triggers": dict(getattr(tool, "negative_triggers", {}) or {}),
                }
            )
        tools.sort(key=lambda item: (item["source"], item["name"]))
        return tools

    def list_connectors(self) -> list[dict[str, Any]]:
        registry = self.task_executor.registry
        connectors: dict[str, dict[str, Any]] = {}
        for tool in registry.list_tools():
            descriptor = getattr(tool, "descriptor", None)
            if descriptor is None:
                continue
            server_id = getattr(descriptor, "server_id", "")
            client = getattr(tool, "client", None)
            if server_id not in connectors:
                inspected = client.inspect_connector() if client is not None and hasattr(client, "inspect_connector") else {}
                connectors[server_id] = {
                    "server_id": server_id,
                    "name": inspected.get("name") or server_id,
                    "description": inspected.get("description") or "",
                    "enabled": inspected.get("enabled", True),
                    "health": inspected.get("health") or {"ok": True, "message": "registered"},
                    "settings": inspected.get("settings") or {},
                    "risk_summary": inspected.get("risk_summary") or {},
                    "tools": [],
                    "tool_count": 0,
                    "risk_levels": [],
                    "requires_confirmation_count": 0,
                    "hosted_blocked_count": 0,
                }
            policy = tool.policy.to_dict() if hasattr(tool.policy, "to_dict") else {}
            connectors[server_id]["tools"].append(
                {
                    "name": tool.name,
                    "external_tool_name": getattr(descriptor, "name", ""),
                    "description": tool.description,
                    "policy": policy,
                }
            )
            connectors[server_id]["tool_count"] += 1
            risk_level = str(policy.get("risk_level") or "unknown")
            if risk_level not in connectors[server_id]["risk_levels"]:
                connectors[server_id]["risk_levels"].append(risk_level)
            if policy.get("requires_confirmation"):
                connectors[server_id]["requires_confirmation_count"] += 1
            if not policy.get("allowed_in_hosted", True):
                connectors[server_id]["hosted_blocked_count"] += 1
        result = list(connectors.values())
        result.sort(key=lambda item: item["server_id"])
        return result

    def start_background_task(
        self,
        content: str,
        user_id: str | None = None,
        *,
        conversation_id: int | None = None,
        agent_run_id: str | None = None,
        idempotency_key: str | None = None,
        idempotency_scope: str = "standalone",
    ) -> dict[str, Any]:
        with self._background_lock:
            if self._closed:
                raise RuntimeError("Task service is closed")
            if idempotency_key:
                existing = self.run_store.replay_if_exists(
                    user_id=user_id,
                    content=content,
                    agent_run_id=agent_run_id,
                    conversation_id=conversation_id,
                    idempotency_key=idempotency_key,
                    idempotency_scope=idempotency_scope,
                )
                if existing is not None:
                    return existing.to_dict()
            if len(self.background_futures) >= self.max_pending_tasks:
                raise AppError(
                    ErrorInfo(
                        code=ErrorCode.RATE_LIMITED,
                        message="The task queue is full.",
                        retryable=True,
                        operation="task.enqueue",
                        details={"max_pending_tasks": self.max_pending_tasks},
                    )
                )
            resolved_agent_run_id = self._resolve_agent_run_link(
                user_id=user_id,
                conversation_id=conversation_id,
                content=content,
                agent_run_id=agent_run_id,
                idempotency_key=idempotency_key,
            )
            if idempotency_key:
                run, created = self.run_store.create_or_get(
                    user_id=user_id,
                    content=content,
                    agent_run_id=resolved_agent_run_id,
                    conversation_id=conversation_id,
                    idempotency_key=idempotency_key,
                    idempotency_scope=idempotency_scope,
                )
            else:
                run = self.run_store.create(
                    user_id=user_id,
                    content=content,
                    agent_run_id=resolved_agent_run_id,
                    conversation_id=conversation_id,
                )
                created = True
            if not created:
                return run.to_dict()
            self.run_store.mark_queued(run, background=True)
            future = self.background_executor.submit(self._execute_run, run)
            self.background_futures[run.task_run_id] = future
        future.add_done_callback(lambda _: self._discard_background_future(run.task_run_id))
        return run.to_dict()

    def _discard_background_future(self, task_run_id: str) -> None:
        with self._background_lock:
            self.background_futures.pop(task_run_id, None)

    def request_cancel(self, task_run_id: str, *, user_id: str | None = None) -> dict[str, Any] | None:
        run = self.run_store.get(task_run_id)
        if not run or (user_id is not None and run.user_id != user_id):
            return None
        cancelled = self.run_store.request_cancel(run)
        with self._background_lock:
            future = self.background_futures.get(task_run_id)
        if cancelled and future and not future.running():
            future.cancel()
            self.run_store.cancel(run)
        return run.to_dict()

    def handle_task(
        self,
        content: str,
        user_id: str | None = None,
        *,
        conversation_id: int | None = None,
        agent_run_id: str | None = None,
        idempotency_key: str | None = None,
        idempotency_scope: str = "standalone",
        deadline: Deadline | None = None,
    ) -> DecisionRecord:
        resolved_agent_run_id = self._resolve_agent_run_link(
            user_id=user_id,
            conversation_id=conversation_id,
            content=content,
            agent_run_id=agent_run_id,
            idempotency_key=idempotency_key,
        )
        if idempotency_key:
            run, created = self.run_store.create_or_get(
                user_id=user_id,
                content=content,
                agent_run_id=resolved_agent_run_id,
                conversation_id=conversation_id,
                idempotency_key=idempotency_key,
                idempotency_scope=idempotency_scope,
            )
            if not created:
                return self._decision_from_run(run)
        else:
            run = self.run_store.create(
                user_id=user_id,
                content=content,
                agent_run_id=resolved_agent_run_id,
                conversation_id=conversation_id,
            )
        return self._execute_run(run, deadline=deadline)

    def _execute_run(self, run: TaskRun, deadline: Deadline | None = None) -> DecisionRecord:
        local_deadline = Deadline.after(self.task_deadline_seconds)
        if deadline is None or local_deadline.remaining_seconds() <= deadline.remaining_seconds():
            deadline = local_deadline
        user_id = run.user_id
        content = run.content
        decision = DecisionRecord(
            task_run_id=run.task_run_id,
            agent_run_id=run.agent_run_id,
            conversation_id=run.conversation_id,
            status=run.status,
            user_id=user_id,
            content=content,
        )
        try:
            deadline.raise_if_expired(operation="task.execute")
            if run.cancel_requested:
                decision.result = {"success": False, "cancelled": True}
                decision.success = False
                decision.error = "Task cancelled"
                self.run_store.cancel(run, decision.result, latency_ms=0.0)
                self._apply_run_to_decision(decision, run)
                self.stats.record(decision)
                return decision
            self.run_store.mark_planning(run)
            decision.status = run.status
            memory_context = self._build_memory_context(run)
            deadline.raise_if_expired(operation="task.memory_context")
            plan = self.rec_planner.plan(content, short_context=memory_context.get("short_context", []))
            deadline.raise_if_expired(operation="task.plan")
            plan.memory_context = memory_context
            decision.plan = plan.to_dict()
            steps = plan.normalized_steps()
            self.run_store.set_plan(run, decision.plan, steps)
            if not plan.need_tool:
                decision.result = {"success": True}
                decision.reward = 0.0
                decision.success = True
                decision.latency_ms = 0.0
                self.run_store.succeed(run, decision.result, latency_ms=decision.latency_ms)
                self._apply_run_to_decision(decision, run)
                self.stats.record(decision)
                return decision

            context: dict[str, Any] = {"memory_context": memory_context}
            if user_id is not None:
                context["user_id"] = user_id
            context["task_content"] = content
            executed_steps: list[dict[str, Any]] = []
            total_latency_ms = 0.0
            self.run_store.mark_running(run)
            decision.status = run.status

            for step in steps:
                deadline.raise_if_expired(operation="task.execute")
                if run.cancel_requested:
                    decision.step_results = executed_steps
                    decision.result = {"success": False, "cancelled": True, "steps": executed_steps}
                    decision.latency_ms = round(total_latency_ms, 3)
                    decision.success = False
                    decision.error = "Task cancelled"
                    self.run_store.cancel(run, decision.result, decision.latency_ms)
                    self._apply_run_to_decision(decision, run)
                    self.stats.record(decision)
                    return decision
                resolved_args = self._resolve_step_args(step.tool_args, context)
                self.run_store.start_step(run, step.step_id, resolved_args)
                result, latency_ms = self.task_executor.execute(
                    step.tool_name,
                    resolved_args,
                    runtime_context={
                        "user_id": user_id,
                        "content": content,
                        "context": context,
                        "deadline": deadline,
                    },
                )
                total_latency_ms += latency_ms
                step_result = result.model_dump()
                self.run_store.record_mcp_call(run, step.step_id, step_result.get("metadata"), success=result.success, error=result.error)
                self.run_store.record_tool_policy(run, step.step_id, step_result.get("metadata"))
                self.run_store.record_recovery(run, step.step_id, step_result.get("metadata"))

                executed_steps.append(
                    {
                        "step_id": step.step_id,
                        "description": step.description,
                        "tool_name": step.tool_name,
                        "tool_args": resolved_args,
                        "result": step_result,
                        "latency_ms": round(latency_ms, 3),
                    }
                )

                if not result.success:
                    self.run_store.fail_step(run, step.step_id, step_result, latency_ms, result.error)
                    decision.step_results = executed_steps
                    decision.result = {
                        "success": False,
                        "steps": executed_steps,
                        "summary": f"Step {step.step_id} failed: {result.error}",
                    }
                    decision.latency_ms = round(total_latency_ms, 3)
                    outcome_memory = self._record_outcome_memory(run, decision.result, executed_steps, success=False)
                    if outcome_memory:
                        decision.result["outcome_memory"] = outcome_memory
                    decision.finalize()
                    decision.reward = self.stats.compute_reward(decision)
                    self.run_store.fail(
                        run,
                        result.error or f"Step {step.step_id} failed",
                        decision.result,
                        decision.latency_ms,
                        error_info=(result.metadata or {}).get("error_info"),
                    )
                    self._apply_run_to_decision(decision, run)
                    self.stats.record(decision)
                    return decision

                self.run_store.complete_step(run, step.step_id, step_result, latency_ms)
                self._update_context(context, step.step_id, step_result, step.output_key, step.extract_path)

            summary = self._build_summary(plan.final_response, context, executed_steps)
            decision.step_results = executed_steps
            decision.result = {
                "success": True,
                "steps": executed_steps,
                "context": context,
                "summary": summary,
            }
            decision.latency_ms = round(total_latency_ms, 3)
            outcome_memory = self._record_outcome_memory(run, decision.result, executed_steps, success=True)
            if outcome_memory:
                decision.result["outcome_memory"] = outcome_memory
            decision.finalize()
            decision.reward = self.stats.compute_reward(decision)
            self.run_store.succeed(run, decision.result, decision.latency_ms)
            self._apply_run_to_decision(decision, run)
            self.stats.record(decision)
            return decision

        except Exception as e:
            error_info = classify_exception(e, operation="task.execute")
            decision.success = False
            decision.error = error_info.message
            decision.reward = -1.0
            decision.result = {
                "success": False,
                "error": error_info.message,
                "error_info": error_info.to_dict(),
            }
            self.run_store.fail(
                run,
                error_info.message,
                decision.result,
                decision.latency_ms,
                error_info=error_info.to_dict(),
            )
            self._apply_run_to_decision(decision, run)
            self.stats.record(decision)
            return decision
        finally:
            self._finalize_standalone_agent_run(run)

    def _decision_from_run(self, run: TaskRun) -> DecisionRecord:
        decision = DecisionRecord(
            task_run_id=run.task_run_id,
            status=run.status,
            user_id=run.user_id,
            content=run.content,
            plan=run.plan,
            result=run.result,
            success=run.success,
            error=run.error,
            latency_ms=run.latency_ms,
        )
        self._apply_run_to_decision(decision, run)
        return decision

    def _resolve_agent_run_link(
        self,
        *,
        user_id: str | None,
        conversation_id: int | None,
        content: str,
        agent_run_id: str | None,
        idempotency_key: str | None,
    ) -> str | None:
        if self.agent_run_store is None:
            return agent_run_id
        if not user_id:
            raise ValueError("user_id is required when runtime persistence is enabled")
        if agent_run_id:
            parent = self.agent_run_store.get(agent_run_id)
            if parent is None:
                raise ValueError("agent_run_id does not reference an existing AgentRun")
            if parent.user_id != user_id or parent.conversation_id != conversation_id:
                raise ValueError("agent_run_id ownership or conversation does not match the task")
            return parent.run_id

        if idempotency_key:
            request_hash = hashlib.sha256(
                json.dumps(
                    {
                        "content": content,
                        "conversation_id": conversation_id,
                        "user_id": user_id,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()
            parent, _ = self.agent_run_store.create_or_get(
                user_id,
                conversation_id,
                kind="standalone_task",
                idempotency_key=idempotency_key,
                request_hash=request_hash,
            )
        else:
            parent = self.agent_run_store.create(
                user_id,
                conversation_id,
                kind="standalone_task",
            )
        return parent.run_id

    def _finalize_standalone_agent_run(self, run: TaskRun) -> None:
        if self.agent_run_store is None or not run.agent_run_id:
            return
        parent = self.agent_run_store.get(run.agent_run_id)
        if parent is None or parent.kind != "standalone_task" or parent.status != "running":
            return
        status = "completed" if run.status == "succeeded" else run.status
        self.agent_run_store.save_response(
            parent,
            {
                "task_run_id": run.task_run_id,
                "status": run.status,
                "success": run.success,
            },
            status=status,
            error_code=run.error_code if run.status == "failed" else None,
            error_message=run.error,
            retryable=run.retryable if run.status == "failed" else None,
        )

    def _apply_run_to_decision(self, decision: DecisionRecord, run) -> None:
        decision.agent_run_id = run.agent_run_id
        decision.conversation_id = run.conversation_id
        decision.status = run.status
        decision.error = run.error or decision.error
        decision.error_code = run.error_code
        decision.retryable = run.retryable
        decision.events = [event.to_dict() for event in run.events]

    def _build_memory_context(self, run: TaskRun) -> dict[str, Any]:
        if not self.memory_service or not run.user_id:
            return {"enabled": False, "selected": [], "short_context": [], "explanations": []}

        self.run_store.record_memory_retrieval_started(run)
        try:
            retrieve = getattr(
                self.memory_service,
                "try_retrieve_for_context_with_explanation",
                self.memory_service.retrieve_for_context_with_explanation,
            )
            selected, explanations = retrieve(
                run.user_id,
                run.content,
            )
            selected_items = [self._memory_to_plan_context(memory) for memory in selected]
            short_context = [
                self._memory_to_short_context(memory)
                for memory in selected[:5]
                if str(getattr(memory, "content", "") or "").strip()
            ]
            memory_context = {
                "enabled": True,
                "selected": selected_items,
                "short_context": short_context,
                "explanations": explanations,
            }
            self.run_store.record_memory_retrieval_completed(run, memory_context)
            return memory_context
        except Exception as exc:
            error_info = classify_exception(
                exc,
                operation="task.memory_context",
                dependency="memory",
            )
            memory_context = {
                "enabled": True,
                "selected": [],
                "short_context": [],
                "explanations": [],
                "error": error_info.message,
                "error_info": error_info.to_dict(),
            }
            self.run_store.record_memory_retrieval_completed(run, memory_context)
            return memory_context

    def _memory_to_plan_context(self, memory: Any) -> dict[str, Any]:
        return {
            "memory_id": getattr(memory, "memory_id", ""),
            "content": getattr(memory, "content", ""),
            "mem_type": getattr(memory, "mem_type", ""),
            "slot": getattr(memory, "slot", ""),
            "score": round(float(getattr(memory, "score", 0.0) or 0.0), 4),
            "similarity": round(float(getattr(memory, "similarity", 0.0) or 0.0), 4),
            "final_score": round(float(getattr(memory, "final_score", 0.0) or 0.0), 4),
            "source": getattr(memory, "source", ""),
            "review_status": getattr(memory, "review_status", ""),
            "is_current": bool(getattr(memory, "is_current", True)),
            "observed_at": getattr(memory, "observed_at", ""),
            "valid_from": getattr(memory, "valid_from", ""),
            "valid_to": getattr(memory, "valid_to", ""),
        }

    def _memory_to_short_context(self, memory: Any) -> str:
        mem_type = str(getattr(memory, "mem_type", "") or "memory")
        slot = str(getattr(memory, "slot", "") or "").strip()
        content = str(getattr(memory, "content", "") or "").strip()
        prefix = f"Memory[{mem_type}:{slot}]" if slot else f"Memory[{mem_type}]"
        return f"{prefix}: {content}"

    def _record_outcome_memory(
        self,
        run: TaskRun,
        result: dict[str, Any],
        executed_steps: list[dict[str, Any]],
        *,
        success: bool,
    ) -> dict[str, Any] | None:
        if not self.memory_service or not run.user_id or not executed_steps:
            return None

        outcome_text, step_id, metadata = self._build_outcome_memory_candidate(run, result, executed_steps, success=success)
        if not outcome_text:
            return None

        self.run_store.record_outcome_memory_started(run)
        try:
            write_outcome = getattr(
                self.memory_service,
                "try_process_task_outcome",
                self.memory_service.process_task_outcome,
            )
            write_result = write_outcome(
                run.user_id,
                outcome_text,
                task_run_id=run.task_run_id,
                step_id=step_id,
                slot=metadata.get("slot", "task_experience"),
                confidence=metadata.get("confidence", 0.62),
                importance=metadata.get("importance", 3.0),
                metadata=metadata,
            )
        except Exception as exc:
            error_info = classify_exception(exc, operation="memory.task_outcome.write")
            write_result = {
                "written": False,
                "reason": error_info.message,
                "error_info": error_info.to_dict(),
            }
        self.run_store.record_outcome_memory_completed(run, write_result)
        if write_result.get("written") and self.maintenance_scheduler is not None:
            try:
                schedule_result = self.maintenance_scheduler.schedule(run.user_id)
                write_result["maintenance"] = {
                    "scheduled": True,
                    "requested_generation": schedule_result.get("requested_generation"),
                }
            except Exception as exc:
                schedule_error = classify_exception(
                    exc,
                    operation="memory.maintenance.schedule",
                )
                write_result["maintenance"] = {
                    "scheduled": False,
                    "error": schedule_error.to_dict(),
                }
        return write_result

    def _build_outcome_memory_candidate(
        self,
        run: TaskRun,
        result: dict[str, Any],
        executed_steps: list[dict[str, Any]],
        *,
        success: bool,
    ) -> tuple[str | None, str | None, dict[str, Any]]:
        tool_names = [str(step.get("tool_name") or "") for step in executed_steps if step.get("tool_name")]
        if not tool_names:
            return None, None, {}

        metadata: dict[str, Any] = {
            "task_run_id": run.task_run_id,
            "task_status": "succeeded" if success else "failed",
            "tool_sequence": ",".join(tool_names),
            "importance": 3.0,
        }
        if success:
            summary = str(result.get("summary") or "").strip()
            content = (
                f"Task experience: for similar task '{run.content}', "
                f"use tools in order: {', '.join(tool_names)}."
            )
            if summary:
                content = f"{content} Outcome summary: {summary[:240]}"
            metadata.update({"slot": "task_workflow", "confidence": 0.62})
            return content, None, metadata

        failed_step = next((step for step in reversed(executed_steps) if not step.get("result", {}).get("success")), executed_steps[-1])
        failed_tool = str(failed_step.get("tool_name") or "")
        error = str(failed_step.get("result", {}).get("error") or result.get("summary") or "").strip()
        content = (
            f"Task experience: tool '{failed_tool}' failed for task '{run.content}'. "
            f"Failure reason: {error[:240]}"
        )
        metadata.update({"slot": "tool_failure", "confidence": 0.58, "failed_tool": failed_tool})
        return content, str(failed_step.get("step_id") or ""), metadata

    def _resolve_step_args(self, tool_args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        return {key: self._resolve_value(value, context) for key, value in tool_args.items()}

    def _resolve_value(self, value: Any, context: dict[str, Any]) -> Any:
        if isinstance(value, str):
            return re.sub(r"\{([a-zA-Z0-9_\.]+)\}", lambda match: str(context.get(match.group(1), match.group(0))), value)
        if isinstance(value, list):
            return [self._resolve_value(item, context) for item in value]
        if isinstance(value, dict):
            return {key: self._resolve_value(item, context) for key, item in value.items()}
        return value

    def _update_context(
        self,
        context: dict[str, Any],
        step_id: str,
        step_result: dict[str, Any],
        output_key: str | None,
        extract_path: str | None,
    ) -> None:
        context[step_id] = step_result
        flattened = self._flatten_result(step_result)
        for key, value in flattened.items():
            context[f"{step_id}.{key}"] = value

        if output_key:
            context[output_key] = self._extract_from_result(step_result, extract_path)

    def _extract_from_result(self, result: dict[str, Any], extract_path: str | None) -> Any:
        if not extract_path:
            return result
        current: Any = result
        for part in extract_path.split("."):
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        return current

    def _flatten_result(self, value: Any, prefix: str = "") -> dict[str, Any]:
        flattened: dict[str, Any] = {}
        if isinstance(value, dict):
            for key, item in value.items():
                nested_prefix = f"{prefix}.{key}" if prefix else key
                flattened.update(self._flatten_result(item, nested_prefix))
        else:
            flattened[prefix] = value
        return flattened

    def _build_summary(self, template: str | None, context: dict[str, Any], executed_steps: list[dict[str, Any]]) -> str:
        if template:
            return self._resolve_value(template, context)
        if not executed_steps:
            return "No steps were executed."
        lines = []
        for step in executed_steps:
            result = step["result"]
            data = result.get("data")
            lines.append(f"{step['step_id']} ({step['tool_name']}): success={result.get('success')} data={data}")
        return "\n".join(lines)
