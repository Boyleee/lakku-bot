# Деплой RunPod воркера из GitHub

Ниже шаги именно для сценария: **RunPod собирает image из вашего GitHub репозитория и пути к Dockerfile**.

## 1. Подготовьте репозиторий
Убедитесь, что в репозитории есть файлы:
- `services/runpod-worker/Dockerfile`
- `services/runpod-worker/handler.py`
- `services/runpod-worker/generation.py`
- `services/runpod-worker/aoti.py`
- `services/runpod-worker/requirements.txt`
- `services/runpod-worker/model/...`

## 2. Создайте/обновите Serverless Endpoint в RunPod
В форме сборки контейнера укажите:
- `Source Type`: `GitHub`
- `Repository URL`: `https://github.com/<you>/<repo>`
- `Branch`: `main` (или ваш branch)
- `Dockerfile Path`: `services/runpod-worker/Dockerfile`
- Если есть `Build Context Path`: `.`

После сохранения дождитесь завершения build/deploy.

Важно:
- Текущий `Dockerfile` поддерживает оба варианта context:
  - `.` (корень репозитория)
  - `services/runpod-worker`
- Ошибка вида `runpod/pytorch:...: not found` означает невалидный тег базового образа. В текущем репозитории уже используется рабочий тег.
- Для совместимости с Python 3.12 в текущем base image:
  - установка зависимостей выполняется через `pip --no-build-isolation`
  - `numpy` задан с маркерами версий (для `py<3.12` и `py>=3.12`)
- В Docker build добавлена автоматическая проверка импортов критичных модулей воркера.
  Если не хватает зависимости, сборка завершится ошибкой с полным списком модулей.
- По хранилищу: эта модель занимает десятки гигабайт.
  Практический минимум свободного места для старта: `70-80 GB`.
  При 5 GB воркер не сможет загрузить веса (ошибка `No space left on device`).

## 3. Подключите endpoint к VPS части (bot + backend)
На VPS в `.env`:
- `RUNPOD_API_KEY=<ваш runpod api key>`
- `RUNPOD_ENDPOINT_ID=<id endpoint из RunPod>`

Перезапустите сервисы:
```bash
docker compose up -d --build
```

## 4. Минимальная проверка
1. В Telegram откройте бота.
2. Выполните `/generate`.
3. Пройдите 7 шагов диалога.
4. Убедитесь, что видео вернулось в чат.

Если задача зависает:
- проверьте логи backend (`docker compose logs -f backend`)
- проверьте состояние endpoint/build в RunPod UI
- убедитесь, что `RUNPOD_ENDPOINT_ID` и `RUNPOD_API_KEY` актуальные

## Частая ошибка: 403 Forbidden
Если backend показывает `403 Forbidden` на `.../v2/<endpoint>/run`, почти всегда это:
- неверный `RUNPOD_API_KEY`
- ключ без нужных прав для serverless run
- ключ из другого workspace/org

Проверка с VPS:
```bash
curl -i -X POST "https://api.runpod.ai/v2/<endpoint_id>/run" \
  -H "Authorization: Bearer <runpod_api_key>" \
  -H "Content-Type: application/json" \
  -d '{"input":{"ping":"ok"}}'
```

Ожидаемо:
- `200/202` -> доступ к endpoint есть
- `401/403` -> проблема в ключе/правах/workspace
