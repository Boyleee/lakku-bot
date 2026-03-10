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
