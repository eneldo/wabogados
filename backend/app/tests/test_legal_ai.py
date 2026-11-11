"""Legal AI (MASTER_PROMPT V5).

The assertions here are about two things that are easy to claim and hard to do:

1. **The index never widens access.** Every hit must be a row the caller could
   already open. A search that returns another client's matter is the worst bug
   this module could have, and it is invisible to a test that only checks "some
   results came back".
2. **The summary does not invent.** It returns the document's own sentences, so
   every one of them must appear verbatim in the source.
"""

from datetime import date
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Case, Client, Document, Lawyer, MediaItem
from app.services.legal_ai import (
    extractive_summary,
    meaningful_terms,
    provider_configured,
    split_sentences,
)

AI = "/api/v1/ai"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# --- text handling --------------------------------------------------------


def test_stop_words_are_dropped_so_a_search_is_not_useless() -> None:
    assert meaningful_terms("el contrato de arrendamiento") == [
        "contrato",
        "arrendamiento",
    ]
    assert meaningful_terms("la responsabilidad") == ["responsabilidad"]
    assert meaningful_terms("el de la y a") == []


def test_sentences_split_on_the_spanish_marks() -> None:
    text = "¿Cómo está usted? Muy bien, gracias. Fin."
    assert split_sentences(text) == ["¿Cómo está usted?", "Muy bien, gracias.", "Fin."]


def test_headings_and_dates_are_not_sentences() -> None:
    text = "Contrato. 12. Objeto: el arrendamiento del inmueble situado en la calle mayor."
    sentences, _ = extractive_summary(text)
    assert sentences == ["12. Objeto: el arrendamiento del inmueble situado en la calle mayor."]


def test_the_summary_returns_the_sources_own_sentences() -> None:
    source = (
        "El arrendatario se obliga a pagar la renta dentro de los primeros cinco "
        "días de cada mes. La falta de pago durante dos meses consecutivos da derecho "
        "a la terminación del contrato. Las partes acuerdan que el aviso se envíe por "
        "correo certificado."
    )
    sentences, terms = extractive_summary(source, "pagar renta mes")

    assert terms == ["pagar", "renta", "mes"]
    assert sentences
    # Verbatim: every returned sentence is a sentence of the source, which is the
    # whole promise of an extractive summary.
    for sentence in sentences:
        assert sentence in source


def test_the_summary_prefers_the_sentences_that_answer_the_query() -> None:
    source = (
        "El inmueble se encuentra ubicado en el barrio norte de la ciudad. "
        "La renta mensual asciende a la suma de dos millones de pesos. "
        "El contrato tiene una duración de un año prorrogable."
    )
    sentences, _ = extractive_summary(source, "renta")

    assert sentences[0] == "La renta mensual asciende a la suma de dos millones de pesos."


def test_an_empty_text_summarises_to_nothing_rather_than_inventing() -> None:
    assert extractive_summary("") == ([], [])


# --- provider -------------------------------------------------------------


def test_the_provider_is_declared_absent_rather_than_assumed() -> None:
    """No key, no provider. The module says so out loud.

    The model name has a default (`gpt-4o-mini`), so it is not counted as
    missing: what the screen owes the operator is the two variables that truly
    have no value, not a padded list.
    """
    status = provider_configured()

    assert status["available"] is False
    assert status["provider"] is None
    assert status["embeddings"] is False
    assert status["vector_store"] is False
    assert len(status["missing"]) == 2
    assert any("AI_PROVIDER" in entry for entry in status["missing"])
    assert any("AI_API_KEY" in entry for entry in status["missing"])


@pytest.mark.asyncio
async def test_the_screen_can_ask_what_is_missing(
    client: AsyncClient, admin_token: str
) -> None:
    response = await client.get(f"{AI}/provider", headers=_auth(admin_token))

    assert response.status_code == 200
    payload = response.json()
    assert payload["available"] is False
    assert any("AI_PROVIDER" in entry for entry in payload["missing"])
    assert any("AI_API_KEY" in entry for entry in payload["missing"])


# --- search ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_finds_a_case_by_its_own_words(
    database_session: AsyncSession,
    client: AsyncClient,
    admin_token: str,
    sample_client: Client,
    sample_lawyer: Lawyer,
) -> None:
    """The term is one this case is given, so the assertion cannot rot."""
    case = Case(
        case_number="WA-2026-000900",
        title="Desahucio por falta de pago",
        description="El arrendatario [\u00bfdej\u00f3] de pagar tres mensualidades.",
        client_id=sample_client.id,
        responsible_lawyer_id=sample_lawyer.id,
        process_type="civil",
        status="abierto",
        opened_at=date(2026, 5, 2),
        is_active=True,
    )
    database_session.add(case)
    await database_session.flush()

    response = await client.get(
        f"{AI}/search", params={"q": "arrendatario dej\u00f3 pagar"}, headers=_auth(admin_token)
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] >= 1
    assert payload["terms"] == ["arrendatario", "dej\u00f3", "pagar"]
    titles = {hit["title"] for hit in payload["items"]}
    assert "Desahucio por falta de pago" in titles


