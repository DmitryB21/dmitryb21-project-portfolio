"""Initial schema with audio_path support.

Revision ID: 20251117_add_audio_path
Revises:
Create Date: 2025-11-17 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg


# revision identifiers, used by Alembic.
revision = "20251117_add_audio_path"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "videos",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("audio_path", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("source_url", name="uq_videos_source_url"),
    )

    op.create_table(
        "transcripts",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("video_id", pg.UUID(as_uuid=True), sa.ForeignKey("videos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("language", sa.String(length=16), nullable=False, server_default="ru"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("metadata", pg.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "summaries",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("video_id", pg.UUID(as_uuid=True), sa.ForeignKey("videos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("data", pg.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "processing_jobs",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("video_id", pg.UUID(as_uuid=True), sa.ForeignKey("videos.id", ondelete="SET NULL"), nullable=True),
        sa.Column("job_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("payload", pg.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("processing_jobs")
    op.drop_table("summaries")
    op.drop_table("transcripts")
    op.drop_table("videos")


