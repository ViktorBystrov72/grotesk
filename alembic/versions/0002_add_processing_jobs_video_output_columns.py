# ruff: noqa: I001

"""Add processing_jobs video output columns.

Revision ID: 0002_add_processing_jobs_video_output_columns
Revises: 0001_initial_schema
Create Date: 2026-05-13 22:25:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = "0002_add_processing_jobs_video_output_columns"
down_revision: str | None = "0001_initial_schema"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

TABLE_NAME = "processing_jobs"


def _has_column(column_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    return column_name in {column["name"] for column in inspector.get_columns(TABLE_NAME)}


def upgrade() -> None:
    if not _has_column("video_output_width"):
        op.add_column(TABLE_NAME, sa.Column("video_output_width", sa.Integer(), nullable=True))
    if not _has_column("video_output_height"):
        op.add_column(TABLE_NAME, sa.Column("video_output_height", sa.Integer(), nullable=True))
    if not _has_column("video_output_fps"):
        op.add_column(TABLE_NAME, sa.Column("video_output_fps", sa.Integer(), nullable=True))
    if not _has_column("video_output_max_frames"):
        op.add_column(TABLE_NAME, sa.Column("video_output_max_frames", sa.Integer(), nullable=True))
    if not _has_column("video_output_guidance_scale"):
        op.add_column(TABLE_NAME, sa.Column("video_output_guidance_scale", sa.Numeric(8, 4), nullable=True))


def downgrade() -> None:
    if _has_column("video_output_guidance_scale"):
        op.drop_column(TABLE_NAME, "video_output_guidance_scale")
    if _has_column("video_output_max_frames"):
        op.drop_column(TABLE_NAME, "video_output_max_frames")
    if _has_column("video_output_fps"):
        op.drop_column(TABLE_NAME, "video_output_fps")
    if _has_column("video_output_height"):
        op.drop_column(TABLE_NAME, "video_output_height")
    if _has_column("video_output_width"):
        op.drop_column(TABLE_NAME, "video_output_width")
