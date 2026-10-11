# syntax

Платформа обратного найма для ИТ: подбор по категориям и вакансиям, анонимные карточки, параметрическое тестирование и объяснимый скоринг.

## Что измерено

Четыре воспроизводимых прогона. Числа проверены на синтетике и размеченных парах, собранных командой; это инженерная проверка механик, не рыночное качество подбора.

| Проверка | Результат | Команда |
|---|---|---|
| Подтверждённый профиль против заявленного | 84/84 пар: verified строго выше claimed, равных и проигрышей нет (до правки формулы проигрышей было 24 из 84) | `python -m scripts.validate` |
| Ранжирование на размеченных парах | Precision@5 0.400, NDCG@5 1.000, MRR 1.000 при `hard-gate`; без него NDCG@5 0.693 и MRR 0.500 | `python -m scripts.validate_pairs` |
| Психометрика item bank | Reliability 0.783 при 20 задачах, `separation` 1.901, различимы 2 грейд-полосы из 3 | `python -m scripts.calibrate_items` |
| Тесты | 387 passed, 0 failed, 10 skipped | `python -m pytest tests -q` |

Ключевой эффект — `hard-gate` по тиру: профиль без завершённого теста не обходит подтверждённый ни в одной из 84 пар, а NDCG@5 на размеченном наборе растёт с 0.693 до 1.000. Что именно осталось непроверенным — `docs/limitations.md`.

## Запуск

`.env` подхватывается docker compose автоматически (подробности переменных — `.env.example` и `docs/api.md`):

```
cp .env.example .env
docker compose up --build
docker compose exec api python -m scripts.seed
docker compose exec api python -m scripts.generate_task_pool
docker compose exec api python -m scripts.seed_demo
```

- API: http://localhost:8000
- Swagger: http://localhost:8000/docs
- Фронтенд: http://localhost:3000
- Описание эндпоинтов: `docs/api.md`
- Сопроводительная документация (8 разделов ТЗ): `docs/README.md`
- Демо-сценарий сквозного пути: `docs/demo-script.md`
- Ограничения доказательной базы: `docs/limitations.md`

Демо-данные для проверки: задайте `SEED_DEMO=1` в `.env` (или окружении) перед `docker compose up --build`. Сидирование идемпотентно: повторный старт ничего не дублирует. Без флага база пустая.

### Семантический поиск направлений (embeddings)

Postgres работает на образе `pgvector/pgvector:pg16` с расширением `vector`. Домены и вакансии могут хранить embedding. В vacancy search релевантность объединяет lexical stack intersection (вес 0.3) и косинусную близость (вес 0.7), если вектор актуален; при недоступном провайдере используется lexical fallback.

Embedding-модель настраивается в `.env` и берётся из Cloud.ru Foundation Models (OpenAI-совместимый API):

```
EMBEDDING_BASE_URL=https://foundation-models.api.cloud.ru/v1
EMBEDDING_API_KEY=<ключ Cloud.ru с доступом к Foundation Models>
EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_DIMENSIONS=1024
```

- Ключ создаётся в Cloud.ru: сервис «Foundation Models», время действия — по необходимости.
- Доступные embedding-модели: `BAAI/bge-m3` (внутренняя, русский, 1024), `Qwen/Qwen3-Embedding-0.6B`, `google/gemini-embedding-001`, `openai/text-embedding-3-small`.
- Эмбеддинги включаются, только когда заданы все три: `EMBEDDING_BASE_URL`, `EMBEDDING_API_KEY` и `EMBEDDING_MODEL`. Если хотя бы одно пусто (в том числе пустая модель), поиск работает в лексическом режиме по алиасам и не делает внешних вызовов. Значения по умолчанию для модели нет намеренно: лексический режим — базовый, векторный включается явной настройкой.
- Если модель настроена, но не отвечает (таймаут, ошибка сети, ошибка API), поиск автоматически переходит на лексический режим и возвращает результат по алиасам. Запрос не падает. Это относится и к индексации: без ответа модели домены просто остаются без векторов.
- Векторы доменов считаются при старте API и при создании нового направления.

Что появится после сидирования:

- 100 кандидатов с категориями и завершёнными тест-сессиями, локальные достижения ПВН у части из них
- 3 работодателя, 20 открытых вакансий, 20 приглашений (по одному на каждый статус), 10 откликов, 3 регулярных задания

Вход (пароль у всех аккаунтов `demo-password`):

| Роль | Email | Что смотреть |
|---|---|---|
| Работодатель | `demo-employer@example.com` (также `demo-employer2@`, `demo-employer3@`) | подбор по категориям, поиск, вакансии, отклики, приглашения и статусы, регулярные задания |
| Кандидат | `demo.candidate.001@example.com` ... `demo.candidate.100@example.com` | приглашения, отклики, тест-сессии, профиль и PDF |
| Новый кандидат | любой новый email | регистрация с выбором направления и грейда, подтверждение email, тест |

Сидирование вручную (если `SEED_DEMO` не задан): `docker compose exec api python -m scripts.seed_demo`.

- работодатель: `demo-employer@example.com`
- кандидаты: `demo.candidate.001@example.com` … `demo.candidate.100@example.com`

## Локальная разработка

```
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn backend.main:app --reload
```

Фронтенд:

```
cd frontend && npm ci && npm run dev
```

Схема создаётся самим приложением: при старте API выполняет `CREATE EXTENSION IF NOT EXISTS vector` и `Base.metadata.create_all`. Поэтому на чистом томе достаточно `docker compose up --build` — отдельный шаг миграций не нужен.

Alembic используется при развитии схемы на уже работающей базе:

```
DATABASE_URL=postgresql+psycopg://syntax:syntax@localhost:5432/syntax alembic upgrade head
```

Не запускайте `alembic upgrade head` на пустой базе до старта API: таблицы создаст приложение, и миграция упрётся в `relation already exists`.

## Скрипты

| Скрипт | Назначение |
|---|---|
| `scripts/seed.py` | банк концептов (107) и словарь контекстов генерации |
| `scripts/generate_task_pool.py` | fallback-пул 240 предгенерированных задач |
| `scripts/generate_synthetic.py` | 100 синтетических кандидатов, 20 вакансий для демо |
| `scripts/seed_demo.py` | полный демо-сид + идемпотентный добор полей профиля и подтверждения грейда |
| `scripts/backfill_grade_confirmation.py` | проставить `grade_confirmed_at` по завершённым сессиям на существующей базе |
| `scripts/validate.py` | проверка пар verified/claimed и hard-gate, отчёт в `docs/validation-results.md` |
| `scripts/validate_pairs.py` | Precision@5/NDCG@5/MRR на размеченном наборе пар, отчёт в `docs/pairs-results.md` |
| `scripts/calibrate_items.py` | IRT-калибровка item bank, отчёт в `docs/psychometrics-results.md` |
| `scripts/e2e_docker.py` | сквозной e2e-прогон против docker compose |
| `scripts/build_docs_pdf.py` | сборка сопроводительной документации в PDF |
| `scripts/build_pitch.py` | сборка презентации по шаблону ПВН |

## Библиотеки и лицензии

| Библиотека | Лицензия |
|---|---|
| fastapi, uvicorn, starlette | BSD-3-Clause |
| sqlalchemy, alembic | MIT |
| psycopg | LGPL-3.0 |
| pydantic, pydantic-settings | MIT |
| PyJWT | MIT |
| passlib, bcrypt | BSD / Apache-2.0 |
| pypdf | BSD-3-Clause |
| reportlab | BSD-3-Clause |
| httpx | BSD-3-Clause |
| pytest | MIT |
