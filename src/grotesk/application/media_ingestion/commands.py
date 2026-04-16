from dataclasses import dataclass

from grotesk.application.common.command import Command, CommandHandler
from grotesk.application.common.interfaces import EventPublisher, UnitOfWork
from grotesk.domain.media_ingestion.model import MediaAsset
from grotesk.domain.media_ingestion.service import MediaIngestionService


@dataclass(frozen=True)
class UploadMediaAsset(Command[MediaAsset]):
    asset: MediaAsset


class UploadMediaAssetHandler(CommandHandler[UploadMediaAsset, MediaAsset]):
    def __init__(
        self,
        media_ingestion_service: MediaIngestionService,
        publisher: EventPublisher,
        uow: UnitOfWork,
    ) -> None:
        self._media_ingestion_service = media_ingestion_service
        self._publisher = publisher
        self._uow = uow

    async def __call__(self, command: UploadMediaAsset) -> MediaAsset:
        await self._media_ingestion_service.register_asset(command.asset)
        await self._publisher.publish(self._media_ingestion_service.pull_events())
        await self._uow.commit()
        return command.asset
