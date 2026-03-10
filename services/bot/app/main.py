from __future__ import annotations

import asyncio
import base64
import io
import logging
import time
from typing import Final

from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from .api_client import BackendApiError, BackendClient
from .config import Settings
from .constants import (
    DEFAULT_DURATION_SECONDS,
    DEFAULT_INFERENCE_STEPS,
    DEFAULT_PROMPT_I2V,
    DEFAULT_VIDEO_QUALITY,
    FPS_CHOICES,
    MAX_DURATION_SECONDS,
    MAX_INFERENCE_STEPS,
    MAX_VIDEO_QUALITY,
    MIN_DURATION_SECONDS,
    MIN_INFERENCE_STEPS,
    MIN_VIDEO_QUALITY,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("wan-telegram-bot")

(
    WAIT_INPUT_IMAGE,
    WAIT_PROMPT,
    WAIT_DURATION,
    WAIT_FPS,
    WAIT_STEPS,
    WAIT_QUALITY,
    WAIT_LAST_IMAGE,
) = range(7)

DATA_INPUT_IMAGE: Final[str] = "input_image_base64"
DATA_LAST_IMAGE: Final[str] = "last_image_base64"
DATA_PROMPT: Final[str] = "prompt"
DATA_DURATION: Final[str] = "duration_seconds"
DATA_FPS: Final[str] = "fps"
DATA_STEPS: Final[str] = "inference_steps"
DATA_QUALITY: Final[str] = "video_quality"

settings = Settings.from_env()
backend_client = BackendClient(settings.backend_base_url)


def _fps_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[str(v) for v in FPS_CHOICES], ["/skip"]],
        one_time_keyboard=True,
        resize_keyboard=True,
        input_field_placeholder="16, 32 или 64",
    )


def _remove_keyboard() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove(remove_keyboard=True)


