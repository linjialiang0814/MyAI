from dataclasses import dataclass

@dataclass
class TaskConfig:
    trigger_threshold: float = 1.0
    min_success_rate: float = 0.3
    max_retries: int = 3
    allow_llm_fallback: bool = True
    llm_timeout_seconds: float = 20.0
    update_trigger_weights: bool = True
    reward_lr: float = 0.05
    min_trigger_weight: float = 0.3
    max_trigger_weight: float = 2.0