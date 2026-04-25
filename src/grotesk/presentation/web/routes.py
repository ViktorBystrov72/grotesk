from decimal import Decimal
from pathlib import Path
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, FastAPI, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from grotesk.application.billing.commands import TopUpBalance
from grotesk.application.billing.queries import GetUserBalance, GetUserTransactionHistory
from grotesk.application.catalog.dto import ModelProfileDTO
from grotesk.application.catalog.queries import GetAvailableModels
from grotesk.application.identity_access.commands import RegisterUser
from grotesk.application.identity_access.dto import UserDTO
from grotesk.application.identity_access.queries import GetUserByEmail
from grotesk.application.processing.commands import (
    CancelProcessingJob,
    SubmitTranscriptionJob,
    SubmitVideoEditingJob,
)
from grotesk.application.processing.queries import GetUserJobDetails, GetUserJobHistory
from grotesk.domain.catalog.model import Capability, ModelId
from grotesk.domain.common.primitives import Money
from grotesk.domain.identity_access.model import UserId
from grotesk.domain.media_ingestion.model import MediaType
from grotesk.domain.processing.model import JobId, ProcessingStatus, TimelineOperation
from grotesk.main.application import Application
from grotesk.presentation.api.dependencies import (
    get_application,
    get_optional_current_user,
    login_user,
    logout_user,
)
from grotesk.presentation.api.routers.auth import get_password_hash, verify_password
from grotesk.presentation.helpers import (
    build_book_transcript,
    load_json_artifact,
    probe_media_duration_seconds,
    register_uploaded_media,
    resolve_result_artifact_path,
)
from grotesk.presentation.web.job_statuses import build_status_pipeline
from grotesk.presentation.web.status_labels import format_processing_status, format_transaction_type

router = APIRouter(include_in_schema=False)
BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
ACTIVE_JOB_STATUSES = {
    ProcessingStatus.PENDING,
    ProcessingStatus.QUEUED,
    ProcessingStatus.RUNNING,
}
CABINET_JOB_LIMIT_OPTIONS = (5, 10, 20, 50, 100)
DEFAULT_CABINET_JOB_LIMIT = 10


def setup_web(app: FastAPI) -> None:
    static_dir = BASE_DIR / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    app.include_router(router)


def template_context(request: Request, current_user: UserDTO | None, **kwargs: object) -> dict[str, object]:
    return {
        "request": request,
        "current_user": current_user,
        "format_processing_status": format_processing_status,
        "format_transaction_type": format_transaction_type,
        **kwargs,
    }


def redirect(url: str) -> RedirectResponse:
    return RedirectResponse(url=url, status_code=303)


def normalize_cabinet_job_limit(limit: int) -> int:
    if limit in CABINET_JOB_LIMIT_OPTIONS:
        return limit
    return DEFAULT_CABINET_JOB_LIMIT


def normalize_cabinet_job_page(page: int, total_jobs: int, job_limit: int) -> int:
    total_pages = max(1, (total_jobs + job_limit - 1) // job_limit)
    return min(max(page, 1), total_pages)


def format_duration_seconds(duration_seconds: float | int | None) -> str:
    if duration_seconds is None:
        return "—"
    total_seconds = max(0, round(float(duration_seconds)))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours} ч {minutes} мин {seconds} сек"
    if minutes:
        return f"{minutes} мин {seconds} сек"
    return f"{seconds} сек"


def resolve_job_duration_label(source_storage_key: str | None, result: dict[str, object] | None) -> str:
    source_duration = probe_media_duration_seconds(source_storage_key)
    if source_duration is not None:
        return format_duration_seconds(source_duration)

    result_duration = result.get("duration_seconds") if result is not None else None
    if isinstance(result_duration, int | float):
        return format_duration_seconds(result_duration)
    return "—"


def filter_models_by_capability(models: list[ModelProfileDTO], capability: Capability) -> list[ModelProfileDTO]:
    return [model for model in models if capability in model.capabilities]


def parse_time_value(raw_value: str) -> int:
    value = raw_value.strip()
    if not value:
        raise ValueError("пустое значение времени")
    if ":" not in value:
        return int(value)

    parts = value.split(":")
    if len(parts) not in (2, 3):
        raise ValueError("время должно быть в формате ss, mm:ss или hh:mm:ss")
    try:
        numbers = [int(part) for part in parts]
    except ValueError as error:
        raise ValueError("время должно содержать только числа") from error

    if any(number < 0 for number in numbers):
        raise ValueError("время не может быть отрицательным")

    if len(numbers) == 2:
        minutes, seconds = numbers
        if seconds >= 60:
            raise ValueError("секунды должны быть меньше 60")
        return minutes * 60 + seconds

    hours, minutes, seconds = numbers
    if minutes >= 60 or seconds >= 60:
        raise ValueError("минуты и секунды должны быть меньше 60")
    return hours * 3600 + minutes * 60 + seconds


