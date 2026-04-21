from grotesk.domain.billing.model import (
    AccountBalance,
    BillingTransaction,
    CreditReservation,
    TopUpRequest,
    TopUpRequestId,
    TransactionId,
)
from grotesk.domain.catalog.model import ModelId, ModelProfile, PricingRule
from grotesk.domain.common.primitives import EntityId, FileLocation, Money
from grotesk.domain.identity_access.model import Credential, Email, PasswordHash, User, UserId
from grotesk.domain.media_ingestion.model import AttachmentAsset, MediaAsset, MediaAssetId
from grotesk.domain.processing.model import JobHistoryRecord, JobId, JobResultRef, ProcessingJob
from grotesk.infrastructure.db.models.entities import (
    AccountBalanceModel,
    BillingTransactionModel,
    JobHistoryRecordModel,
    MediaAssetModel,
    ModelProfileModel,
    ProcessingJobModel,
    TopUpRequestModel,
    UserModel,
)


def user_to_domain(model: UserModel) -> User:
    return User(
        id=UserId(model.id),
        credential=Credential(
            email=Email(model.email),
            password_hash=PasswordHash(model.password_hash),
        ),
        role=model.role,
        is_active=model.is_active,
    )


def account_balance_to_domain(model: AccountBalanceModel) -> AccountBalance:
    return AccountBalance(
        user_id=UserId(model.user_id),
        available=Money(model.available_amount, model.currency),
        reservations=[
            CreditReservation(
                job_id=JobId(reservation.job_id),
                amount=Money(reservation.amount, reservation.currency),
                is_confirmed=reservation.is_confirmed,
            )
            for reservation in model.reservations
        ],
    )


def top_up_request_to_domain(model: TopUpRequestModel) -> TopUpRequest:
    return TopUpRequest(
        id=TopUpRequestId(model.id),
        user_id=UserId(model.user_id),
        amount=Money(model.amount, model.currency),
        status=model.status,
    )


def billing_transaction_to_domain(model: BillingTransactionModel) -> BillingTransaction:
    return BillingTransaction(
        id=TransactionId(model.id),
        user_id=UserId(model.user_id),
        amount=Money(model.amount, model.currency),
        transaction_type=model.transaction_type,
        created_at=model.created_at,
        related_job_id=JobId(model.related_job_id) if model.related_job_id else None,
    )


def model_profile_to_domain(model: ModelProfileModel) -> ModelProfile:
    return ModelProfile(
        id=ModelId(model.id),
        name=model.name,
        capabilities=[capability.capability for capability in model.capabilities],
        pricing_rules=[
            PricingRule(
                capability=pricing_rule.capability,
                price=Money(pricing_rule.amount, pricing_rule.currency),
            )
            for pricing_rule in model.pricing_rules
        ],
        is_active=model.is_active,
    )


def media_asset_to_domain(model: MediaAssetModel) -> MediaAsset:
    return MediaAsset(
        id=MediaAssetId(model.id),
        owner_id=UserId(model.owner_id),
        media_type=model.media_type,
        location=FileLocation(model.location),
        status=model.status,
        attachments=[
            AttachmentAsset(
                id=MediaAssetId(attachment.id),
                owner_id=UserId(attachment.owner_id),
                media_type=attachment.media_type,
                location=FileLocation(attachment.location),
            )
            for attachment in model.attachments
        ],
    )


def history_record_to_domain(model: JobHistoryRecordModel) -> JobHistoryRecord:
    return JobHistoryRecord(
        status=model.status,
        changed_at=model.changed_at,
        message=model.message,
    )


def processing_job_to_domain(model: ProcessingJobModel) -> ProcessingJob:
    result_ref = None
    if model.result_type and model.result_id:
        result_ref = JobResultRef(result_type=model.result_type, result_id=EntityId(model.result_id))

    return ProcessingJob(
        id=JobId(model.id),
        user_id=UserId(model.user_id),
        media_asset_id=MediaAssetId(model.media_asset_id),
        model_id=ModelId(model.model_id),
        job_type=model.job_type,
        estimated_cost=Money(model.estimated_cost_amount, model.estimated_cost_currency),
        status=model.status,
        created_at=model.created_at,
        result_ref=result_ref,
        history=[history_record_to_domain(record) for record in model.history],
    )
