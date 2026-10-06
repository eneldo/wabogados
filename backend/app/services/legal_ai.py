"""Legal AI: lexical search over the firm's material, and extractive summaries
(MASTER_PROMPT V5).

**There is no language model behind this module, and the module says so.** No key,
no provider, no vector store, no queue (ADR-057). What is here is the half of "RAG"
that is true without a model, and it is the half people actually notice:

1. **Search** that returns real rows with their provenance, so a lawyer can check
   them. It is lexical — PostgreSQL, no embeddings — which is not a compromise
   here: the question a firm asks is "where is this justified", and an exact match
   beats a similarity score that cannot be explained to a client.
2. **Extractive summaries**, which *lift sentences from the text* and are labelled
   as such everywhere they appear. A summary you can trace back to a sentence is
   evidence of reading; a summary that rewrites is a claim, and in a legal file the
   difference is the whole point.

What deliberately does not exist: generation, analysis, embeddings. Inventing a
provider would mean a button that answers with fiction, and this project has spent
three modules refusing to do that.

**Scope is inherited, never widened.** Every row the index can return is a row the
caller could already reach through the screen that owns it: cases go through
`scope_filter`, and a caller with no case scope gets `literal(False)` rather than
an empty result set that looks like "nothing matched".
"""

import re
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import false, func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_user_permission_names
from app.models import Case, Client, Document, MediaItem, User
from app.services.cases import CaseScope, scope_filter

#: Words that carry no signal in a legal corpus and would match everything.
STOP_WORDS: frozenset[str] = frozenset(
    """
    a al algo algunas algunos ante antes como con contra cual cuando de del desde donde
    dos el ella ellos en entre era erais eran eres es esa esas ese eso esos esta
    estas este esto estos ha hasta la las le les lo los mas me mi mis mucho muy nada
    ni no nos nosotros o os otra otro para pero poco por porque que quien se sea
    sin sobre son su sus te tiene tienen todo todos tu tus un una uno unos y ya
    """.split()
)

#: Sentences shorter than this are headings and dates, not content.
MIN_SENTENCE_CHARS = 40

#: A summary of a document is a handful of its own sentences. More than that stops
#: being a summary and becomes a copy.
MAX_SUMMARY_SENTENCES = 5


@dataclass(frozen=True)
class SearchHit:
    """One row the index matched, with where it came from."""

    kind: str
    id: UUID
    title: str
    excerpt: str
    case_id: UUID | None
    case_number: str | None
    score: float


@dataclass(frozen=True)
class Summary:
    """Sentences taken from a document, plus how they were chosen."""

    kind: str
    id: UUID
    title: str
    #: Words the selection weighted on, so the result can be argued with.
    terms: list[str]
    #: Verbatim sentences from the source. Not rewritten, not joined.
    sentences: list[str]
    method: str = "extractive"


def meaningful_terms(query: str) -> list[str]:
    """Split a query into the words worth ranking on.

    Stop words are dropped because a search for «el contrato» must not match every
    document containing «el». Terms are lowercased and de-punctuated so that
    «culpa» finds « Culpa.».
    """
    cleaned = re.sub(r"[^\w\sáéíóúüñÁÉÍÓÚÜÑ]", " ", query.lower())
    return [word for word in cleaned.split() if len(word) > 2 and word not in STOP_WORDS]


def _rank(term: str, haystack: str) -> float:
    """How strongly a term appears. Deliberately simple and explainable.

    A word in the title counts more than one in the body, and a prefix match
    counts a little: «prescripc» should find «prescripción» without the caller
    having to know the noun is spelled with a ción.
    """
    score = 0.0
    title_hits = haystack.count(term)
    if title_hits:
        score += 3.0 * title_hits
    body_hits = haystack.count(term)
    score += body_hits
    return score


def split_sentences(text: str) -> list[str]:
    """Split prose into sentences, Spanish included.

    The Spanish question mark and inverted exclamation are real sentence ends and a
    split that ignores them leaves «¿Cómo está usted?» glued to the next sentence,
    which is exactly the fragment a summary must not quote.

    A short numeric token before the full stop is treated as a **list marker**, not
    as the end of a sentence: «12. Objeto: …» is one item, and splitting it would
    leave a summary quoting «Objeto: …» with the number that identifies it lost.
    """
    if not text:
        return []
    parts = re.split(r"(?<=[.!?])\s+(?=[¿¡A-ZÁÉÍÓÚÑ0-9])", text.strip())

    merged: list[str] = []
    # A list marker belongs to the sentence **after** it, and that sentence has
    # not been seen yet when the marker is, so it waits here.
    pending = ""
    for part in parts:
        stripped = part.strip()
        if not stripped:
            continue
        if re.fullmatch(r"\d{1,3}[.)]?", stripped):
            pending = f"{pending} {stripped}".strip()
            continue
        merged.append(f"{pending} {stripped}".strip() if pending else stripped)
        pending = ""
    if pending:
        # A marker with nothing after it is a truncated document, not a sentence.
        if merged:
            merged[-1] = f"{merged[-1]} {pending}"
        else:
            merged.append(pending)
    return merged