@pytest.mark.asyncio
async def test_search_reads_cases_documents_and_the_library(
    database_session: AsyncSession,
    client: AsyncClient,
    admin_token: str,
    sample_case: Case,
    sample_client: Client,
) -> None:
    """A firm files things in three places, and the index covers all three."""
    database_session.add(
        Case(
            case_number="WA-2026-000901",
            title="Desahucio por arrendamiento impagado",
            description="Tres mensualidades de arrendamiento sin pagar.",
            client_id=sample_client.id,
            process_type="civil",
            status="abierto",
            opened_at=date(2026, 5, 2),
            is_active=True,
        )
    )
    database_session.add(
        Document(
            case_id=sample_case.id,
            document_type="contrato",
            title="Contrato de arrendamiento del inmueble",
            description="Arrendamiento del local comercial por dos años.",
        )
    )
    # The library item belongs to no case: firm material, visible to any staff
    # profile, exactly as it is on the library screen.
    database_session.add(
        MediaItem(
            title="Grabación de la inspección",
            description="Arrendamiento dialogado con el arrendatario.",
            kind="video",
        )
    )
    await database_session.flush()

    response = await client.get(
        f"{AI}/search", params={"q": "arrendamiento"}, headers=_auth(admin_token)
    )

    assert response.status_code == 200
    kinds = {hit["kind"] for hit in response.json()["items"]}
    assert {"case", "document", "media"} <= kinds


@pytest.mark.asyncio
async def test_the_index_never_returns_a_case_the_caller_cannot_open(
    database_session: AsyncSession,
    client: AsyncClient,
    staff_token: str,
    sample_case: Case,
) -> None:
    """The failure this module could have worst: another matter, by relevance.

    The lawyer here is a different person from the one responsible for
    `sample_case` and is assigned to nothing, so their scope is `assigned` and the
    case is not theirs. A search that reached it would hand over a stranger's file
    — and the response would look entirely normal.
    """
    database_session.add(
        Document(
            case_id=sample_case.id,
            document_type="contrato",
            title="Contrato de arrendamiento del inmueble ajeno",
            description="Arrendamiento del local de un tercero.",
        )
    )
    await database_session.flush()

    response = await client.get(
        f"{AI}/search", params={"q": "arrendamiento"}, headers=_auth(staff_token)
    )

    assert response.status_code == 200
    titles = {hit["title"] for hit in response.json()["items"]}
    assert "Contrato de arrendamiento del inmueble ajeno" not in titles