def format_seconds_label(total_seconds: int) -> str:
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def build_operation_rows(operations: list[TimelineOperation]) -> list[dict[str, str]]:
    return [
        {
            "start": format_seconds_label(operation.start_second),
            "end": format_seconds_label(operation.end_second),
            "prompt": operation.prompt,
        }
        for operation in operations
    ]


def parse_operations_text(operations_text: str) -> tuple[list[TimelineOperation], str | None]:
    operations: list[TimelineOperation] = []
    for line_number, raw_line in enumerate(operations_text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        parts = [part.strip() for part in line.split("|", maxsplit=2)]
        if len(parts) != 3:
            return [], f"Строка {line_number}: используйте формат start|end|prompt"
        try:
            start_second = parse_time_value(parts[0])
            end_second = parse_time_value(parts[1])
        except ValueError:
            return [], f"Строка {line_number}: время должно быть в формате ss, mm:ss или hh:mm:ss"
        try:
            operations.append(
                TimelineOperation(
                    start_second=start_second,
                    end_second=end_second,
                    prompt=parts[2],
                )
            )
        except ValueError as error:
            return [], f"Строка {line_number}: {error}"
    return operations, None


@router.get("/")
async def home(
    request: Request,
    current_user: Annotated[UserDTO | None, Depends(get_optional_current_user)] = None,
):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context=template_context(request, current_user),
    )


@router.get("/register")
async def register_page(
    request: Request,
    current_user: Annotated[UserDTO | None, Depends(get_optional_current_user)] = None,
):
    if current_user is not None:
        return redirect("/cabinet")
    return templates.TemplateResponse(
        request=request,
        name="register.html",
        context=template_context(request, current_user),
    )


@router.post("/register")
async def register_submit(
    request: Request,
    email: Annotated[str, Form(...)],
    password: Annotated[str, Form(...)],
    application: Annotated[Application, Depends(get_application)],
    current_user: Annotated[UserDTO | None, Depends(get_optional_current_user)] = None,
):
    if current_user is not None:
        return redirect("/cabinet")

    user_id = UserId(uuid4())
    command = RegisterUser(
        user_id=user_id,
        email=email,
        password_hash=get_password_hash(password),
    )
    try:
        await application.register_user(command)
        login_user(request, user_id)
        return redirect("/cabinet")
    except ValueError as error:
        return templates.TemplateResponse(
            request=request,
            name="register.html",
            context=template_context(request, None, error=str(error), email=email),
            status_code=400,
        )


@router.get("/login")
async def login_page(
    request: Request,
    current_user: Annotated[UserDTO | None, Depends(get_optional_current_user)] = None,
):
    if current_user is not None:
        return redirect("/cabinet")
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context=template_context(request, current_user),
    )


@router.post("/login")
async def login_submit(
    request: Request,
    email: Annotated[str, Form(...)],
    password: Annotated[str, Form(...)],
    application: Annotated[Application, Depends(get_application)],
    current_user: Annotated[UserDTO | None, Depends(get_optional_current_user)] = None,
):
    if current_user is not None:
        return redirect("/cabinet")
    try:
        user_dto = await application.get_user_by_email(GetUserByEmail(email=email))
        if not verify_password(password, user_dto.password_hash):
            raise ValueError("Invalid credentials")
        login_user(request, user_dto.user_id)
        return redirect("/cabinet")
    except ValueError:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context=template_context(request, None, error="Неверный email или пароль", email=email),
            status_code=401,
        )


@router.post("/logout")
async def logout_submit(request: Request):
    logout_user(request)
    return redirect("/")