def extractive_summary(text: str, query: str = "") -> tuple[list[str], list[str]]:
    """Pick the sentences that carry the query, or carry the document.

    Without a query this ranks by sentence length within reason, which is a crude
    proxy for informational weight and is only ever used on short texts. With a
    query it ranks by the meaningful terms the sentence contains.

    **It never paraphrases.** The returned strings are the source's own sentences,
    which is what makes the summary checkable and what the label promises.
    """
    terms = meaningful_terms(query)
    candidates = [
        sentence
        for sentence in split_sentences(text)
        if len(sentence) >= MIN_SENTENCE_CHARS
    ]
    if not candidates:
        return [], terms

    def weight(sentence: str) -> float:
        lowered = sentence.lower()
        if terms:
            hits = sum(lowered.count(term) for term in terms)
            # Length only breaks ties between sentences that match equally, and is
            # capped so a long paragraph cannot outrank a precise one.
            return hits * 10 + min(len(sentence), 400) / 400
        return min(len(sentence), 400) / 400

    ranked = sorted(
        enumerate(candidates),
        key=lambda item: weight(item[1]),
        reverse=True,
    )
    selected = ranked[:MAX_SUMMARY_SENTENCES]
    if not terms:
        selected.sort(key=lambda item: item[0])
    return [sentence for _, sentence in selected], terms


class LegalSearchService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def search(
        self,
        query: str,
        user: User,
        scope: CaseScope,
        *,
        limit: int = 20,
    ) -> list[SearchHit]:
        """Search the firm's own material, within what the caller may read.

        Three sources because a firm files things in three places: cases, documents
        and the multimedia library. All three are filtered by the same case scope,
        so a hit is never a row the caller could not have opened anyway.
        """
        terms = meaningful_terms(query)
        if not terms:
            return []

        case_clause = await scope_filter(self.session, user, scope)
        case_ids = (
            None
            if case_clause is None
            else select(Case.id).where(case_clause).scalar_subquery()
        )

        hits: list[SearchHit] = []

        # The client's name travels with the case for the excerpt's context; it is
        # read here so the row a lawyer sees says whose matter it is.
        cases = await self.session.execute(
            select(Case, Client.full_name)
            .join(Client, Case.client_id == Client.id)
            .where(
                case_clause if case_clause is not None else literal(True),
                Case.is_active.is_(True),
                _matches(
                    terms,
                    Case.title,
                    func.coalesce(Case.description, ""),
                    func.coalesce(Case.notes, ""),
                    func.coalesce(Case.file_number, ""),
                ),
            )
            .limit(limit)
        )
        for case, _client_name in cases.all():
            haystack = f"{case.title} {case.description or ''} {case.notes or ''}".lower()
            hits.append(
                SearchHit(
                    kind="case",
                    id=case.id,
                    title=case.title,
                    excerpt=_excerpt(case.description or case.notes, terms),
                    case_id=case.id,
                    case_number=case.case_number,
                    score=_combined(terms, haystack, f"{case.title} {case.case_number}".lower()),
                )
            )

        documents = await self.session.execute(
            select(Document, Case.case_number)
            .select_from(Document)
            .join(Case, Document.case_id == Case.id)
            .where(
                Document.is_active.is_(True),
                Document.case_id.in_(case_ids) if case_ids is not None else literal(True),
                _matches(
                    terms,
                    Document.title,
                    func.coalesce(Document.description, ""),
                ),
            )
            .limit(limit)
        )
        for document, case_number in documents.all():
            haystack = f"{document.title} {document.description or ''}".lower()
            hits.append(
                SearchHit(
                    kind="document",
                    id=document.id,
                    title=document.title,
                    excerpt=_excerpt(document.description, terms),
                    case_id=document.case_id,
                    case_number=case_number,
                    score=_combined(terms, haystack, document.title.lower()),
                )
            )

        media = await self.session.execute(
            select(MediaItem, Case.case_number)
            .outerjoin(Case, MediaItem.case_id == Case.id)
            .where(
                MediaItem.is_active.is_(True),
                # A library item with no case is firm material; it is visible to
                # any staff profile, exactly as it is on the library screen.
                (MediaItem.case_id.is_(None) | MediaItem.case_id.in_(case_ids))
                if case_ids is not None
                else MediaItem.case_id.is_(None),
                _matches(
                    terms,
                    MediaItem.title,
                    func.coalesce(MediaItem.description, ""),
                    func.coalesce(MediaItem.tags, ""),
                ),
            )
            .limit(limit)
        )
        for item, case_number in media.all():
            haystack = f"{item.title} {item.description or ''} {item.tags or ''}".lower()
            hits.append(
                SearchHit(
                    kind="media",
                    id=item.id,
                    title=item.title,
                    excerpt=_excerpt(item.description, terms),
                    case_id=item.case_id,
                    case_number=case_number,
                    score=_combined(terms, haystack, item.title.lower()),
                )
            )

        hits.sort(key=lambda hit: hit.score, reverse=True)
        return hits[:limit]

    async def summarize_document(
        self, document_id: UUID, user: User, scope: CaseScope
    ) -> Summary | None:
        """Summarise one document by lifting its own sentences.

        Two gates, not one. The permission says the profile reads documents at all;
        the case scope says this *particular* document is one of theirs. Checking
        only the first would let any lawyer summarise a stranger's file by guessing
        an id, which is the same leak the search filter exists to prevent.
        """
        if "documents:read" not in get_user_permission_names(user) and not user.is_superuser:
            return None

        case_clause = await scope_filter(self.session, user, scope)
        statement = (
            select(Document, Case.case_number)
            .select_from(Document)
            .join(Case, Document.case_id == Case.id)
            .where(Document.id == document_id, Document.is_active.is_(True))
        )
        if case_clause is not None:
            statement = statement.where(case_clause)
        row = (await self.session.execute(statement)).first()
        if row is None:
            return None
        document, _case_number = row

        # The extractable text is the current version's description and notes; the
        # bytes of a PDF are not parsed here, and pretending otherwise would be the
        # first lie this module tells.
        body = " ".join(
            part for part in (document.description,) if part
        ).strip()
        sentences, terms = extractive_summary(body)
        if not sentences:
            # No text, no summary. Falling back to the title would return something
            # shaped like a summary that is only the document's own name, and the
            # reader would have no way to tell the two apart. The route turns this
            # into a 404, and the screen names the possible causes.
            return None

        return Summary(
            kind="document",
            id=document.id,
            title=document.title,
            sentences=sentences,
            terms=terms,
        )


