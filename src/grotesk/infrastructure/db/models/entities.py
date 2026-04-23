from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from grotesk.domain.billing.model import TopUpStatus, TransactionType
from grotesk.domain.catalog.model import Capability
from grotesk.domain.identity_access.model import UserRole
from grotesk.domain.media_ingestion.model import MediaStatus, MediaType
from grotesk.domain.processing.model import JobType, ProcessingStatus
from grotesk.infrastructure.db.base import Base


class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(sa.Uuid(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(sa.String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(sa.Enum(UserRole, native_enum=False), nullable=False)
    is_active: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=True)


class AccountBalanceModel(Base):
    __tablename__ = "account_balances"

    user_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    available_amount: Mapped[Decimal] = mapped_column(sa.Numeric(12, 2), nullable=False, default=Decimal("0"))
    currency: Mapped[str] = mapped_column(sa.String(32), nullable=False, default="CREDIT")

    reservations: Mapped[list["CreditReservationModel"]] = relationship(
        back_populates="account_balance",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class CreditReservationModel(Base):
    __tablename__ = "credit_reservations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("account_balances.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    job_id: Mapped[UUID] = mapped_column(sa.Uuid(as_uuid=True), nullable=False)
    amount: Mapped[Decimal] = mapped_column(sa.Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(sa.String(32), nullable=False, default="CREDIT")
    is_confirmed: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=False)

    account_balance: Mapped[AccountBalanceModel] = relationship(back_populates="reservations")


class BillingTransactionModel(Base):
    __tablename__ = "billing_transactions"

    id: Mapped[UUID] = mapped_column(sa.Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    amount: Mapped[Decimal] = mapped_column(sa.Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(sa.String(32), nullable=False, default="CREDIT")
    transaction_type: Mapped[TransactionType] = mapped_column(
        sa.Enum(TransactionType, native_enum=False),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    )
    related_job_id: Mapped[UUID | None] = mapped_column(sa.Uuid(as_uuid=True), nullable=True)


class TopUpRequestModel(Base):
    __tablename__ = "top_up_requests"

    id: Mapped[UUID] = mapped_column(sa.Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(sa.Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(sa.String(32), nullable=False, default="CREDIT")
    status: Mapped[TopUpStatus] = mapped_column(sa.Enum(TopUpStatus, native_enum=False), nullable=False)


class ModelProfileModel(Base):
    __tablename__ = "model_profiles"

    id: Mapped[UUID] = mapped_column(sa.Uuid(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False, unique=True)
    is_active: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=True)

    capabilities: Mapped[list["ModelCapabilityModel"]] = relationship(
        back_populates="model_profile",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    pricing_rules: Mapped[list["PricingRuleModel"]] = relationship(
        back_populates="model_profile",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class ModelCapabilityModel(Base):
    __tablename__ = "model_capabilities"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    model_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("model_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    capability: Mapped[Capability] = mapped_column(sa.Enum(Capability, native_enum=False), nullable=False)

    model_profile: Mapped[ModelProfileModel] = relationship(back_populates="capabilities")


class PricingRuleModel(Base):
    __tablename__ = "pricing_rules"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    model_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("model_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    capability: Mapped[Capability] = mapped_column(sa.Enum(Capability, native_enum=False), nullable=False)
    amount: Mapped[Decimal] = mapped_column(sa.Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(sa.String(32), nullable=False, default="CREDIT")

    model_profile: Mapped[ModelProfileModel] = relationship(back_populates="pricing_rules")


class MediaAssetModel(Base):
    __tablename__ = "media_assets"

    id: Mapped[UUID] = mapped_column(sa.Uuid(as_uuid=True), primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    media_type: Mapped[MediaType] = mapped_column(sa.Enum(MediaType, native_enum=False), nullable=False)
    location: Mapped[str] = mapped_column(sa.String(512), nullable=False)
    status: Mapped[MediaStatus] = mapped_column(sa.Enum(MediaStatus, native_enum=False), nullable=False)

    attachments: Mapped[list["AttachmentAssetModel"]] = relationship(
        back_populates="media_asset",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class AttachmentAssetModel(Base):
    __tablename__ = "attachment_assets"

    id: Mapped[UUID] = mapped_column(sa.Uuid(as_uuid=True), primary_key=True, default=uuid4)
    parent_asset_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("media_assets.id", ondelete="CASCADE"),
        nullable=False,
    )
    owner_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    media_type: Mapped[MediaType] = mapped_column(sa.Enum(MediaType, native_enum=False), nullable=False)
    location: Mapped[str] = mapped_column(sa.String(512), nullable=False)

    media_asset: Mapped[MediaAssetModel] = relationship(back_populates="attachments")


class ProcessingJobModel(Base):
    __tablename__ = "processing_jobs"

    id: Mapped[UUID] = mapped_column(sa.Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    media_asset_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("media_assets.id", ondelete="CASCADE"),
        nullable=False,
    )
    model_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("model_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    job_type: Mapped[JobType] = mapped_column(sa.Enum(JobType, native_enum=False), nullable=False)
    estimated_cost_amount: Mapped[Decimal] = mapped_column(sa.Numeric(12, 2), nullable=False)
    estimated_cost_currency: Mapped[str] = mapped_column(sa.String(32), nullable=False, default="CREDIT")
    prompt_text: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    operations_payload: Mapped[list[dict[str, object]] | None] = mapped_column(sa.JSON, nullable=True)
    status: Mapped[ProcessingStatus] = mapped_column(
        sa.Enum(ProcessingStatus, native_enum=False),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    )
    result_type: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)
    result_id: Mapped[UUID | None] = mapped_column(sa.Uuid(as_uuid=True), nullable=True)

    history: Mapped[list["JobHistoryRecordModel"]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="JobHistoryRecordModel.changed_at",
    )


class JobHistoryRecordModel(Base):
    __tablename__ = "job_history_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    job_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("processing_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[ProcessingStatus] = mapped_column(sa.Enum(ProcessingStatus, native_enum=False), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    )
    message: Mapped[str] = mapped_column(sa.Text, nullable=False, default="")

    job: Mapped[ProcessingJobModel] = relationship(back_populates="history")