@router.get("/cabinet")
async def cabinet_page(
    request: Request,
    application: Annotated[Application, Depends(get_application)],
    current_user: Annotated[UserDTO | None, Depends(get_optional_current_user)],
    job_limit: int = DEFAULT_CABINET_JOB_LIMIT,
    job_page: int = 1,
):
    if current_user is None:
        return redirect("/login")
    selected_job_limit = normalize_cabinet_job_limit(job_limit)
    balance = Decimal(await application.get_user_balance(GetUserBalance(user_id=current_user.user_id)))
    jobs = await application.get_user_job_history(GetUserJobHistory(user_id=current_user.user_id))
    total_jobs = len(jobs)
    selected_job_page = normalize_cabinet_job_page(job_page, total_jobs, selected_job_limit)
    total_job_pages = max(1, (total_jobs + selected_job_limit - 1) // selected_job_limit)
    job_offset = (selected_job_page - 1) * selected_job_limit
    return templates.TemplateResponse(
        request=request,
        name="cabinet.html",
        context=template_context(
            request,
            current_user,
            balance=balance,
            jobs=jobs[job_offset : job_offset + selected_job_limit],
            job_limit_options=CABINET_JOB_LIMIT_OPTIONS,
            selected_job_limit=selected_job_limit,
            selected_job_page=selected_job_page,
            total_job_pages=total_job_pages,
            previous_job_page=selected_job_page - 1,
            next_job_page=selected_job_page + 1,
            has_previous_job_page=selected_job_page > 1,
            has_next_job_page=selected_job_page < total_job_pages,
            total_jobs=total_jobs,
        ),
    )


@router.get("/cabinet/balance")
async def balance_page(
    request: Request,
    application: Annotated[Application, Depends(get_application)],
    current_user: Annotated[UserDTO | None, Depends(get_optional_current_user)],
):
    if current_user is None:
        return redirect("/login")
    balance = Decimal(await application.get_user_balance(GetUserBalance(user_id=current_user.user_id)))
    transactions = await application.get_user_transaction_history(
        GetUserTransactionHistory(user_id=current_user.user_id)
    )
    return templates.TemplateResponse(
        request=request,
        name="balance.html",
        context=template_context(request, current_user, balance=balance, transactions=transactions),
    )


@router.post("/cabinet/balance")
async def balance_submit(
    request: Request,
    amount: Annotated[Decimal, Form(...)],
    application: Annotated[Application, Depends(get_application)],
    current_user: Annotated[UserDTO | None, Depends(get_optional_current_user)],
):
    if current_user is None:
        return redirect("/login")
    try:
        await application.top_up_balance(TopUpBalance(user_id=current_user.user_id, amount=Money(amount)))
        return redirect("/cabinet/balance")
    except ValueError as error:
        balance = Decimal(await application.get_user_balance(GetUserBalance(user_id=current_user.user_id)))
        transactions = await application.get_user_transaction_history(
            GetUserTransactionHistory(user_id=current_user.user_id)
        )
        return templates.TemplateResponse(
            request=request,
            name="balance.html",
            context=template_context(
                request,
                current_user,
                balance=balance,
                transactions=transactions,
                error=str(error),
            ),
            status_code=400,
        )


@router.get("/cabinet/transcription")
async def transcription_page(
    request: Request,
    application: Annotated[Application, Depends(get_application)],
    current_user: Annotated[UserDTO | None, Depends(get_optional_current_user)],
):
    if current_user is None:
        return redirect("/login")
    models = await application.get_available_models(GetAvailableModels())
    return templates.TemplateResponse(
        request=request,
        name="transcription.html",
        context=template_context(
            request,
            current_user,
            models=filter_models_by_capability(models, Capability.TRANSCRIPTION),
        ),
    )


@router.post("/cabinet/transcription")
async def transcription_submit(
    request: Request,
    model_id: Annotated[UUID, Form(...)],
    file: Annotated[UploadFile, File(...)],
    application: Annotated[Application, Depends(get_application)],
    current_user: Annotated[UserDTO | None, Depends(get_optional_current_user)],
):
    if current_user is None:
        return redirect("/login")
    models = await application.get_available_models(GetAvailableModels())
    try:
        asset = await register_uploaded_media(application, current_user.user_id, file)
        job_id = JobId(uuid4())
        await application.submit_transcription_job(
            SubmitTranscriptionJob(
                job_id=job_id,
                user_id=current_user.user_id,
                media_asset_id=asset.id,
                model_id=ModelId(model_id),
                estimated_cost=Money(Decimal("10.0")),
            )
        )
        return redirect(f"/cabinet/jobs/{job_id.value}")
    except ValueError as error:
        return templates.TemplateResponse(
            request=request,
            name="transcription.html",
            context=template_context(
                request,
                current_user,
                models=filter_models_by_capability(models, Capability.TRANSCRIPTION),
                error=str(error),
            ),
            status_code=400,
        )


@router.get("/cabinet/video-editing")
async def video_editing_page(
    request: Request,
    application: Annotated[Application, Depends(get_application)],
    current_user: Annotated[UserDTO | None, Depends(get_optional_current_user)],
):
    if current_user is None:
        return redirect("/login")
    models = await application.get_available_models(GetAvailableModels())
    return templates.TemplateResponse(
        request=request,
        name="video_editing.html",
        context=template_context(
            request,
            current_user,
            models=filter_models_by_capability(models, Capability.VIDEO_EDITING),
        ),
    )


@router.post("/cabinet/video-editing")
async def video_editing_submit(
    request: Request,
    model_id: Annotated[UUID, Form(...)],
    file: Annotated[UploadFile, File(...)],
    application: Annotated[Application, Depends(get_application)],
    current_user: Annotated[UserDTO | None, Depends(get_optional_current_user)],
    prompt_text: Annotated[str, Form()] = "",
    operations_text: Annotated[str, Form()] = "",
):
    if current_user is None:
        return redirect("/login")
    models = await application.get_available_models(GetAvailableModels())
    operations, operations_error = parse_operations_text(operations_text)
    if operations_error is not None:
        return templates.TemplateResponse(
            request=request,
            name="video_editing.html",
            context=template_context(
                request,
                current_user,
                models=filter_models_by_capability(models, Capability.VIDEO_EDITING),
                error=operations_error,
                prompt_text=prompt_text,
                operations_text=operations_text,
            ),
            status_code=400,
        )
    if not prompt_text.strip() and not operations:
        return templates.TemplateResponse(
            request=request,
            name="video_editing.html",
            context=template_context(
                request,
                current_user,
                models=filter_models_by_capability(models, Capability.VIDEO_EDITING),
                error="Укажите общий prompt или хотя бы одну операцию по времени.",
                prompt_text=prompt_text,
                operations_text=operations_text,
            ),
            status_code=400,
        )

    try:
        asset = await register_uploaded_media(application, current_user.user_id, file)
        if asset.media_type != MediaType.VIDEO:
            raise ValueError("Для video-editing нужно загрузить видеофайл.")

        job_id = JobId(uuid4())
        await application.submit_video_edit_job(
            SubmitVideoEditingJob(
                job_id=job_id,
                user_id=current_user.user_id,
                media_asset_id=asset.id,
                model_id=ModelId(model_id),
                estimated_cost=Money(Decimal("50.0")),
                prompt_text=prompt_text,
                operations=operations,
            )
        )
        return redirect(f"/cabinet/jobs/{job_id.value}")
    except ValueError as error:
        return templates.TemplateResponse(
            request=request,
            name="video_editing.html",
            context=template_context(
                request,
                current_user,
                models=filter_models_by_capability(models, Capability.VIDEO_EDITING),
                error=str(error),
                prompt_text=prompt_text,
                operations_text=operations_text,
            ),
            status_code=400,
        )


@router.get("/cabinet/history")
async def history_page(
    request: Request,
    application: Annotated[Application, Depends(get_application)],
    current_user: Annotated[UserDTO | None, Depends(get_optional_current_user)],
):
    if current_user is None:
        return redirect("/login")
    jobs = await application.get_user_job_history(GetUserJobHistory(user_id=current_user.user_id))
    transactions = await application.get_user_transaction_history(
        GetUserTransactionHistory(user_id=current_user.user_id)
    )
    return templates.TemplateResponse(
        request=request,
        name="history.html",
        context=template_context(request, current_user, jobs=jobs, transactions=transactions),
    )


@router.get("/cabinet/jobs/{job_id}")
async def job_detail_page(
    request: Request,
    job_id: UUID,
    application: Annotated[Application, Depends(get_application)],
    current_user: Annotated[UserDTO | None, Depends(get_optional_current_user)],
):
    if current_user is None:
        return redirect("/login")
    try:
        job = await application.get_user_job_detail(
            GetUserJobDetails(user_id=current_user.user_id, job_id=JobId(job_id))
        )
    except ValueError:
        return redirect("/cabinet/history")

    artifact_path = resolve_result_artifact_path(job.result_type, job.result_id)
    result = load_json_artifact(artifact_path)
    status_stages = build_status_pipeline(job.status, job.history)
    auto_refresh = job.status in ACTIVE_JOB_STATUSES
    duration_label = resolve_job_duration_label(job.source_storage_key, result)
    return templates.TemplateResponse(
        request=request,
        name="job_detail.html",
        context=template_context(
            request,
            current_user,
            job=job,
            result=result,
            duration_label=duration_label,
            book_transcript=build_book_transcript(result),
            operation_rows=build_operation_rows(job.operations),
            artifact_url=f"/jobs/{job.job_id.value}/artifact" if artifact_path is not None else None,
            status_stages=status_stages,
            auto_refresh=auto_refresh,
            can_cancel=job.status in ACTIVE_JOB_STATUSES,
        ),
    )


@router.post("/cabinet/jobs/{job_id}/cancel")
async def cancel_job_submit(
    job_id: UUID,
    application: Annotated[Application, Depends(get_application)],
    current_user: Annotated[UserDTO | None, Depends(get_optional_current_user)],
):
    if current_user is None:
        return redirect("/login")

    try:
        await application.cancel_processing_job(CancelProcessingJob(job_id=JobId(job_id), user_id=current_user.user_id))
    except ValueError:
        return redirect(f"/cabinet/jobs/{job_id}")
    return redirect(f"/cabinet/jobs/{job_id}")
