from datetime import date, datetime
from typing import Literal

from pydantic import UUID4, BaseModel, ConfigDict, Field


class WebsiteEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: UUID4
    visitor_id: UUID4
    kind: Literal["page_view", "phone_click"]
    path: str = Field(min_length=1, max_length=180, pattern=r"^/(?:[a-z0-9/-]*)$")


class WebsiteCounts(BaseModel):
    page_views: int = 0
    estimated_visitors: int = 0
    phone_clicks: int = 0
    consultations: int = 0


class WebsiteDay(WebsiteCounts):
    day: date


class WebsiteMonth(WebsiteCounts):
    month: str


class WebsitePage(BaseModel):
    path: str
    page_views: int
    phone_clicks: int


class WebsiteSummary(BaseModel):
    start: date
    end: date
    timezone: str
    generated_at: datetime
    totals: WebsiteCounts
    daily: list[WebsiteDay]
    monthly: list[WebsiteMonth]
    pages: list[WebsitePage]
    areas: list[WebsitePage]
