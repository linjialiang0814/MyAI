from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from typing import Any, Dict, Type
from pydantic import BaseModel, Field

class EmptyArgs(BaseModel):
    pass

class ToolResult(BaseModel):
    """
    工具执行后的结果统一
    """
    success: bool
    data: Any = None
    error: str | None = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


@dataclass(frozen=True)
class ToolPolicy:
    risk_level: str = "safe"
    timeout_seconds: float = 10.0
    retry_count: int = 0
    requires_confirmation: bool = False
    allowed_in_local: bool = True
    allowed_in_hosted: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

class Tool(ABC):
    """
    工具抽象类
    """
    name: str = ""
    description: str = ""
    args: Type[BaseModel] = EmptyArgs
    trigger_words: Dict[str, float] = {}
    negative_triggers: Dict[str, float] = {}
    policy: ToolPolicy = ToolPolicy()

    @property
    def schema(self) -> Dict[str, Any]:
        parameters = self.args.model_json_schema()
        parameters.pop("title", None)
        parameters.pop("$defs", None)
        parameters.pop("definitions", None)

        return{
            "type":"function",
            "function":{
                "name": self.name,
                "description": self.description,
                "parameters": parameters
            }
        }

    def validate_args(self, args: Dict[str, Any] | None) -> BaseModel:
        return self.args.model_validate(args or {})

    def prepare_args(self, args: Dict[str, Any] | None, runtime_context: Dict[str, Any] | None = None) -> Dict[str, Any]:
        return dict(args or {})

    def extract_args(self, content: str) -> Dict[str, Any]:
        return {}

    def policy_for_args(
        self,
        args: Dict[str, Any] | None,
        runtime_context: Dict[str, Any] | None = None,
    ) -> ToolPolicy:
        return self.policy

    @abstractmethod
    def run(self, **kwargs) -> ToolResult:
        pass
    #接收kwargs可以直接对接LLM输出的json

