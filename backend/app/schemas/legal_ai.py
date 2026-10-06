"""Schemas for legal AI (MASTER_PROMPT V5)."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel

HitKind = Literal["case", "document", "media"]


class SearchHitResponse(BaseModel):
    kind: HitKind
    id: UUID
    title: str
    #: A window of the text around the match, not the whole field.
    excerpt: str
    case_id: UUID | None
    case_number: str | None
    #: Higher is a better match. Opaque on purpose: the terms that produced it are
    #: what a lawyer argues with, and hiding them would make it unexplainable.
    score: float


class SearchResponse(BaseModel):
    query: str
    #: The words actually ranked on, after dropping stop words. Echoed so a
    #: surprising result can be traced to the word that caused it.
    terms: list[str]
    total: int
    items: list[SearchHitResponse]


class SummaryResponse(BaseModel):
    kind: HitKind
    id: UUID
    title: str
    #: The source's own sentences, verbatim. Not paraphrased.
    sentences: list[str]
    #: Always `extractive`, and shown on screen: a summary that rewrites is a claim.
    method: str
    terms: list[str]


class ProviderStatusResponse(BaseModel):
    """What a generation backend would need, and which of it is missing.

    The screen shows this instead of a prompt box. Naming the four absences is more
    useful than a disabled field, and it keeps the module honest about the fact
    that nothing here calls a model.
    """

    provider: str | None
    model: str | None
    embeddings: bool
    vector_store: bool
    queue: bool
    available: bool
    missing: list[str]
    app_name: str


__all__ = [
    "HitKind",
    "ProviderStatusResponse",
    "SearchHitResponse",
    "SearchResponse",
    "SummaryResponse",
]
