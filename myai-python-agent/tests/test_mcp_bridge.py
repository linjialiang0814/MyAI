from pathlib import Path
import os
import shutil
import unittest
from unittest.mock import patch

from app.runtime.error_model import ErrorCode
from app.task.mcp import GitReadOnlyMCPClient, MCPServerConfig, MCPToolDescriptor, MCPToolRegistryLoader, MockMCPClient, ReadOnlyFilesystemMCPClient
from app.task.tool.tool_registry import ToolRegistry
from app.task.plan.executor import ToolExecutor
from app.task.plan.planner import ToolPlan, ToolStep
from app.task.config.task_config import TaskConfig
from app.task.service.task_service import TaskService
from app.task.stats.statistics import StatsManager
from app.task.mcp.policy import map_mcp_tool_policy


class FixedMCPPlanner:
    def plan(self, content: str, short_context: list[str] | None = None) -> ToolPlan:
        return ToolPlan(
            need_tool=True,
            source="test",
            steps=[
                ToolStep(
                    step_id="step1",
                    description="Call MCP echo.",
                    tool_name="mcp__mock_server__echo_text",
                    tool_args={"text": "hello timeline"},
                )
            ],
        )


class RaisingOnceMCPClient(MockMCPClient):
    """Exercise the adapter's exception boundary instead of MockMCPClient's payload path."""

    def __init__(self, descriptor: MCPToolDescriptor) -> None:
        super().__init__([descriptor])
        self.attempts = 0

    def call_tool(self, server_id: str, tool_name: str, arguments: dict) -> dict:
        self.attempts += 1
        self.calls.append(
            {
                "server_id": server_id,
                "tool_name": tool_name,
                "arguments": dict(arguments),
            }
        )
        if self.attempts == 1:
            raise ConnectionError("offline")
        return {"success": True, "data": {"echo": arguments["text"]}, "metadata": {"mock": True}}


