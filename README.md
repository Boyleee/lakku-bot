# lakku-bot

Полноценный MVP из двух частей:
- `services/bot` — Telegram-бот с русским интерфейсом.
- `services/backend` — API/очередь, которая отправляет задачи в RunPod.
- `services/runpod-worker` — воркер Wan2.2 I2V (логика генерации перенесена из HF Space).

## Что уже реализовано
- Сценарий бота: загрузка исходного фото, промпт, длительность, FPS, inference steps, video quality, опциональный last image.
- Дефолты и диапазоны — из исходного HF Space.
- Backend создает задачу, опрашивает RunPod и отдает видео боту.
- Воркер готов к сборке в RunPod из GitHub по пути к Dockerfile.

## 1) Запуск бота и backend на VPS

1. Скопируйте переменные окружения:
```bash
cp .env.example .env
```

2. Заполните `.env`:
- `TELEGRAM_BOT_TOKEN`
- `RUNPOD_API_KEY`
- `RUNPOD_ENDPOINT_ID`

3. Поднимите сервисы:
```bash
docker compose up --build -d
```

4. Проверьте backend:
```bash
curl http://localhost:8000/healthz
```

## 2) Деплой RunPod воркера из GitHub (как вы и хотите)

В RunPod Serverless при создании/редактировании endpoint укажите:
- **Source Type**: `GitHub`
- **Repository URL**: `https://github.com/<ваш-аккаунт>/<ваш-репозиторий>`
- **Branch**: `main` (или ваш рабочий branch)
- **Dockerfile Path**: `services/runpod-worker/Dockerfile`
- Если есть поле **Build Context Path**: `.` (корень репозитория)

Требование по диску:
- для модели `TestOrganizationPleaseIgnore/WAMU_v2_WAN2.2_I2V_LIGHTNING` нужно существенно больше 5 GB
- ориентир: минимум `70-80 GB` свободного места под кэш/загрузку модели
- при наличии volume лучше использовать его как кэш (`WAN22_CACHE_DIR=/runpod-volume/hf-cache`)

Требование по GPU:
- текущий воркер зафиксирован под `NVIDIA A100 (SM 8.0)` и не запускается на других GPU
- путь генерации детерминированный и фиксированный: `BF16` без квантования и без runtime fallback
- seed по умолчанию фиксирован (`WAN22_DEFAULT_SEED`, по умолчанию `42`)

Почему так: Dockerfile воркера настроен на сборку из контекста корня репозитория и копирует файлы через `services/runpod-worker/...`.

Если раньше вы видели ошибку `runpod/pytorch:...: not found`, это было из-за несуществующего base image тега. В актуальном `Dockerfile` это исправлено.
Если видели ошибку `pkgutil.ImpImporter` на шаге `pip install`, это исправлено в текущем `Dockerfile` (обновление pip/setuptools/wheel + `--no-build-isolation`).

После сборки и запуска endpoint:
1. Скопируйте `Endpoint ID`.
2. Вставьте его в `.env` на VPS (`RUNPOD_ENDPOINT_ID`).
3. Перезапустите backend+bot:
```bash
docker compose up -d --build
```

Если получаете `403 Forbidden` при генерации, проверьте `RUNPOD_API_KEY` (права и workspace) и `RUNPOD_ENDPOINT_ID`. Детальный разбор: `docs/DEPLOY_RUNPOD_GITHUB_RU.md`.

## 3) Локальная проверка

Проверка синтаксиса:
```bash
python3 -m compileall services
```

Проверка тестов backend:
```bash
python3 -m pip install -r services/backend/requirements.txt
python3 -m pip install pytest
pytest services/backend/tests -q
```

## Полезные файлы
- Архитектура: `docs/ARCHITECTURE.md`
- Пошаговый деплой RunPod из GitHub: `docs/DEPLOY_RUNPOD_GITHUB_RU.md`
- Compose: `docker-compose.yml`
- Переменные окружения: `.env.example`
