"""Thought leadership: the legal analyses module (MASTER_PROMPT V5 adjacent).

Three assertions carry this file:

1. **The slug is an address, so a collision is a decision, not a 500.** The
   public site links `/analisis/{slug}`, so the unique constraint is a contract
   the API must express as a 409 with the field named.
2. **Publishing is a deliberate act.** An analysis that is not published, or
   whose `published_at` lies in the future, never reaches the public site —
   drafting in the open would turn the module into a press release nobody
   approved.
3. **The drafting surface is staff-only.** The client role has no `analyses:*`
   permission and must get a 403, not a listing.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from httpx import AsyncClient

ANALYSES = "/api/v1/analyses"
PUBLIC = "/api/v1/public/analyses"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _payload(slug: str, **overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "title": "Prescripción de la acción penal civil",
        "slug": slug,
        "summary": "Cuándo prescribe y qué la interrumpe.",
        "content": "El análisis completo del término prescriptivo y sus causas de interrupción.",
        "author_name": "Oficina WABOGADOS",
        "is_published": False,
    }
    body.update(overrides)
    return body


@pytest.mark.asyncio
async def test_an_administrator_creates_and_lists_an_analysis(
    client: AsyncClient, admin_token: str
) -> None:
    created = await client.post(
        ANALYSES, json=_payload(f"prescripcion-{uuid4()}"), headers=_auth(admin_token)
    )
    assert created.status_code == 201, created.text

    listed = await client.get(ANALYSES, headers=_auth(admin_token))
    assert listed.status_code == 200
    assert any(
        item["title"] == "Prescripción de la acción penal civil"
        for item in listed.json()
    )


@pytest.mark.asyncio
async def test_a_duplicate_slug_is_a_409_with_the_field_named(
    client: AsyncClient, admin_token: str
) -> None:
    slug = f"duplicado-{uuid4()}"
    first = await client.post(ANALYSES, json=_payload(slug), headers=_auth(admin_token))
    assert first.status_code == 201

    second = await client.post(ANALYSES, json=_payload(slug), headers=_auth(admin_token))
    assert second.status_code == 409
    # The uniform error envelope, not a bare 500: the caller must be able to tell
    # it was the slug without opening the server logs.
    assert "slug" in second.text.lower()


@pytest.mark.asyncio
async def test_an_update_cannot_steal_another_analysis_slug(
    client: AsyncClient, admin_token: str
) -> None:
    slug_a, slug_b = f"uno-{uuid4()}", f"dos-{uuid4()}"
    created_a = (
        await client.post(ANALYSES, json=_payload(slug_a), headers=_auth(admin_token))
    ).json()
    await client.post(ANALYSES, json=_payload(slug_b), headers=_auth(admin_token))

    stolen = await client.patch(
        f"{ANALYSES}/{created_a['id']}", json={"slug": slug_b}, headers=_auth(admin_token)
    )
    assert stolen.status_code == 409

    # Its own slug stays legal, so editing other fields is untouched.
    kept = await client.patch(
        f"{ANALYSES}/{created_a['id']}",
        json={"title": "Título corregido"},
        headers=_auth(admin_token),
    )
    assert kept.status_code == 200
    assert kept.json()["title"] == "Título corregido"


@pytest.mark.asyncio
async def test_deactivation_hides_the_analysis_until_include_inactive(
    client: AsyncClient, admin_token: str
) -> None:
    created = await client.post(
        ANALYSES, json=_payload(f"retirado-{uuid4()}"), headers=_auth(admin_token)
    )
    analysis_id = created.json()["id"]

    removed = await client.delete(f"{ANALYSES}/{analysis_id}", headers=_auth(admin_token))
    assert removed.status_code == 200
    assert removed.json()["is_active"] is False

    listed = await client.get(ANALYSES, headers=_auth(admin_token))
    assert not any(item["id"] == analysis_id for item in listed.json())

    inactive = await client.get(
        ANALYSES, params={"include_inactive": "true"}, headers=_auth(admin_token)
    )
    assert any(item["id"] == analysis_id for item in inactive.json())


@pytest.mark.asyncio
async def test_the_public_site_only_shows_published_analyses(
    client: AsyncClient, admin_token: str
) -> None:
    slug = f"publicado-{uuid4()}"
    created = await client.post(
        ANALYSES, json=_payload(slug), headers=_auth(admin_token)
    )
    analysis_id = created.json()["id"]

    public_before = await client.get(PUBLIC)
    assert public_before.status_code == 200
    assert not any(item["slug"] == slug for item in public_before.json()["items"])

    published = await client.patch(
        f"{ANALYSES}/{analysis_id}",
        json={"is_published": True},
        headers=_auth(admin_token),
    )
    assert published.status_code == 200

    public_after = await client.get(PUBLIC)
    assert any(item["slug"] == slug for item in public_after.json()["items"])


@pytest.mark.asyncio
async def test_a_future_publication_date_does_not_publish_early(
    client: AsyncClient, admin_token: str
) -> None:
    slug = f"agendado-{uuid4()}"
    future = (datetime.now(UTC) + timedelta(days=7)).isoformat()
    created = await client.post(
        ANALYSES,
        json=_payload(slug, is_published=True, published_at=future),
        headers=_auth(admin_token),
    )
    assert created.status_code == 201

    detail = await client.get(f"{PUBLIC}/{slug}")
    assert detail.status_code == 404


@pytest.mark.asyncio
async def test_a_client_never_reaches_the_drawing_surface(
    client: AsyncClient, portal_token: str
) -> None:
    refused = await client.post(
        ANALYSES, json=_payload(f"cliente-{uuid4()}"), headers=_auth(portal_token)
    )
    assert refused.status_code == 403

    listing = await client.get(ANALYSES, headers=_auth(portal_token))
    assert listing.status_code == 403


@pytest.mark.asyncio
async def test_an_anonymous_caller_cannot_even_list(
    client: AsyncClient,
) -> None:
    response = await client.get(ANALYSES)
    assert response.status_code == 401