class MCPBridgeTest(unittest.TestCase):
    def test_filesystem_connector_is_disabled_by_default_and_requires_explicit_opt_in(self):
        from app.task.service.prepare import _filesystem_mcp_enabled

        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(_filesystem_mcp_enabled())
        with patch.dict(os.environ, {"MYAI_MCP_FILESYSTEM_ENABLED": "true"}, clear=True):
            self.assertTrue(_filesystem_mcp_enabled())

    def test_filesystem_connector_requires_explicit_roots_when_enabled(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "MYAI_MCP_FILESYSTEM_ROOTS is required"):
                ReadOnlyFilesystemMCPClient.from_env()

    def test_mcp_descriptor_registers_as_tool_with_schema_and_policy(self):
        descriptor = MCPToolDescriptor(
            server_id="mock-server",
            name="echo_text",
            description="Echo input text.",
            input_schema={
                "type": "object",
                "properties": {"text": {"type": "string", "description": "Text to echo"}},
                "required": ["text"],
            },
            risk_level="safe",
            timeout_seconds=3.0,
        )
        client = MockMCPClient([descriptor])
        loader = MCPToolRegistryLoader([MCPServerConfig(server_id="mock-server", name="Mock")], client)
        registry = ToolRegistry()

        tools = loader.register_into(registry)

        self.assertEqual(len(tools), 1)
        tool = registry.get_tool("mcp__mock_server__echo_text")
        self.assertIsNotNone(tool)
        self.assertEqual(tool.name, "mcp__mock_server__echo_text")
        self.assertEqual(tool.schema["function"]["parameters"]["required"], ["text"])
        self.assertEqual(tool.policy.risk_level, "safe")
        self.assertEqual(tool.policy.timeout_seconds, 3.0)

    def test_mcp_tool_executes_through_existing_tool_executor(self):
        descriptor = MCPToolDescriptor(
            server_id="mock-server",
            name="echo_text",
            description="Echo input text.",
            input_schema={
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
        )
        client = MockMCPClient([descriptor])
        client.register_handler("mock-server", "echo_text", lambda args: {"echo": args["text"]})
        registry = ToolRegistry()
        MCPToolRegistryLoader([MCPServerConfig(server_id="mock-server", name="Mock")], client).register_into(registry)

        result, latency_ms = ToolExecutor(registry).execute("mcp__mock_server__echo_text", {"text": "hello mcp"})

        self.assertTrue(result.success)
        self.assertEqual(result.data["echo"], "hello mcp")
        self.assertGreaterEqual(latency_ms, 0)
        self.assertEqual(result.metadata["tool_source"], "mcp")
        self.assertEqual(result.metadata["mcp_server_id"], "mock-server")
        self.assertEqual(result.metadata["mcp_tool_name"], "echo_text")
        self.assertEqual(result.metadata["mcp_call_status"], "completed")
        self.assertIn("mcp_call_started_at", result.metadata)
        self.assertIn("mcp_call_finished_at", result.metadata)
        self.assertGreaterEqual(result.metadata["mcp_call_latency_ms"], 0)
        self.assertEqual(client.calls[0]["arguments"], {"text": "hello mcp"})

    def test_task_runtime_records_mcp_call_events(self):
        descriptor = MCPToolDescriptor(
            server_id="mock-server",
            name="echo_text",
            description="Echo input text.",
            input_schema={
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
        )
        client = MockMCPClient([descriptor])
        client.register_handler("mock-server", "echo_text", lambda args: {"echo": args["text"]})
        registry = ToolRegistry()
        MCPToolRegistryLoader([MCPServerConfig(server_id="mock-server", name="Mock")], client).register_into(registry)
        service = TaskService(
            rec_planner=FixedMCPPlanner(),
            task_executor=ToolExecutor(registry),
            stats=StatsManager(registry=registry, config=TaskConfig()),
        )

        decision = service.handle_task("call mcp echo", user_id="u-mcp-trace")
        run = service.get_run(decision.task_run_id)

        self.assertTrue(decision.success)
        event_types = [event["type"] for event in run["events"]]
        self.assertIn("task.mcp_call.completed", event_types)
        mcp_event = next(event for event in run["events"] if event["type"] == "task.mcp_call.completed")
        self.assertEqual(mcp_event["metadata"]["server_id"], "mock-server")
        self.assertEqual(mcp_event["metadata"]["tool_name"], "echo_text")
        self.assertEqual(mcp_event["metadata"]["registry_name"], "mcp__mock_server__echo_text")
        self.assertEqual(mcp_event["metadata"]["call_status"], "completed")
        self.assertGreaterEqual(mcp_event["metadata"]["call_latency_ms"], 0)
        self.assertIn("task.mcp_call.completed", [event["type"] for event in run["steps"][0]["events"]])

    def test_mcp_tool_validation_failure_uses_existing_executor_path(self):
        descriptor = MCPToolDescriptor(
            server_id="mock-server",
            name="requires_text",
            description="Require text.",
            input_schema={
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
        )
        client = MockMCPClient([descriptor])
        registry = ToolRegistry()
        MCPToolRegistryLoader([MCPServerConfig(server_id="mock-server", name="Mock")], client).register_into(registry)

        result, _ = ToolExecutor(registry).execute("mcp__mock_server__requires_text", {})

        self.assertFalse(result.success)
        self.assertEqual(result.error, "The request contains an invalid value.")
        self.assertEqual(result.metadata["error_info"]["code"], ErrorCode.INVALID_ARGUMENT.value)
        self.assertEqual(client.calls, [])

    def test_mcp_connection_exception_preserves_typed_error_and_retries(self):
        descriptor = MCPToolDescriptor(
            server_id="mock-server",
            name="flaky_echo",
            description="Fail once, then echo.",
            input_schema={
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
            retry_count=1,
        )
        client = RaisingOnceMCPClient(descriptor)
        registry = ToolRegistry()
        MCPToolRegistryLoader(
            [MCPServerConfig(server_id="mock-server", name="Mock")],
            client,
        ).register_into(registry)

        result, _ = ToolExecutor(registry, sleep_fn=lambda _: None).execute(
            "mcp__mock_server__flaky_echo",
            {"text": "hello"},
        )

        self.assertTrue(result.success)
        self.assertEqual(result.data["echo"], "hello")
        self.assertEqual(client.attempts, 2)
        self.assertEqual(result.metadata["recovery_status"], "succeeded_after_retry")
        self.assertEqual(
            result.metadata["error_infos"][0]["code"],
            ErrorCode.DEPENDENCY_UNAVAILABLE.value,
        )

    def test_mcp_permission_required_policy_blocks_before_execution(self):
        descriptor = MCPToolDescriptor(
            server_id="mock-server",
            name="write_file",
            description="Write a file.",
            input_schema={
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
            risk_level="filesystem/write",
            requires_confirmation=True,
        )
        client = MockMCPClient([descriptor])
        client.register_handler("mock-server", "write_file", lambda args: {"written": args["path"]})
        registry = ToolRegistry()
        MCPToolRegistryLoader([MCPServerConfig(server_id="mock-server", name="Mock")], client).register_into(registry)

        blocked, _ = ToolExecutor(registry).execute("mcp__mock_server__write_file", {"path": "notes.txt"})
        allowed, _ = ToolExecutor(registry).execute(
            "mcp__mock_server__write_file",
            {"path": "notes.txt"},
            runtime_context={"permission_confirmed": True},
        )

        self.assertFalse(blocked.success)
        self.assertTrue(blocked.metadata["permission_required"])
        self.assertEqual(blocked.metadata["policy_decision"], "permission_required")
        self.assertEqual(client.calls, [{"server_id": "mock-server", "tool_name": "write_file", "arguments": {"path": "notes.txt"}}])
        self.assertTrue(allowed.success)
        self.assertEqual(allowed.data["written"], "notes.txt")

    def test_disabled_mcp_server_is_not_registered(self):
        descriptor = MCPToolDescriptor(
            server_id="disabled-server",
            name="echo",
            description="Echo.",
            input_schema={"type": "object", "properties": {}, "required": []},
        )
        registry = ToolRegistry()
        client = MockMCPClient([descriptor])

        tools = MCPToolRegistryLoader(
            [MCPServerConfig(server_id="disabled-server", name="Disabled", enabled=False)],
            client,
        ).register_into(registry)

        self.assertEqual(tools, [])
        self.assertFalse(registry.has_tool("mcp__disabled_server__echo"))

    def test_task_service_inspection_lists_mcp_tool_metadata(self):
        descriptor = MCPToolDescriptor(
            server_id="mock-server",
            name="search_docs",
            description="Search docs.",
            input_schema={
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
            risk_level="network",
            requires_confirmation=False,
        )
        registry = ToolRegistry()
        client = MockMCPClient([descriptor])
        MCPToolRegistryLoader([MCPServerConfig(server_id="mock-server", name="Mock")], client).register_into(registry)
        service = TaskService(
            rec_planner=object(),
            task_executor=ToolExecutor(registry),
            stats=StatsManager(registry=registry, config=TaskConfig()),
        )

        tools = service.list_tools()

        self.assertEqual(len(tools), 1)
        tool = tools[0]
        self.assertEqual(tool["name"], "mcp__mock_server__search_docs")
        self.assertEqual(tool["source"], "mcp")
        self.assertEqual(tool["server_id"], "mock-server")
        self.assertEqual(tool["external_tool_name"], "search_docs")
        self.assertEqual(tool["policy"]["risk_level"], "network")
        self.assertEqual(tool["required"], ["query"])
        self.assertEqual(tool["policy_metadata"]["policy_source"], "mcp_metadata")

    def test_mcp_policy_mapping_uses_read_only_hint(self):
        descriptor = MCPToolDescriptor(
            server_id="mock-server",
            name="read_file",
            description="Read file.",
            annotations={"readOnlyHint": True},
        )

        policy = map_mcp_tool_policy(descriptor)

        self.assertEqual(policy["risk_level"], "filesystem/read")
        self.assertFalse(policy["requires_confirmation"])
        self.assertTrue(policy["allowed_in_hosted"])
        self.assertIn("read-only", policy["policy_reason"])

    def test_mcp_policy_mapping_requires_confirmation_for_open_world_network(self):
        descriptor = MCPToolDescriptor(
            server_id="mock-server",
            name="web_lookup",
            description="Lookup web.",
            annotations={"openWorldHint": True, "timeoutSeconds": 4, "retryCount": 2},
        )

        policy = map_mcp_tool_policy(descriptor)

        self.assertEqual(policy["risk_level"], "network")
        self.assertTrue(policy["requires_confirmation"])
        self.assertEqual(policy["timeout_seconds"], 4.0)
        self.assertEqual(policy["retry_count"], 2)

    def test_mcp_policy_mapping_blocks_hosted_and_disables_retry_for_destructive(self):
        descriptor = MCPToolDescriptor(
            server_id="mock-server",
            name="delete_file",
            description="Delete file.",
            retry_count=3,
            annotations={"destructiveHint": True},
        )

        policy = map_mcp_tool_policy(descriptor)

        self.assertEqual(policy["risk_level"], "destructive")
        self.assertTrue(policy["requires_confirmation"])
        self.assertFalse(policy["allowed_in_hosted"])
        self.assertEqual(policy["retry_count"], 0)

    def test_mcp_policy_mapping_unknown_risk_fails_conservative(self):
        descriptor = MCPToolDescriptor(
            server_id="mock-server",
            name="mystery",
            description="Unknown capability.",
            risk_level="",
        )

        policy = map_mcp_tool_policy(descriptor)

        self.assertEqual(policy["risk_level"], "unknown")
        self.assertTrue(policy["requires_confirmation"])

    def test_mcp_loader_applies_server_confirmation_default(self):
        descriptor = MCPToolDescriptor(
            server_id="mock-server",
            name="server_sensitive",
            description="Server default sensitive.",
            input_schema={"type": "object", "properties": {}, "required": []},
            risk_level="safe",
        )
        registry = ToolRegistry()
        client = MockMCPClient([descriptor])

        MCPToolRegistryLoader(
            [MCPServerConfig(server_id="mock-server", name="Mock", requires_confirmation=True)],
            client,
        ).register_into(registry)
        tool = registry.get_tool("mcp__mock_server__server_sensitive")

        self.assertIsNotNone(tool)
        self.assertTrue(tool.policy.requires_confirmation)

    def test_readonly_filesystem_connector_lists_reads_and_searches_allowed_root(self):
        root = Path.cwd() / ".test-mcp-fs-root"
        shutil.rmtree(root, ignore_errors=True)
        try:
            root.mkdir()
            (root / "notes").mkdir()
            (root / "notes" / "mcp_plan.txt").write_text("filesystem connector plan", encoding="utf-8")
            client = ReadOnlyFilesystemMCPClient({"workspace": root})
            registry = ToolRegistry()

            MCPToolRegistryLoader(
                [MCPServerConfig(server_id=client.server_id, name="Filesystem Read-Only", risk_level="filesystem/read")],
                client,
            ).register_into(registry)
            executor = ToolExecutor(registry)

            listed, _ = executor.execute("mcp__filesystem_readonly__list_files", {"path": "notes"})
            read, _ = executor.execute("mcp__filesystem_readonly__read_text", {"path": "notes/mcp_plan.txt"})
            searched, _ = executor.execute("mcp__filesystem_readonly__search_names", {"query": "mcp"})

            self.assertTrue(listed.success)
            self.assertEqual(listed.data["entries"][0]["name"], "mcp_plan.txt")
            self.assertTrue(read.success)
            self.assertEqual(read.data["content"], "filesystem connector plan")
            self.assertTrue(searched.success)
            self.assertEqual(searched.data["matches"][0]["path"], "notes/mcp_plan.txt")
            self.assertEqual(read.metadata["tool_source"], "mcp")
            self.assertEqual(read.metadata["connector"], "filesystem_readonly")
            inspected = client.inspect_connector()
            self.assertTrue(inspected["enabled"])
            self.assertTrue(inspected["health"]["ok"])
            self.assertEqual(inspected["settings"]["roots"][0]["name"], "workspace")
            self.assertTrue(inspected["settings"]["roots"][0]["readable"])
            self.assertEqual(inspected["risk_summary"]["risk_level"], "filesystem/read")
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_readonly_filesystem_connector_uses_first_custom_env_root_by_default(self):
        root = Path.cwd() / ".test-mcp-fs-custom-root"
        shutil.rmtree(root, ignore_errors=True)
        try:
            root.mkdir()
            (root / "note.txt").write_text("custom root", encoding="utf-8")
            with patch.dict(os.environ, {"MYAI_MCP_FILESYSTEM_ROOTS": str(root)}, clear=True):
                client = ReadOnlyFilesystemMCPClient.from_env()

            descriptor = next(tool for tool in client.list_tools() if tool.name == "read_text")
            root_schema = descriptor.input_schema["properties"]["root"]
            result = client.call_tool(client.server_id, "read_text", {"path": "note.txt"})

            self.assertEqual(root_schema["default"], "root1")
            self.assertEqual(root_schema["enum"], ["root1"])
            self.assertTrue(result["success"])
            self.assertEqual(result["data"]["root"], "root1")
            self.assertEqual(result["data"]["content"], "custom root")
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_readonly_filesystem_connector_rejects_path_escape(self):
        root = Path.cwd() / ".test-mcp-fs-escape-root"
        shutil.rmtree(root, ignore_errors=True)
        try:
            root.mkdir()
            client = ReadOnlyFilesystemMCPClient({"workspace": root})
            registry = ToolRegistry()

            MCPToolRegistryLoader(
                [MCPServerConfig(server_id=client.server_id, name="Filesystem Read-Only", risk_level="filesystem/read")],
                client,
            ).register_into(registry)
            result, _ = ToolExecutor(registry).execute("mcp__filesystem_readonly__read_text", {"path": "../outside.txt"})

            self.assertFalse(result.success)
            self.assertEqual(result.metadata["error_category"], "path_outside_allowed_roots")
            self.assertEqual(result.metadata["mcp_call_status"], "failed")
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_readonly_filesystem_connector_hides_and_rejects_sensitive_paths(self):
        root = Path.cwd() / ".test-mcp-fs-sensitive-root"
        shutil.rmtree(root, ignore_errors=True)
        try:
            root.mkdir()
            (root / "safe.txt").write_text("safe content", encoding="utf-8")
            (root / ".env").write_text("ARK_API_KEY=super-secret", encoding="utf-8")
            (root / "prod.env").write_text("DB_PASSWORD=super-secret", encoding="utf-8")
            (root / "client.pem").write_text("private key", encoding="utf-8")
            (root / "id_rsa").write_text("private key", encoding="utf-8")
            (root / ".hidden").mkdir()
            (root / ".hidden" / "notes.txt").write_text("hidden content", encoding="utf-8")
            client = ReadOnlyFilesystemMCPClient({"workspace": root})

            listed = client.call_tool(client.server_id, "list_files", {"path": "."})
            searched = client.call_tool(client.server_id, "search_names", {"query": "env"})
            hidden_search = client.call_tool(client.server_id, "search_names", {"query": "notes"})
            safe_read = client.call_tool(client.server_id, "read_text", {"path": "safe.txt"})

            self.assertTrue(listed["success"])
            self.assertEqual([entry["name"] for entry in listed["data"]["entries"]], ["safe.txt"])
            self.assertTrue(searched["success"])
            self.assertEqual(searched["data"]["matches"], [])
            self.assertTrue(hidden_search["success"])
            self.assertEqual(hidden_search["data"]["matches"], [])
            self.assertTrue(safe_read["success"])
            sensitive_paths = [".env", "prod.env", "client.pem", "id_rsa", ".hidden/notes.txt"]
            for sensitive_path in sensitive_paths:
                denied = client.call_tool(client.server_id, "read_text", {"path": sensitive_path})
                self.assertFalse(denied["success"], sensitive_path)
                self.assertEqual(denied["metadata"]["error_category"], "sensitive_path")
                self.assertNotIn("super-secret", denied.get("error", ""))
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_git_readonly_connector_reports_status_and_log(self):
        client = GitReadOnlyMCPClient(Path.cwd().parent)
        registry = ToolRegistry()

        MCPToolRegistryLoader(
            [MCPServerConfig(server_id=client.server_id, name="Git Read-Only", risk_level="filesystem/read")],
            client,
        ).register_into(registry)
        executor = ToolExecutor(registry)

        status, _ = executor.execute("mcp__git_readonly__status", {})
        log, _ = executor.execute("mcp__git_readonly__log", {"limit": 3})
        inspected = client.inspect_connector()

        self.assertTrue(inspected["enabled"])
        self.assertTrue(inspected["health"]["ok"])
        self.assertTrue(status.success)
        self.assertIn("status", status.data)
        self.assertEqual(status.metadata["connector"], "git_readonly")
        self.assertTrue(log.success)
        self.assertLessEqual(log.data["limit"], 3)
        self.assertEqual(log.metadata["tool_source"], "mcp")


if __name__ == "__main__":
    unittest.main()
