from typing import Optional
from enum import Enum
from pydantic import BaseModel, Field


class SceneType(str, Enum):
    FAMILY = "family"
    FRIENDS = "friends"
    COUPLE = "couple"
    SOLO = "solo"


class UserIntent(BaseModel):
    """从自然语言解析出的用户意图"""

    scene_type: SceneType = SceneType.FRIENDS
    city: str = "杭州"
    group_size: int = 2
    duration_hours: float = 4.0
    budget_per_person: Optional[int] = None
    child_age: Optional[int] = None
    dietary_requirements: Optional[list[str]] = Field(default_factory=list)
    interests: Optional[list[str]] = Field(default_factory=list)
    start_time: str = "14:00"
    special_requests: Optional[list[str]] = Field(default_factory=list)
    location: Optional[str] = None
    raw_input: str = ""
