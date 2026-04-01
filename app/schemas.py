from typing import Literal

from pydantic import BaseModel, Field

DOMAINS = ["videos", "music", "podcasts", "movies", "news"]
FEEDBACK_ACTIONS = ["like", "dislike", "save", "hide", "view"]


class ProfilePayload(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    interests: list[str] = Field(default_factory=list, max_length=25)
    demand_text: str = Field(default="", max_length=1200)
    languages: list[str] = Field(default_factory=lambda: ["en"], max_length=5)
    domain_weights: dict[str, int]


class FeedbackPayload(BaseModel):
    content_id: str
    action: Literal["like", "dislike", "save", "hide", "view"]


class RecommendationItem(BaseModel):
    id: str
    domain: str
    title: str
    description: str
    tags: list[str]
    language: str
    duration_minutes: int
    source: str
    url: str
    creator: str
    published_at: str
    popularity: float
    score: float
    reason: str
    saved: bool = False
