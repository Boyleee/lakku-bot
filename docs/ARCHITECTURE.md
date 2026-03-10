# Архитектура Wan2.2 Telegram проекта

## Цель
Разделить систему на 2 отдельные части:
- Part 1: Telegram-бот + backend на VPS.
- Part 2: GPU-генерация на RunPod endpoint.

Логика генерации должна совпадать с HF Space:
- [r3gm/wan2-2-fp8da-aoti-preview](https://huggingface.co/spaces/r3gm/wan2-2-fp8da-aoti-preview)

## Сервисы

### Part 1 (VPS)
- `services/bot` — Telegram UX (FSM-диалог, сбор параметров).
- `services/backend` — REST API для создания задач, интеграция с RunPod, выдача видео.

### Part 2 (RunPod)
- `services/runpod-worker` — serverless handler + inference pipeline.

## Поток запроса
1. Пользователь запускает `/generate`.
2. Бот собирает параметры.
3. Бот вызывает `POST /api/v1/jobs` backend.
4. Backend отправляет `run` в RunPod, потом опрашивает `status/{id}`.
5. RunPod возвращает `video_base64` и метаданные.
6. Backend хранит результат задачи (MVP: в памяти) и отдает видео через `/api/v1/jobs/{job_id}/video`.
7. Бот отправляет mp4 пользователю в Telegram.

## Паритет с HF Space
В worker перенесены:
- модель: `TestOrganizationPleaseIgnore/WAMU_v2_WAN2.2_I2V_LIGHTNING`
- дефолтный prompt
- фиксированный negative prompt
- `scheduler=UniPCMultistep`, `flow_shift=3.0`
- `guidance_scale=1.0`, `guidance_scale_2=1.0`
- resize/crop логика
- формула кадров: `1 + clip(round(duration * 16), 8, 160)`
- RIFE интерполяция для FPS выше 16
- экспорт в mp4 через `export_to_video(..., quality=...)`

## Профиль рантайма
- Текущая конфигурация воркера зафиксирована под `NVIDIA A100 (SM 8.0)`.
- Путь инференса детерминированный: фиксированный режим `BF16` (без квантования) и фиксируемый seed по умолчанию (`WAN22_DEFAULT_SEED=42`).

## Ограничения MVP
- Backend хранит задачи и видео в памяти процесса.
- Для production лучше заменить хранение на Redis/Postgres + объектное хранилище.