@pytest.mark.asyncio
async def test_a_document_out_of_scope_cannot_be_summarised_by_guessing_its_id(
    database_session: AsyncSession,
    client: AsyncClient,
    staff_token: str,
    sample_case: Case,
) -> None:
    """Summarising must respect the same scope the search does.

    The endpoint takes an id, so it is the place where a lawyer could reach a file
    they have no case for. The answer has to be the same 404 as an id that does not
    exist: distinguishing them would confirm the document is real.
    """
    document = Document(
        case_id=sample_case.id,
        document_type="contrato",
        title="Contrato ajeno",
        description="Este documento pertenece a otro expediente.",
    )
    database_session.add(document)
    await database_session.flush()

    response = await client.get(
        f"{AI}/documents/{document.id}/summary", headers=_auth(staff_token)
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_a_document_with_no_text_gets_no_summary(
    database_session: AsyncSession,
    client: AsyncClient,
    admin_token: str,
    sample_case: Case,
) -> None:
    """A title is not a summary, and returning it would look like one.

    Falling back to the document name would answer with something shaped like an
    extractive summary that contains no sentence from the file. The screen would
    show a heading and an empty list, and nothing on it would say why.
    """
    document = Document(
        case_id=sample_case.id,
        document_type="contrato",
        title="Contrato de servicios profesionales",
    )
    database_session.add(document)
    await database_session.flush()

    response = await client.get(
        f"{AI}/documents/{document.id}/summary", headers=_auth(admin_token)
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_the_summary_quotes_the_document_and_says_so(
    database_session: AsyncSession,
    client: AsyncClient,
    admin_token: str,
    sample_case: Case,
) -> None:
    document = Document(
        case_id=sample_case.id,
        document_type="sentencia",
        title="Sentencia de primera instancia",
        description=(
            "El juzgado condemna al demandado al pago de la suma adeudada. "
            "Las costas se imponen a la parte vencida. "
            "Contra esta sentencia cabe recurso de apelación."
        ),
    )
    database_session.add(document)
    await database_session.flush()

    response = await client.get(
        f"{AI}/documents/{document.id}/summary", headers=_auth(admin_token)
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["method"] == "extractive"
    assert payload["sentences"] == [
        "El juzgado condemna al demandado al pago de la suma adeudada.",
        "Las costas se imponen a la parte vencida.",
        "Contra esta sentencia cabe recurso de apelación.",
    ]


@pytest.mark.asyncio
async def test_a_client_never_reaches_the_index(
    client: AsyncClient, portal_token: str
) -> None:
    """Relevance search over the whole firm would hand a client the whole firm."""
    assert (
        await client.get(f"{AI}/search?q=arrendamiento", headers=_auth(portal_token))
    ).status_code == 403
    assert (await client.get(f"{AI}/provider", headers=_auth(portal_token))).status_code == 403
    assert (await client.get(f"{AI}/search?q=arrendamiento")).status_code == 401


@pytest.mark.asyncio
async def test_a_query_of_only_stop_words_returns_nothing_rather_than_everything(
    client: AsyncClient, admin_token: str
) -> None:
    """Otherwise «el» matches every row and the screen looks broken."""
    response = await client.get(
        f"{AI}/search", params={"q": "el de la"}, headers=_auth(admin_token)
    )

    assert response.status_code == 200
    assert response.json()["total"] == 0
    assert response.json()["terms"] == []


@pytest.mark.asyncio
async def test_a_query_too_short_is_refused(
    client: AsyncClient, admin_token: str
) -> None:
    response = await client.get(f"{AI}/search", params={"q": "a"}, headers=_auth(admin_token))

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_the_summary_of_an_unknown_document_is_a_404(
    client: AsyncClient, admin_token: str
) -> None:
    response = await client.get(
        f"{AI}/documents/{uuid4()}/summary", headers=_auth(admin_token)
    )

    assert response.status_code == 404


# --- generation ------------------------------------------------------------


class _NoProvider:
    """Settings shape with nothing configured, so the contract is env-proof."""

    ai_provider = None
    ai_api_key = None
    ai_model = None
    ai_max_tokens = 800


@pytest.mark.asyncio
async def test_generation_without_a_provider_is_a_503(
    client: AsyncClient, admin_token: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No provider, no draft: the endpoint refuses instead of answering fiction."""
    monkeypatch.setattr("app.core.config.get_settings", lambda: _NoProvider())

    response = await client.post(
        f"{AI}/generate",
        json={"prompt": "Redacta el hecho 1 de una contestación"},
        headers=_auth(admin_token),
    )

    assert response.status_code == 503


@pytest.mark.asyncio
async def test_generation_returns_the_draft_and_marks_it_for_review(
    client: AsyncClient, admin_token: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_draft(prompt: str, context: str = "") -> str:
        assert prompt
        return "BORRADOR REVISABLE"

    monkeypatch.setattr("app.api.v1.legal_ai.generate_draft", fake_draft)

    response = await client.post(
        f"{AI}/generate",
        json={"prompt": "Redacta el hecho 1", "context": "Hechos del expediente"},
        headers=_auth(admin_token),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["draft"] == "BORRADOR REVISABLE"
    # The contract of the route: a draft is raw material for a lawyer, and the
    # response says so in the same breath it carries the text.
    assert payload["requires_review"] is True


@pytest.mark.asyncio
async def test_a_provider_failure_never_echoes_the_provider_message(
    client: AsyncClient, admin_token: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def broken_draft(prompt: str, context: str = "") -> str:
        # A plain exception, not a RuntimeError: the route maps RuntimeError to
        # 503 (nothing configured) and any other failure to 502 (provider broke).
        raise ValueError("HTTP 429 quota exceeded for key sk-abc-secret")

    monkeypatch.setattr("app.api.v1.legal_ai.generate_draft", broken_draft)

    response = await client.post(
        f"{AI}/generate",
        json={"prompt": "Redacta el hecho 1"},
        headers=_auth(admin_token),
    )

    assert response.status_code == 502
    assert "sk-abc-secret" not in response.text
    # The uniform error envelope keeps a human message, never the provider's.
    assert "proveedor" in response.text.lower()


@pytest.mark.asyncio
async def test_generation_is_refused_without_the_ai_permission(
    client: AsyncClient, portal_token: str
) -> None:
    response = await client.post(
        f"{AI}/generate",
        json={"prompt": "Redacta el hecho 1"},
        headers=_auth(portal_token),
    )

    assert response.status_code == 403
