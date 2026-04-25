from grotesk.domain.billing.model import TransactionType
from grotesk.domain.processing.model import ProcessingStatus

_STATUS_LABELS: dict[str, str] = {
    str(ProcessingStatus.PENDING): "Принято",
    str(ProcessingStatus.QUEUED): "В очереди",
    str(ProcessingStatus.RUNNING): "Выполняется",
    str(ProcessingStatus.COMPLETED): "Готово",
    str(ProcessingStatus.FAILED): "Ошибка",
    str(ProcessingStatus.CANCELED): "Отменена",
}

_TRANSACTION_TYPE_LABELS: dict[str, str] = {
    str(TransactionType.TOP_UP): "Пополнение",
    str(TransactionType.RESERVATION): "Бронь",
    str(TransactionType.CHARGE): "Списание",
    str(TransactionType.REFUND): "Возврат",
}


def format_processing_status(status: ProcessingStatus | str) -> str:
    code = str(status)
    return _STATUS_LABELS.get(code, code)


def format_transaction_type(transaction_type: TransactionType | str) -> str:
    code = str(transaction_type)
    return _TRANSACTION_TYPE_LABELS.get(code, code)
