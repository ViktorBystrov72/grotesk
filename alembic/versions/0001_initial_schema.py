# ruff: noqa: E501, I001

"""Initial schema.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-05-13 22:20:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from grotesk.domain.billing.model import TopUpStatus, TransactionType
from grotesk.domain.catalog.model import Capability
from grotesk.domain.identity_access.model import UserRole
from grotesk.domain.media_ingestion.model import MediaStatus, MediaType
from grotesk.domain.processing.model import JobType, ProcessingStatus

# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.Enum(UserRole, native_enum=False), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_table(
        "model_profiles",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_model_profiles")),
        sa.UniqueConstraint("name", name=op.f("uq_model_profiles_name")),
    )
    op.create_table(
        "account_balances",
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("available_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_account_balances_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_account_balances")),
    )
    op.create_table(
        "billing_transactions",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=32), nullable=False),
        sa.Column("transaction_type", sa.Enum(TransactionType, native_enum=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("related_job_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_billing_transactions_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_billing_transactions")),
    )
    op.create_index(op.f("ix_billing_transactions_user_id"), "billing_transactions", ["user_id"], unique=False)
    op.create_table(
        "top_up_requests",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=32), nullable=False),
        sa.Column("status", sa.Enum(TopUpStatus, native_enum=False), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_top_up_requests_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_top_up_requests")),
    )
    op.create_table(
        "model_capabilities",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("model_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("capability", sa.Enum(Capability, native_enum=False), nullable=False),
        sa.ForeignKeyConstraint(["model_id"], ["model_profiles.id"], name=op.f("fk_model_capabilities_model_id_model_profiles"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_model_capabilities")),
    )
    op.create_table(
        "pricing_rules",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("model_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("capability", sa.Enum(Capability, native_enum=False), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["model_id"], ["model_profiles.id"], name=op.f("fk_pricing_rules_model_id_model_profiles"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pricing_rules")),
    )
    op.create_table(
        "media_assets",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("owner_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("media_type", sa.Enum(MediaType, native_enum=False), nullable=False),
        sa.Column("location", sa.String(length=512), nullable=False),
        sa.Column("status", sa.Enum(MediaStatus, native_enum=False), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], name=op.f("fk_media_assets_owner_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_media_assets")),
    )
    op.create_table(
        "attachment_assets",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("parent_asset_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("owner_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("media_type", sa.Enum(MediaType, native_enum=False), nullable=False),
        sa.Column("location", sa.String(length=512), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], name=op.f("fk_attachment_assets_owner_id_users"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["parent_asset_id"],
            ["media_assets.id"],
            name=op.f("fk_attachment_assets_parent_asset_id_media_assets"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_attachment_assets")),
    )
    op.create_table(
        "processing_jobs",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("media_asset_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("model_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("job_type", sa.Enum(JobType, native_enum=False), nullable=False),
        sa.Column("estimated_cost_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("estimated_cost_currency", sa.String(length=32), nullable=False),
        sa.Column("prompt_text", sa.Text(), nullable=True),
        sa.Column("operations_payload", sa.JSON(), nullable=True),
        sa.Column("status", sa.Enum(ProcessingStatus, native_enum=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("result_type", sa.String(length=255), nullable=True),
        sa.Column("result_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["media_asset_id"], ["media_assets.id"], name=op.f("fk_processing_jobs_media_asset_id_media_assets"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["model_id"], ["model_profiles.id"], name=op.f("fk_processing_jobs_model_id_model_profiles"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_processing_jobs_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_processing_jobs")),
    )
    op.create_table(
        "credit_reservations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("job_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=32), nullable=False),
        sa.Column("is_confirmed", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["account_balances.user_id"],
            name=op.f("fk_credit_reservations_user_id_account_balances"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_credit_reservations")),
    )
    op.create_table(
        "job_history_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("job_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("status", sa.Enum(ProcessingStatus, native_enum=False), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["processing_jobs.id"], name=op.f("fk_job_history_records_job_id_processing_jobs"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_job_history_records")),
    )


def downgrade() -> None:
    op.drop_table("job_history_records")
    op.drop_table("credit_reservations")
    op.drop_table("processing_jobs")
    op.drop_table("attachment_assets")
    op.drop_table("media_assets")
    op.drop_table("pricing_rules")
    op.drop_table("model_capabilities")
    op.drop_table("top_up_requests")
    op.drop_index(op.f("ix_billing_transactions_user_id"), table_name="billing_transactions")
    op.drop_table("billing_transactions")
    op.drop_table("account_balances")
    op.drop_table("model_profiles")
    op.drop_table("users")
