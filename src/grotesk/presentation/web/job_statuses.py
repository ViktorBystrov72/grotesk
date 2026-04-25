from grotesk.domain.processing.model import ProcessingStatus

# Порядок нормального прохождения задачи (без ветки failed)
_MAIN_FLOW: tuple[str, ...] = ("pending", "queued", "running", "completed")
_INTERRUPTED_FLOW: tuple[str, ...] = ("pending", "queued", "running")

# Короткие заголовки и пояснения для UI (легенда + маршрут)
_LABELS: dict[str, tuple[str, str]] = {
    "pending": (
        "Принято",
        "Задача создана, проверяется баланс и бронь кредитов.",
    ),
    "queued": (
        "В очереди",
        "Задача в очереди брокера сообщений. Воркер заберёт её, когда освободится — обычно от секунд до пары минут.",
    ),
    "running": (
        "Выполняется",
        "Идёт ML-обработка на воркере. Длительность зависит от размера файла и нагрузки (часто минуты).",
    ),
    "completed": (
        "Готово",
        "Результат записан, можно скачать артефакт (если тип задачи подразумевает файл/JSON).",
    ),
    "failed": (
        "Ошибка",
        "Пайплайн завершился с ошибкой. Кредиты: не списываются с брони или возвращаются — см. биллинг и логи воркера.",
    ),
    "canceled": (
        "Отменена",
        "Задача отменена пользователем. "
        "Если ML уже стартовал, воркер прерывает дочерний процесс и освобождает бронь кредитов.",
    ),
}


def _status_code(record: object) -> str:
    status = getattr(record, "status", record)
    return str(status.value if hasattr(status, "value") else status)


def build_status_pipeline(
    current: ProcessingStatus,
    history: list[object] | None = None,
) -> list[dict[str, str]]:
    """
    Состояния этапов для «маршрута» на странице задачи: done | active | upcoming | error | canceled.
    """
    s = current.value
    history_codes = {_status_code(record) for record in (history or [])}
    if s in {"failed", "canceled"}:
        steps: list[dict[str, str]] = []
        for code in _INTERRUPTED_FLOW:
            title, description = _LABELS[code]
            steps.append(
                {
                    "code": code,
                    "title": title,
                    "description": description,
                    "state": "done" if code in history_codes else "upcoming",
                }
            )
        title, description = _LABELS[s]
        steps.append(
            {
                "code": s,
                "title": title,
                "description": description,
                "state": "canceled" if s == "canceled" else "error",
            }
        )
        return steps

    try:
        active_index = _MAIN_FLOW.index(s)
    except ValueError:
        active_index = 0

    out: list[dict[str, str]] = []
    for i, code in enumerate(_MAIN_FLOW):
        title, description = _LABELS[code]
        if s == "completed":
            st = "done"
        elif i < active_index:
            st = "done"
        elif i == active_index:
            st = "active"
        else:
            st = "upcoming"
        out.append(
            {
                "code": code,
                "title": title,
                "description": description,
                "state": st,
            }
        )
    return out