async def _download_image_base64(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str | None:
    message = update.message
    if message is None:
        return None

    file_id: str | None = None
    if message.photo:
        file_id = message.photo[-1].file_id
    elif message.document and (message.document.mime_type or "").startswith("image/"):
        file_id = message.document.file_id

    if not file_id:
        return None

    file = await context.bot.get_file(file_id)
    payload = await file.download_as_bytearray()
    return base64.b64encode(bytes(payload)).decode("utf-8")


def _parse_float_in_range(raw: str, *, minimum: float, maximum: float) -> float:
    value = float(raw.replace(",", "."))
    if value < minimum or value > maximum:
        raise ValueError(f"value must be in range [{minimum}, {maximum}]")
    return value


def _parse_int_in_range(raw: str, *, minimum: int, maximum: int) -> int:
    value = int(raw)
    if value < minimum or value > maximum:
        raise ValueError(f"value must be in range [{minimum}, {maximum}]")
    return value


async def start(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return

    await update.message.reply_text(
        "Этот бот генерирует видео через Wan2.2 I2V (RunPod).\n"
        "Команды:\n"
        "/generate - создать видео\n"
        "/cancel - отменить текущий диалог"
    )


async def generate_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message is None:
        return ConversationHandler.END

    context.user_data.clear()
    await update.message.reply_text(
        "Шаг 1/7. Пришлите исходное изображение.",
        reply_markup=_remove_keyboard(),
    )
    return WAIT_INPUT_IMAGE


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message is not None:
        await update.message.reply_text("Диалог отменен.", reply_markup=_remove_keyboard())
    context.user_data.clear()
    return ConversationHandler.END


async def receive_input_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message is None:
        return WAIT_INPUT_IMAGE

    image_b64 = await _download_image_base64(update, context)
    if image_b64 is None:
        await update.message.reply_text("Нужно прислать изображение: как фото или как документ-картинку.")
        return WAIT_INPUT_IMAGE

    context.user_data[DATA_INPUT_IMAGE] = image_b64
    await update.message.reply_text(
        "Шаг 2/7. Введите промпт.\n"
        f"Можно /skip для значения по умолчанию:\n`{DEFAULT_PROMPT_I2V}`",
        parse_mode="Markdown",
    )
    return WAIT_PROMPT


async def receive_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message is None or not update.message.text:
        return WAIT_PROMPT

    prompt = update.message.text.strip()
    if not prompt:
        await update.message.reply_text("Промпт не может быть пустым. Пришлите текст или /skip.")
        return WAIT_PROMPT

    context.user_data[DATA_PROMPT] = prompt
    await update.message.reply_text(
        "Шаг 3/7. Укажите длительность в секундах (0.5 - 10.0).\n"
        f"Можно /skip (по умолчанию {DEFAULT_DURATION_SECONDS})."
    )
    return WAIT_DURATION


async def skip_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data[DATA_PROMPT] = DEFAULT_PROMPT_I2V
    if update.message is not None:
        await update.message.reply_text(
            "Использую промпт по умолчанию.\n"
            "Шаг 3/7. Укажите длительность в секундах (0.5 - 10.0)."
        )
    return WAIT_DURATION


async def receive_duration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message is None or not update.message.text:
        return WAIT_DURATION

    try:
        duration = _parse_float_in_range(
            update.message.text.strip(),
            minimum=MIN_DURATION_SECONDS,
            maximum=MAX_DURATION_SECONDS,
        )
    except ValueError:
        await update.message.reply_text("Некорректная длительность. Введите число от 0.5 до 10.0 или /skip.")
        return WAIT_DURATION

    context.user_data[DATA_DURATION] = duration
    await update.message.reply_text(
        "Шаг 4/7. Укажите FPS: 16, 32 или 64.\nМожно /skip (16).",
        reply_markup=_fps_keyboard(),
    )
    return WAIT_FPS


async def skip_duration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data[DATA_DURATION] = DEFAULT_DURATION_SECONDS
    if update.message is not None:
        await update.message.reply_text(
            "Использую длительность по умолчанию.\n"
            "Шаг 4/7. Укажите FPS: 16, 32 или 64.",
            reply_markup=_fps_keyboard(),
        )
    return WAIT_FPS


async def receive_fps(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message is None or not update.message.text:
        return WAIT_FPS

    raw = update.message.text.strip()
    try:
        fps = int(raw)
    except ValueError:
        await update.message.reply_text("FPS должен быть числом: 16, 32 или 64.")
        return WAIT_FPS

    if fps not in FPS_CHOICES:
        await update.message.reply_text("Поддерживаются только 16, 32 или 64.")
        return WAIT_FPS

    context.user_data[DATA_FPS] = fps
    await update.message.reply_text(
        "Шаг 5/7. Укажите число шагов инференса (1-30).\n"
        f"Можно /skip (по умолчанию {DEFAULT_INFERENCE_STEPS}).",
        reply_markup=_remove_keyboard(),
    )
    return WAIT_STEPS


async def skip_fps(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data[DATA_FPS] = FPS_CHOICES[0]
    if update.message is not None:
        await update.message.reply_text(
            "Использую FPS по умолчанию (16).\n"
            "Шаг 5/7. Укажите число шагов инференса (1-30).",
            reply_markup=_remove_keyboard(),
        )
    return WAIT_STEPS


async def receive_steps(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message is None or not update.message.text:
        return WAIT_STEPS

    try:
        steps = _parse_int_in_range(
            update.message.text.strip(),
            minimum=MIN_INFERENCE_STEPS,
            maximum=MAX_INFERENCE_STEPS,
        )
    except ValueError:
        await update.message.reply_text("Некорректное значение. Введите целое число от 1 до 30 или /skip.")
        return WAIT_STEPS

    context.user_data[DATA_STEPS] = steps
    await update.message.reply_text(
        "Шаг 6/7. Укажите качество видео (1-10).\n"
        f"Можно /skip (по умолчанию {DEFAULT_VIDEO_QUALITY})."
    )
    return WAIT_QUALITY


async def skip_steps(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data[DATA_STEPS] = DEFAULT_INFERENCE_STEPS
    if update.message is not None:
        await update.message.reply_text(
            "Использую шаги инференса по умолчанию.\n"
            "Шаг 6/7. Укажите качество видео (1-10)."
        )
    return WAIT_QUALITY


async def receive_quality(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message is None or not update.message.text:
        return WAIT_QUALITY

    try:
        quality = _parse_int_in_range(
            update.message.text.strip(),
            minimum=MIN_VIDEO_QUALITY,
            maximum=MAX_VIDEO_QUALITY,
        )
    except ValueError:
        await update.message.reply_text("Некорректное значение. Введите целое число от 1 до 10 или /skip.")
        return WAIT_QUALITY

    context.user_data[DATA_QUALITY] = quality
    await update.message.reply_text(
        "Шаг 7/7. Пришлите опциональное финальное изображение или /skip."
    )
    return WAIT_LAST_IMAGE


async def skip_quality(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data[DATA_QUALITY] = DEFAULT_VIDEO_QUALITY
    if update.message is not None:
        await update.message.reply_text(
            "Использую качество видео по умолчанию.\n"
            "Шаг 7/7. Пришлите опциональное финальное изображение или /skip."
        )
    return WAIT_LAST_IMAGE


def _build_backend_payload(data: dict) -> dict:
    return {
        "input_image_base64": data[DATA_INPUT_IMAGE],
        "last_image_base64": data.get(DATA_LAST_IMAGE),
        "prompt": data.get(DATA_PROMPT, DEFAULT_PROMPT_I2V),
        "duration_seconds": data.get(DATA_DURATION, DEFAULT_DURATION_SECONDS),
        "fps": data.get(DATA_FPS, FPS_CHOICES[0]),
        "inference_steps": data.get(DATA_STEPS, DEFAULT_INFERENCE_STEPS),
        "video_quality": data.get(DATA_QUALITY, DEFAULT_VIDEO_QUALITY),
    }


async def _submit_and_wait(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    message = update.message
    if message is None:
        context.user_data.clear()
        return ConversationHandler.END

    payload = _build_backend_payload(context.user_data)

    try:
        submit_msg = await message.reply_text("Отправляю задачу в очередь генерации...")
        job_id = await backend_client.submit_job(payload)
        await submit_msg.edit_text(f"Задача создана: `{job_id}`\nСтатус: в очереди", parse_mode="Markdown")

        last_status_push = time.monotonic()

        while True:
            await asyncio.sleep(settings.poll_interval_seconds)
            status = await backend_client.get_job_status(job_id)

            if status.status == "completed":
                break

            if status.status == "failed":
                raise BackendApiError(status.error or "Сервер генерации вернул ошибку")

            now = time.monotonic()
            if now - last_status_push >= settings.status_update_seconds:
                await message.reply_text(f"Задача `{job_id}` в обработке...", parse_mode="Markdown")
                last_status_push = now

        await context.bot.send_chat_action(chat_id=message.chat_id, action=ChatAction.UPLOAD_VIDEO)
        video_bytes = await backend_client.download_video(job_id)

        video_file = io.BytesIO(video_bytes)
        video_file.name = f"wan22-{job_id}.mp4"
        video_file.seek(0)

        caption = f"Готово. ID задачи: {job_id}"
        if status.seed is not None:
            caption += f", seed={status.seed}"

        await context.bot.send_video(
            chat_id=message.chat_id,
            video=video_file,
            caption=caption,
            supports_streaming=True,
        )
    except BackendApiError as exc:
        logger.exception("Generation failed (backend error)")
        await message.reply_text(f"Ошибка на сервере генерации: {exc}")
    except Exception as exc:  # noqa: BLE001
        logger.exception("Generation failed")
        await message.reply_text(f"Внутренняя ошибка: {exc}")

    context.user_data.clear()
    return ConversationHandler.END


async def receive_last_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    image_b64 = await _download_image_base64(update, context)
    if image_b64 is None:
        if update.message is not None:
            await update.message.reply_text("Нужно прислать изображение: как фото или как документ-картинку, либо /skip.")
        return WAIT_LAST_IMAGE

    context.user_data[DATA_LAST_IMAGE] = image_b64
    return await _submit_and_wait(update, context)


async def skip_last_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop(DATA_LAST_IMAGE, None)
    return await _submit_and_wait(update, context)


def build_application() -> Application:
    app = Application.builder().token(settings.telegram_bot_token).build()

    conversation = ConversationHandler(
        entry_points=[CommandHandler("generate", generate_entry)],
        states={
            WAIT_INPUT_IMAGE: [
                MessageHandler(filters.PHOTO | filters.Document.IMAGE, receive_input_image),
            ],
            WAIT_PROMPT: [
                CommandHandler("skip", skip_prompt),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_prompt),
            ],
            WAIT_DURATION: [
                CommandHandler("skip", skip_duration),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_duration),
            ],
            WAIT_FPS: [
                CommandHandler("skip", skip_fps),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_fps),
            ],
            WAIT_STEPS: [
                CommandHandler("skip", skip_steps),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_steps),
            ],
            WAIT_QUALITY: [
                CommandHandler("skip", skip_quality),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_quality),
            ],
            WAIT_LAST_IMAGE: [
                CommandHandler("skip", skip_last_image),
                MessageHandler(filters.PHOTO | filters.Document.IMAGE, receive_last_image),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(conversation)
    return app


def main() -> None:
    app = build_application()
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
