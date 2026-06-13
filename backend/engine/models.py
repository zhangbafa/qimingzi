from pydantic import BaseModel, Field
from typing import Literal, Optional


class GenerationConfig(BaseModel):
    name_type: Literal["person", "company", "brand", "product"] = "person"
    surname: str = ""
    industry: list[str] = Field(default_factory=list)
    style: list[str] = Field(default_factory=list)
    length: Optional[int] = None
    gender: Literal["M", "F", "N"] = "N"
    exclude_chars: list[str] = Field(default_factory=list)
    count: int = Field(default=10, ge=1, le=50)
    with_ai: bool = True


class DimensionScores(BaseModel):
    meaning: float = 0.0
    tone: float = 0.0
    style: float = 0.0
    readability: float = 0.0
    length: float = 0.0
    repeat: float = 0.0
    ai: float = 0.0


class NameCandidate(BaseModel):
    name: str
    chars: list[str]
    pinyin: list[str]
    score: float
    dimensions: DimensionScores
    meaning: str = ""
    story: str = ""


class GenerateResponse(BaseModel):
    names: list[NameCandidate]
    meta: dict = Field(default_factory=lambda: {
        "total_candidates": 0,
        "generation_ms": 0,
        "ai_ms": 0,
    })
