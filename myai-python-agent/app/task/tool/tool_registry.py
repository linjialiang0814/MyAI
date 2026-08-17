from typing import Dict, List, Optional

from app.task.tool.tool import Tool


class ToolRegistry:
    """
    工具注册
    """
    def __init__(self):
        self.tools: Dict[str, Tool] = {}

    def register(self, tool: Tool):
        if tool.name in self.tools:
            print(f"Warning: tool {tool.name} already exists, overwriting it.")
        self.tools[tool.name] = tool

    def register_many(self, tools: List[Tool]) -> None:
        for tool in tools:
            self.register(tool)

    def has_tool(self, name: str) -> bool:
        return name in self.tools

    def get_tool(self, name: str) -> Optional[Tool]:
        return self.tools.get(name)

    def list_tools(self) -> List[Tool]:
        return list(self.tools.values())

    def get_all_schemas(self) -> List[dict]:
        """
        直接返回标准的tools列表
        :return:
        """
        return [tool.schema for tool in self.tools.values()]

