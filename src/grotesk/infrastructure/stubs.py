from grotesk.domain.billing.model import AccountBalance, TopUpRequest, TopUpRequestId
from grotesk.domain.catalog.model import ModelId, ModelProfile
from grotesk.domain.common.event import Event
from grotesk.domain.identity_access.model import Email, User, UserId
from grotesk.domain.media_ingestion.model import MediaAsset, MediaAssetId
from grotesk.domain.processing.model import JobId, ProcessingJob


class InMemoryUnitOfWork:
    async def commit(self) -> None:
        return None


class InMemoryEventPublisher:
    def __init__(self) -> None:
        self.published_events: list[Event] = []

    async def publish(self, events: list[Event]) -> None:
        self.published_events.extend(events)


class InMemoryUserRepository:
    def __init__(self) -> None:
        self._users: dict[str, User] = {}

    async def add(self, user: User) -> None:
        self._users[str(user.id.value)] = user

    async def get_by_id(self, user_id: UserId) -> User | None:
        return self._users.get(str(user_id.value))

    async def get_by_email(self, email: Email) -> User | None:
        for user in self._users.values():
            if user.credential.email == email:
                return user
        return None


class InMemoryAccountBalanceRepository:
    def __init__(self) -> None:
        self._balances: dict[str, AccountBalance] = {}

    async def get_by_user_id(self, user_id: UserId) -> AccountBalance | None:
        return self._balances.get(str(user_id.value))

    async def save(self, account_balance: AccountBalance) -> None:
        self._balances[str(account_balance.user_id.value)] = account_balance


class InMemoryTopUpRequestRepository:
    def __init__(self) -> None:
        self._requests: dict[str, TopUpRequest] = {}

    async def add(self, request: TopUpRequest) -> None:
        self._requests[str(request.id.value)] = request

    async def get_by_id(self, request_id: TopUpRequestId) -> TopUpRequest | None:
        return self._requests.get(str(request_id.value))


class InMemoryMediaAssetRepository:
    def __init__(self) -> None:
        self._assets: dict[str, MediaAsset] = {}

    async def add(self, asset: MediaAsset) -> None:
        self._assets[str(asset.id.value)] = asset

    async def get_by_id(self, asset_id: MediaAssetId) -> MediaAsset | None:
        return self._assets.get(str(asset_id.value))

    async def save(self, asset: MediaAsset) -> None:
        self._assets[str(asset.id.value)] = asset


class InMemoryModelCatalogRepository:
    def __init__(self) -> None:
        self._models: dict[str, ModelProfile] = {}

    async def get_by_id(self, model_id: ModelId) -> ModelProfile | None:
        return self._models.get(str(model_id.value))

    async def save(self, profile: ModelProfile) -> None:
        self._models[str(profile.id.value)] = profile


class InMemoryProcessingJobRepository:
    def __init__(self) -> None:
        self._jobs: dict[str, ProcessingJob] = {}

    async def add(self, job: ProcessingJob) -> None:
        self._jobs[str(job.id.value)] = job

    async def get_by_id(self, job_id: JobId) -> ProcessingJob | None:
        return self._jobs.get(str(job_id.value))

    async def save(self, job: ProcessingJob) -> None:
        self._jobs[str(job.id.value)] = job
