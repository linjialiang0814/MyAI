import platform
import os
import psutil
from pydantic import BaseModel
from app.task.tool.tool import Tool, ToolPolicy, ToolResult


class SystemInfoArgs(BaseModel):
    pass


class SystemInfoTool(Tool):
    name = "system_info"
    description = "Get current runtime system information such as OS, CPU and memory."
    args = SystemInfoArgs
    policy = ToolPolicy(risk_level="safe", timeout_seconds=5.0)
    trigger_words = {
        "system": 1.0,
        "cpu": 0.8,
        "memory": 0.8,
        "ram": 0.8,
        "系统": 1.0,
        "系统信息": 1.2,
        "内存": 0.9,
        "cpu占用": 0.9,
    }

    def run(self, **kwargs):
        info = {
            "os": platform.system(),
            "os_version": platform.version(),
            "machine": platform.machine(),
            "python_version": platform.python_version(),
            "cpu_count": os.cpu_count(),
            "cpu_percent": psutil.cpu_percent(interval=0.1),
            "memory_total_gb": round(psutil.virtual_memory().total / (1024**3), 2),
            "memory_used_gb": round(psutil.virtual_memory().used / (1024**3), 2),
            "memory_percent": psutil.virtual_memory().percent,
        }
        return ToolResult(success=True, data=info)

#需求分析 功能描述 知识点 接口部署
#ppt按照 软件 去做 论文按照软件写
