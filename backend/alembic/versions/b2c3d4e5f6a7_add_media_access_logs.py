"""Add `media_access_logs`, so a media download leaves a trace.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-10-06

Found by the 2026-10-05 audit. `GET /api/v1/media/{id}/content` served the bytes
with no row written anywhere: no `EvidenceAccessLog`, no `audit_logs` entry, because
the audit middleware only records mutations. The evidence chain of custody recorded
every read, and media did not, even though the library holds recordings, signature
images and photographs of documents.

The shape copies `evidence_access_logs` on purpose. Two different tables for the same
question ("who opened this file, from where") would mean two queries to answer it and
two places to forget to write.

`bytes_served` is there because `Range` is honoured on this route: a video player
asking for one slice would otherwise write the full size on every seek.

Nothing here backfills. Rows for downloads that already happened do not exist and
cannot be reconstructed; pretending otherwise would be worse than the gap.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "media_access_logs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "media_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("media_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("access_type", sa.String(20), nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # 45 is the widest an IPv6 address with a scope id can render as text.
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("bytes_served", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_media_access_logs_media_id", "media_access_logs", ["media_id"]
    )
    op.create_index(
        "ix_media_access_logs_access_type", "media_access_logs", ["access_type"]
    )
    op.create_index(
        "ix_media_access_logs_media_id_created_at",
        "media_access_logs",
        ["media_id", "created_at"],
    )


def downgrade() -> None:
    """Drop the trail.

    That loses real access history, so it is destructive by design and only exists
    for symmetry with the other revisions. A downgrade of this table is a decision to
    stop recording who opened the library, not a rollback of a schema mistake.
    """
    op.drop_index("ix_media_access_logs_media_id_created_at", table_name="media_access_logs")
    op.drop_index("ix_media_access_logs_access_type", table_name="media_access_logs")
    op.drop_index("ix_media_access_logs_media_id", table_name="media_access_logs")
    op.drop_table("media_access_logs")