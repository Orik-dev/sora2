📖 README — Veo 3 Studio Bot
🚀 О проекте

Veo 3 Studio Bot — Telegram-бот для генерации AI-видео (Text-to-Video и Image-to-Video) на модели Veo 3.
Оплаты: 🇷🇺 YooKassa, 🌍 Sokin Pay.
Инфраструктура уровня продакшн с безопасными вебхуками, очередями и дедупликацией.

⚙️ Технологический стек

FastAPI, aiogram==3.20.0.post0, uvicorn[standard], gunicorn
mysql (SQLAlchemy 2.x + aiomysql), redis, arq==0.25.0
httpx, python-dotenv, Pillow
nginx (reverse proxy) + Cloudflare (WAF/SSL)
Платежи: 🇷🇺 YooKassa, 🌍 Sokin Pay
Генерация: Kie AI (Veo 3 / veo3_fast)

🧭 Пользовательский сценарий (коротко)

/start → выбор языка RU/EN (инлайн-кнопки) → приветствие + CTA:
«📸 Изображение → Видео», «📝 Текст → Видео», «💳 Купить 1 видео», «🎁 Пакеты», «📂 Мои видео»

Генерация:

Image-to-Video → запросить aspect ratio (16:9/9:16) и режим (veo3_fast/veo3), опционально watermark.

Text-to-Video → то же самое.

Создать generation_task → очередь arq → POST /api/v1/veo/generate

Оплата:

Buy once (разовая) — покупка 1 или N видео без пополнения общего баланса

Buy package — пакет на 5/10/20 видео (дешевле за штуку)

🇷🇺 YooKassa / 🌍 Sokin Pay → редирект на платёжную страницу → вебхук меняет статус payments → начисление/списание credits

Вебхуки:

Платежные вебхуки → обновляют payments.status и кредиты

KieAI callback → обновляет generation_tasks + выдаёт resultUrls (и, если нужно, запрашиваем 1080p)


app/
  main.py                 # FastAPI (lifespan, include_routers)
  core/                   # инфраструктура: настройки/логгер/БД/Redis
    settings.py
    logger.py
    db.py
    redis.py
  api/                    # HTTP-контракты (FastAPI routers + Pydantic schemas)
    routers/
      telegram.py         # /webhook/telegram (проверка Secret Token)
      yookassa.py         # /webhook/yookassa (подпись/идемпотентность)
      sokin.py            # /webhook/sokin   (подпись/идемпотентность)
      veo_callback.py     # /webhook/veo-callback?token=
      payments.py         # создание платежей/линков (Buy once / Packages)
      videos.py           # мои видео, статусы задач
      health.py           # /healthz, /readinessz
    schemas/
      payments.py
      videos.py
      common.py
  bot/                    # Telegram-логика (aiogram 3)
    init.py               # bot, dp, middlewares
    handlers/
      start.py            # выбор языка RU/EN, приветствие, меню
      image.py            # Image-to-Video
      text.py             # Text-to-Video
      plans.py            # Buy once / Packages
      my_videos.py        # список задач/результатов
    keyboards/
      common.py
    i18n/
      en.json
      ru.json
  domain/                 # бизнес-логика (чистые сервисы)
    payments/
      service.py          # create_payment, apply_payment, credits
      providers/
        yookassa.py
        sokin.py
    generation/
      service.py          # submit_task, finalize, get_1080p
      clients/
        kie_ai.py         # httpx клиент к KieAI (generate/record-info/1080p)
    users/
      service.py
  repos/                  # доступ к MySQL (SQLAlchemy 2.0)
    db.py
    users.py
    payments.py
    tasks.py
    credits.py
  models/                 # SQLAlchemy-модели
    user.py
    payment.py
    payment_item.py
    generation_task.py
    credit_ledger.py
  workers/                # фоновые задачи (ARQ)
    arq_worker.py
    jobs/
      generate.py         # вызов KieAI generate
      poll.py             # опциональный поллинг
      fetch_1080p.py
      notify.py           # уведомления/доставки ссылок
  middleware/
    error_handler.py
    request_id.py         # X-Request-ID в логи
    locale.py
  utils/
    idempotency.py        # Redis SETNX helpers
    urls.py               # rstrip('/'), сборка webhook URL
