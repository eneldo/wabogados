"""Tests for the multimedia derivative foundation.

ADR-055 left four things to the library: transcoding, thumbnails, measured
duration and large-file processing. None of them existed, and all four need the
same two things first: somewhere to put the output, and somewhere to put the
pending work. These tests cover those two, because they are what everything else
will stand on.

The key layout is asserted rather than assumed: a derivative that lands in the
same directory as its original is the kind of mistake that is invisible in a
listing and obvious the first time somebody deletes the wrong file.
"""

from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MediaDerivative, MediaItem, MediaProcessingJob
from app.services.storage import (
    MEDIA_DERIVATIVE_AREAS,
    build_media_derivative_key,
    build_media_key,
)

MEDIA_ID = UUID("11111111-1111-1111-1111-111111111111")


# -- Derivative keys --------------------------------------------------------


def test_a_derivative_lives_in_its_own_area() -> None:
    key = build_media_derivative_key(MEDIA_ID, "thumbnails", "poster", ".jpg")

    assert key == f"media/{MEDIA_ID}/thumbnails/poster.jpg"


def test_the_original_never_shares_a_directory_with_a_derivative() -> None:
    """The mistake that would make a thumbnail look like the asset itself."""
    original = build_media_key(MEDIA_ID, ".mp4")
    derivative = build_media_derivative_key(MEDIA_ID, "previews", "stream", ".webm")

    assert original.split("/")[-2] != derivative.split("/")[-2]


@pytest.mark.parametrize("area", MEDIA_DERIVATIVE_AREAS)
def test_every_declared_area_builds(area: str) -> None:
    assert f"/{area}/" in build_media_derivative_key(MEDIA_ID, area, "x", ".jpg")


def test_an_unknown_area_is_refused() -> None:
    """Sanitising would create a directory no listing knows how to read."""
    with pytest.raises(ValueError) as excinfo:
        build_media_derivative_key(MEDIA_ID, "thumb", "poster", ".jpg")

    assert "thumb" in str(excinfo.value)


def test_an_extension_without_a_dot_is_still_well_formed() -> None:
    assert build_media_derivative_key(MEDIA_ID, "previews", "stream", "webm").endswith(
        ".webm"
    )


def test_a_name_with_traversal_characters_is_reduced() -> None:
    key = build_media_derivative_key(MEDIA_ID, "thumbnails", "../../etc/passwd", ".jpg")

    assert ".." not in key
    assert key.startswith(f"media/{MEDIA_ID}/thumbnails/")


def test_an_empty_name_still_produces_a_key() -> None:
    """Otherwise a regenerated thumbnail would end up at `media/x/thumbnails/.jpg`."""
    key = build_media_derivative_key(MEDIA_ID, "thumbnails", "", ".jpg")

    assert key.endswith("derivative.jpg")


# -- The two tables ---------------------------------------------------------


async def test_a_derivative_is_recorded(database_session: AsyncSession) -> None:
    item = MediaItem(title="Inspección", kind="image")
    database_session.add(item)
    await database_session.flush()

    derivative = MediaDerivative(
        media_id=item.id,
        kind="thumbnail",
        storage_key=f"media/{item.id}/thumbnails/poster.jpg",
        mime_type="image/jpeg",
        size_bytes=4096,
        sha256="a" * 64,
        width=400,
        height=300,
    )
    database_session.add(derivative)
    await database_session.commit()

    found = await database_session.execute(
        select(MediaDerivative).where(MediaDerivative.media_id == item.id)
    )
    rows = list(found.scalars().all())

    assert len(rows) == 1
    assert rows[0].kind == "thumbnail"
    assert rows[0].width == 400


async def test_only_one_derivative_of_a_kind(database_session: AsyncSession) -> None:
    """Regenerating must replace, not accumulate copies nobody lists."""
    item = MediaItem(title="Inspección", kind="image")
    database_session.add(item)
    await database_session.flush()

    for _ in range(2):
        database_session.add(
            MediaDerivative(
                media_id=item.id,
                kind="thumbnail",
                storage_key=f"media/{item.id}/thumbnails/x.jpg",
                mime_type="image/jpeg",
            )
        )

    # The specific error, not `Exception`: a blind `pytest.raises` passes for any
    # failure at all, including a typo in this test.
    with pytest.raises(IntegrityError):
        await database_session.commit()
    await database_session.rollback()


async def test_deleting_an_asset_removes_its_derivatives_and_jobs(
    database_session: AsyncSession,
) -> None:
    """A derivative without its asset is an object nobody can reach."""
    item = MediaItem(title="Inspección", kind="image")
    database_session.add(item)
    await database_session.flush()

    database_session.add(
        MediaDerivative(
            media_id=item.id,
            kind="thumbnail",
            storage_key=f"media/{item.id}/thumbnails/x.jpg",
            mime_type="image/jpeg",
        )
    )
    database_session.add(MediaProcessingJob(media_id=item.id, job_type="process"))
    await database_session.commit()

    await database_session.delete(item)
    await database_session.commit()

    derivatives = await database_session.execute(select(MediaDerivative))
    jobs = await database_session.execute(select(MediaProcessingJob))

    assert list(derivatives.scalars().all()) == []
    assert list(jobs.scalars().all()) == []


async def test_a_job_starts_queued(database_session: AsyncSession) -> None:
    item = MediaItem(title="Grabación", kind="video")
    database_session.add(item)
    await database_session.flush()

    job = MediaProcessingJob(media_id=item.id)
    database_session.add(job)
    await database_session.commit()

    stored = await database_session.get(MediaProcessingJob, job.id)

    assert stored is not None
    assert stored.status == "queued"
    assert stored.attempts == 0
    assert stored.error is None


async def test_the_original_duration_is_still_untouched(database_session: AsyncSession) -> None:
    """Nothing measures it yet, and the column must not pretend otherwise."""
    item = MediaItem(title="Grabación", kind="video")
    database_session.add(item)
    await database_session.commit()

    assert item.duration_seconds is None