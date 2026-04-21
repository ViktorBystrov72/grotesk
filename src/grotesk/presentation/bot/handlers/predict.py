from aiogram import Dispatcher, Router
from aiogram.filters import Command
from aiogram.types import Message

from grotesk.presentation.bot.api_client import APIClient
from grotesk.presentation.bot.handlers.auth import get_user_id

router = Router()


@router.message(Command("transcribe"))
async def cmd_transcribe(message: Message, api_client: APIClient) -> None:
    user_id = get_user_id(message.from_user.id)
    if not user_id:
        await message.answer("Please login first: /login <email> <password>")
        return

    args = message.text.split()[1:] if message.text else []
    if len(args) != 2:
        await message.answer("Usage: /transcribe <media_asset_id> <model_id>")
        return

    media_asset_id, model_id = args
    try:
        job_id = await api_client.submit_transcription(user_id, media_asset_id, model_id)
        await message.answer(f"Transcription job submitted. Job ID: {job_id}")
    except Exception as e:
        await message.answer(f"Failed to submit job: {e}")


@router.message(Command("video_edit"))
async def cmd_video_edit(message: Message, api_client: APIClient) -> None:
    user_id = get_user_id(message.from_user.id)
    if not user_id:
        await message.answer("Please login first: /login <email> <password>")
        return

    args = message.text.split()[1:] if message.text else []
    if len(args) < 3:
        await message.answer("Usage: /video_edit <media_asset_id> <model_id> <prompt>")
        return

    media_asset_id = args[0]
    model_id = args[1]
    prompt_text = " ".join(args[2:])

    try:
        job_id = await api_client.submit_video_editing(user_id, media_asset_id, model_id, prompt_text)
        await message.answer(f"Video editing job submitted. Job ID: {job_id}")
    except Exception as e:
        await message.answer(f"Failed to submit job: {e}")


def setup_predict_handlers(dp: Dispatcher) -> None:
    dp.include_router(router)
