from grotesk.domain.processing.model import ProcessingStatus

# Порядок нормального прохождения задачи (без ветки failed)
_MAIN_FLOW: tuple[str, ...] = ("pending", "queued", "running", "completed")

# Короткие заголовки и пояснения для UI (легенда + маршрут)
_LABELS: dict[str, tuple[str, str]] = {
    "pending": (
        "Принято",
        "Задача создана, проверяется баланс и бронь кредитов.",
    ),
    "queued": (
        "В очереди",
        "Задача в очереди брокера сообщений. "
        "Воркер заберёт её, когда освободится — обычно от секунд до пары минут.",
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
        "Пайплайн завершился с ошибкой. "
        "Кредиты: не списываются с брони или возвращаются — см. биллинг и логи воркера.",
    ),
}


def build_status_pipeline(current: ProcessingStatus) -> list[dict[str, str]]:
    """
    Состояния этапов для «маршрута» на странице задачи: done | active | upcoming | error.
    """
    s = current.value
    if s == "failed":
        steps: list[dict[str, str]] = []
        for code in ("pending", "queued", "running"):
            title, description = _LABELS[code]
            steps.append(
                {
                    "code": code,
                    "title": title,
                    "description": description,
                    "state": "done",
                }
            )
        title, description = _LABELS["failed"]
        steps.append(
            {
                "code": "failed",
                "title": title,
                "description": description,
                "state": "error",
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
        if i < active_index:
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
