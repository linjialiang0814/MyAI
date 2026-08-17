from enum import Enum

class MemoryType(str, Enum):
    PREFERENCE = "preference"
    FACT = "fact"
    DECISION = "decision"
    OPINION = "opinion"
    GENERAL = "general"

class MemoryStatus(str, Enum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    DELETED = "deleted"



