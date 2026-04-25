from grotesk.domain.processing.model import ProcessingStatus
from grotesk.presentation.web.job_statuses import build_status_pipeline


def test_completed_status_has_no_active_spinner_step() -> None:
    steps = build_status_pipeline(ProcessingStatus.COMPLETED)

    assert all(step["state"] == "done" for step in steps)
    assert [step["code"] for step in steps] == ["pending", "queued", "running", "completed"]


def test_canceled_status_has_terminal_canceled_step() -> None:
    class HistoryRecord:
        def __init__(self, status: ProcessingStatus) -> None:
            self.status = status

    steps = build_status_pipeline(
        ProcessingStatus.CANCELED,
        [
            HistoryRecord(ProcessingStatus.QUEUED),
            HistoryRecord(ProcessingStatus.RUNNING),
            HistoryRecord(ProcessingStatus.CANCELED),
        ],
    )

    assert [step["code"] for step in steps] == ["pending", "queued", "running", "canceled"]
    assert steps[-1]["state"] == "canceled"