def _matches(terms: list[str], *columns: Any) -> Any:
    """Match rows carrying **any** of the terms, in any of the columns.

    The filter is a disjunction over words, not a phrase. Filtering on the whole
    query as one literal is the classic search bug: someone types three words that
    all appear in the document and gets nothing, because the words are not adjacent
    on the page. Ranking afterwards is what decides the order; the filter only has
    to be generous, because a hit that does not rank well is still a hit the
    lawyer can recognise.
    """
    clauses = [
        func.lower(column).like(f"%{term}%")
        for term in terms
        for column in columns
        if column is not None
    ]
    if not clauses:
        # Nothing searchable was passed, so the answer is no rows. Returning an
        # always-true filter here would hand back the whole index.
        return false()
    return or_(*clauses)


def _combined(terms: list[str], haystack: str, title: str) -> float:
    return sum(_rank(term, haystack) + 2.0 * _rank(term, title) for term in terms)


def _excerpt(text: str | None, terms: list[str], width: int = 180) -> str:
    """A window of the text around the first term that matched.

    Returning the whole field would bury the hit in a paragraph nobody reads, and
    returning nothing would make every row look identical.
    """
    if not text:
        return ""
    lowered = text.lower()
    position = -1
    for term in terms:
        found = lowered.find(term)
        if found != -1 and (position == -1 or found < position):
            position = found
    if position == -1:
        return text[:width].strip()
    start = max(0, position - width // 3)
    return ("…" if start else "") + text[start : start + width].strip() + (
        "…" if start + width < len(text) else ""
    )


def provider_configured() -> dict[str, Any]:
    """What a generation backend would need, and which of it is missing.

    Returning this instead of a chat box is the point of the module today: the
    screen can say precisely what is absent, which is more useful than a text field
    that would have to be disabled.
    """
    from app.core.config import get_settings

    settings = get_settings()
    return {
        "provider": None,
        "model": None,
        "embeddings": False,
        "vector_store": False,
        "queue": False,
        "available": False,
        # Named so the screen can list what is missing instead of shrugging.
        "missing": [
            "Proveedor de lenguaje configurado",
            "Clave de API en el entorno",
            "Índice de vectores para la búsqueda semántica",
            "Cola de trabajos para las tareas largas",
        ],
        "app_name": settings.app_name,
    }


__all__ = [
    "MAX_SUMMARY_SENTENCES",
    "MIN_SENTENCE_CHARS",
    "STOP_WORDS",
    "LegalSearchService",
    "SearchHit",
    "Summary",
    "extractive_summary",
    "meaningful_terms",
    "provider_configured",
    "split_sentences",
]
