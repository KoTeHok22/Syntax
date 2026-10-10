# API — syntax

REST API платформы. Интерактивная документация (Swagger UI): `/docs`, спецификация OpenAPI: `/openapi.json`.

- Базовый URL при локальном запуске: `http://localhost:8000`
- Формат: JSON (кроме `GET /candidates/me/profile.pdf`)
- Аутентификация: Bearer JWT в заголовке `Authorization: Bearer <token>`
- Токен содержит OIDC-совместимые claims: `sub`, `email`, `role`, `pvn_id`, `iss`, `exp`

## Роли

| Роль | Назначение |
|---|---|
| `candidate` | кандидат: профиль, тестирование, приглашения, отклики, регулярные задания |
| `employer` | работодатель: категории, анонимные карточки, приглашения, вакансии, регулярные задания |

Роль фиксируется при регистрации и проверяется на каждом защищённом эндпоинте (403 при несоответствии).

## Сквозной пример

```
POST /auth/register (candidate) → GET /auth/confirm/{token} → POST /auth/login
→ PUT /candidates/me → PUT /candidates/me/grade
→ POST /test-sessions → POST /test-sessions/{id}/answers
→ [работодатель] GET /employer/categories → GET /employer/categories/{id}/cards
→ POST /invitations → [кандидат] POST /invitations/{id}/accept → контакты раскрыты
```

## Health

### GET /health
Доступ: без аутентификации. Ответ: `{"status": "ok"}`.

## Аутентификация

### POST /auth/register
Доступ: открытый. Тело:

```json
{
  "email": "user@example.com",
  "password": "password123",
  "role": "candidate",
  "consent_accepted": true,
  "pvn_id": "PVN-100001"
}
```

- `consent_accepted` обязателен (`true`) — согласие на обработку персональных данных (152-ФЗ); при `false` — 400
- `role`: `candidate` или `employer`; `pvn_id` необязателен
- Ответ 201: `{"id", "email", "role", "is_email_confirmed", "confirmation_url"}`
- `confirmation_url` возвращается только когда SMTP не настроен (dev-режим); в продакшене письмо уходит на email
- 409 — email уже зарегистрирован

### GET /auth/confirm/{token}
Доступ: открытый (переход из письма). Подтверждает email. Ответ: `{"email", "is_email_confirmed": true}`. 404 — токен не найден.

### POST /auth/login
Доступ: открытый. Тело: `application/x-www-form-urlencoded` (`username`, `password`).

- Ответ: `{"access_token", "token_type": "bearer", "role"}`
- 401 — неверные данные; 403 — email не подтверждён

### GET /auth/me
Доступ: любая роль. Ответ: `{"id", "email", "role", "pvn_id", "is_email_confirmed"}`.

`pvn_id` — необязательный идентификатор участника ПВН. Он уникален: повторная привязка того же ID к другому аккаунту возвращает 409. Наличие `pvn_id` даёт отметку подтверждения в профиле и карточке кандидата.

## Профиль кандидата

### GET /candidates/me
Доступ: candidate. Полный профиль, включая контакты (владелец). Содержит `pvn_id` и `is_pvn_verified`.

### PUT /candidates/me
Доступ: candidate. Тело (все поля опциональны). `pvn_id` можно задать или очистить пустой строкой; занятый другим аккаунтом ID даёт 409.

```json
{
  "full_name": "Иван Кандидатов",
  "contacts": {"email": "ivan@example.com", "phone": "+79000000000"},
  "stack": ["python", "fastapi"],
  "years_of_experience": 2,
  "soft_skills": ["командная работа"],
  "specialization": "backend",
  "city": "Москва",
  "work_format": "hybrid"
}
```

`work_format` — `remote` / `office` / `hybrid` (или пустая строка). Город и формат видны работодателю в карточке и детальном профиле; они не идентифицируют личность и потому безопасны для слепого найма (в отличие от ФИО, контактов и аватара, которые в выдаче работодателя не показываются).

При заполненных `specialization` и `grade` кандидат автоматически попадает в категорию.

### PUT /candidates/me/grade
Доступ: candidate. Тело: `{"grade": "junior" | "middle" | "senior"}`.

- Грейд не понижается принудительно — смена только по решению кандидата
- Кулдаун 3 месяца (конфигурируется `GRADE_COOLDOWN_MONTHS`): повторная смена раньше срока — 409
- Меняет категорию кандидата

### PUT /candidates/me/visibility
Доступ: candidate. Тело: `{"is_visible": false}`. Скрытый кандидат не попадает в выдачу работодателю (категории, поиск).

### POST /candidates/me/resume
Доступ: candidate. `multipart/form-data`, поле `file` — PDF-резюме.

- Извлечённый текст резюме разбирается LLM на поля профиля, найденные поля применяются
- Требуется настроенный LLM (без него ответ содержит пустой `applied`)
- 400 — файл не является корректным PDF или без текста

### GET /candidates/me/profile.pdf
Доступ: candidate. Стандартизированный PDF-профиль: данные, история тестирования, достижения ПВН. Ответ: `application/pdf`.

## Профиль работодателя

### GET /employers/me и PUT /employers/me
Доступ: employer. Тело PUT: `{"company_name", "description", "contacts"}`.

## Категории и подборка

### GET /employer/categories
Доступ: employer. Параметры: `specialization`, `grade`. Ответ — категории с числом видимых кандидатов:

```json
[{"id": 1, "specialization": "backend", "grade": "junior", "candidate_count": 47}]
```

### GET /employer/categories/{category_id}/cards
Доступ: employer. Анонимизированные карточки кандидатов категории — без имени, контактов и прочих идентифицирующих данных. Параметры:

| Параметр | Тип | Описание |
|---|---|---|
| `stack` | список строк | требуемый стек; задаёт `match_relevance` — долю совпадения |
| `has_pvn` | bool | только с историей ПВН / только без |
| `verified_only` | bool | только карточки с подтверждённым ПВН |
| `min_score` | float 0–100 | нижняя граница скоринга |
| `city` | строка | город кандидата (точное совпадение без регистра) |
| `work_format` | строка | формат работы: `remote` / `office` / `hybrid` |
| `skip`, `limit` | int | пагинация (по умолчанию 0/50, максимум 200) |

Ранжирование: `final_score = score + match_relevance × 20`, сортировка по ключу `(proof_tier, final_score, score)`. Ответ:

```json
[{
  "candidate_profile_id": 12,
  "grade": "middle",
  "specialization": "backend",
  "city": "Москва",
  "work_format": "hybrid",
  "stack": ["python", "postgresql"],
  "score": 78.5,
  "score_breakdown": {
    "test_score": {"label": "Результат тестирования", "value": 80, "weight": 0.8},
    "pvn_achievements": {"label": "Достижения ПВН", "value": 35, "weight": 0.3},
    "profile_completeness": {"label": "Полнота профиля", "value": 100, "weight": 0.1}
  },
  "has_pvn_history": true,
  "is_pvn_verified": true,
  "pvn_achievements": [{"type": "хакатон", "level": "победитель", "date": "2026-05-01", "score": 35.0}],
  "match_relevance": 1.0,
  "final_score": 98.5,
  "match_breakdown": {"stack": 1.0, "semantic": null, "mode": "lexical", "stack_weight": 1.0, "semantic_weight": 0.0, "relevance": 1.0, "overlap": {"matched_total": 2, "required_total": 2, "matched": ["python", "postgresql"], "missing": []}},
  "proof_tier": "verified",
  "is_verified": true
}]
```

Скоринг объясним: `score = Σ(компонент × вес)`. Отсутствующие компоненты (нет истории ПВН, нет завершённой тест-сессии) исключаются, веса перенормируются на их сумму — карточка без достижений ПВН показывает пометку `has_pvn_history: false`.

**Proof-тиры.** `proof_tier` = `verified` при наличии завершённой тест-сессии и `claimed` — иначе; `is_verified` — булев дубль этого признака. Сортировка выдачи идёт по ключу `(proof_tier, final_score, score)` по убыванию: сначала `verified`, внутри тира — по `final_score`, при равенстве — по `score`.

**Соответствие потребности.** `match_relevance` (0.0–1.0) — аддитивная надбавка до +20 баллов (`final_score = score + match_relevance × 20`), а не множитель. Порог допуска `match_relevance ≥ 0.2` применяется при явном включении фильтра по релевантности. `match_breakdown` объясняет режим и состав совпадения: `mode` = `semantic` при доступном embedding и `lexical` иначе; `overlap` несёт `matched_total`, `required_total`, `matched`, `missing`.

### GET /employer/search
Доступ: employer. Поиск по всему банку кандидатов. Параметры: `specialization`, `grade`, `stack`, `has_pvn`, `verified_only`, `min_score`, `city`, `work_format`, `skip`, `limit`. Формат ответа — как у карточек.

### GET /employer/candidates/{candidate_profile_id}
Доступ: employer. Детальный **анонимный** профиль кандидата. Даёт больше, чем карточка списка: разбивку стека по навыкам (`stack_proof`), опыт, софт-скиллы, город и формат работы, разбор скоринга и укрупнённые достижения ФСП. Не отдаёт идентифицирующих данных.

Параметры:

| Параметр | Тип | Описание |
|---|---|---|
| `candidate_profile_id` | int (path) | ID профиля кандидата |
| `vacancy_id` | int (query, опц.) | вакансия владельца; при ней считается `match_relevance` |

Правила ответа:

- 404 — кандидат не существует, скрыт (`is_visible = false`) или не проходит демо-фильтр; «пустого» профиля не бывает;
- 403 — роль не `employer`;
- `match_relevance` — `null` без `vacancy_id`; заполняется близостью по той же логике, что и карточка;
- **чего в ответе нет:** `full_name`, `contacts`, `avatar_data_url`, `resume_text`, `pvn_id` — эти поля не входят в схему `CandidatePublicProfileResponse`;
- достижения ФСП сведены к `{type, level}` — без даты и балла (анти-де-анимизация в узких нишах, см. `docs/03-matching-mechanics.md`).

```json
{
  "candidate_profile_id": 12,
  "grade": "middle",
  "specialization": "backend",
  "stack_proof": [
    {"stack": "python", "domain": "backend", "proof": "verified"},
    {"stack": "postgresql", "domain": "databases", "proof": "verified"},
    {"stack": "react", "domain": null, "proof": "claimed"}
  ],
  "years_of_experience": 3.0,
  "soft_skills": ["командная работа"],
  "city": "Москва",
  "work_format": "hybrid",
  "proof_tier": "verified",
  "is_verified": true,
  "score": 78.5,
  "score_breakdown": {
    "test_score": {"label": "Результат тестирования", "value": 80, "weight": 0.8},
    "pvn_achievements": {"label": "Достижения ПВН", "value": 35, "weight": 0.3},
    "profile_completeness": {"label": "Полнота профиля", "value": 100, "weight": 0.1}
  },
  "match_relevance": 0.66,
  "pvn_achievements": [{"type": "хакатон", "level": "победитель"}]
}
```

`proof` по навыку: `verified` — домен навыка подтверждён корректным ответом в последней завершённой тест-сессии, `claimed` — иначе (`domain: null`); механика — `docs/02-testing-mechanics.md`. В примере с `?vacancy_id` заполнено; без него `match_relevance` — `null`.

## Приглашения

Статусы: `sent` → `viewed` → `accepted` / `rejected`. Зарплата («от–до», рубли) обязательна. Контакты кандидата скрыты до принятия приглашения обеими сторонами.

### POST /invitations
Доступ: employer. Тело:

```json
{
  "candidate_profile_id": 12,
  "message": "Приглашаем в команду",
  "salary_from": 150000,
  "salary_to": 200000,
  "company_name": "ООО Пример",
  "contact_method": "hr@example.com"
}
```

- 422 — `salary_to < salary_from` или отрицательные значения
- Ответ 201: приглашение; `candidate_contacts: null` (скрыто)
- Кандидат видит предложение целиком, включая зарплату, до начала общения

### GET /invitations/incoming
Доступ: candidate. Входящие приглашения с условиями и зарплатой. Параметры: `skip`, `limit` (по умолчанию 0/50, максимум 200).

### GET /invitations/sent
Доступ: employer. Отправленные; `candidate_contacts` раскрывается только в статусе `accepted`. Параметры: `skip`, `limit` (по умолчанию 0/50, максимум 200).

Оба списка возвращают `created_at`, `viewed_at`, `responded_at` — реальные метки переходов, из которых обе роли строят статусную ленту «Отправлено → Просмотрено → Принято». Лента не выдумывает даты: если перехода не было, поле `null`.

### POST /invitations/{id}/view
Доступ: candidate (адресат). Переводит `sent` → `viewed`, записывает `viewed_at`. Идемпотентен.

### POST /invitations/{id}/accept
Доступ: candidate (адресат). Переводит `viewed` → `accepted`, записывает `responded_at`, после чего контакты кандидата видны обеим сторонам как событие «Контакты открыты». 409 — недопустимый переход (`sent → accepted` запрещён напрямую, требуется предварительный просмотр).

### POST /invitations/{id}/reject
Доступ: candidate (адресат). Переводит `sent`/`viewed` → `rejected`, записывает `responded_at`.

## Тестирование

### POST /test-sessions
Доступ: candidate. Тело: `{"grade": "junior" | "middle" | "senior"}`.

Создаёт сессию на `TASKS_PER_SESSION` задач грейда (по умолчанию 20). Задачи уникальны по формулировке: LLM-генерация → fallback-пул → детерминированная генерация по якорям сложности концепта. Ответ содержит задачи (`statement`, `options`) без эталонных ответов.

Активная незавершённая сессия возвращается повторно вместо создания новой.

### GET /test-sessions и GET /test-sessions/{id}
Доступ: candidate. История сессий и детали.

### POST /test-sessions/{id}/answers
Доступ: candidate. Тело — список ответов:

```json
[{"task_id": 101, "option_index": 2}, {"task_id": 102, "option_index": 0}]
```

Завершает сессию. Ответ:

```json
{
  "id": 5,
  "grade": "junior",
  "task_count": 5,
  "correct_count": 4,
  "result_score": 80,
  "verdict": "suggest_higher",
  "suggested_grade": "middle"
}
```

- Вердикт считается по доле верных ответов (`backend/core/testing.py`): доля ≥ 0.95 → `suggest_higher` (предложение, не принуждение); доля ≥ порога грейда (`pass_ratio`: junior 0.60, middle 0.75, senior 0.85; без грейда — 0.80) → `confirmed`; иначе → `suggest_lower`
- Все значения верных считаются от `task_count` (по умолчанию 20): например, 19/20 → `suggest_higher`, 15/20 → `confirmed`, 11/20 → `suggest_lower`
- 409 — сессия уже завершена; 400 — задачи не принадлежат сессии

## Вакансии

### POST /vacancies
Доступ: employer. Тело: `title`, `description`, `stack`, `specialization`, `grade`, `salary_from`, `salary_to` (зарплата обязательна, 422 при инверсии диапазона).

### GET /vacancies
Доступ: открытый. Открытые вакансии. Параметры: `grade`, `specialization`, `skip`, `limit` (по умолчанию 0/50, максимум 200).

### GET /vacancies/my
Доступ: employer. Свои вакансии, включая закрытые, новые сверху. Параметры: `skip`, `limit` (по умолчанию 0/50, максимум 200).

### GET /vacancies/{id}
Доступ: открытый.

### PUT /vacancies/{id}
Доступ: employer (владелец). Редактирование вакансии. Тело — полный набор полей, как у POST /vacancies. Статус вакансии не меняется. 404 — вакансия не найдена или чужая; 422 — инверсия диапазона зарплаты.

### POST /vacancies/{id}/close
Доступ: employer (владелец). Закрывает вакансию.

## Отклики

Статусы: `new` → `viewed` → `accepted` / `rejected` (управляет работодатель).

### POST /applications
Доступ: candidate. Тело: `{"vacancy_id": 3, "message": "Отклик"}`. 409 — повторный отклик на ту же вакансию.

### GET /applications/my
Доступ: candidate. Свои отклики со статусами. Параметры: `skip`, `limit` (по умолчанию 0/50, максимум 200).

### GET /applications/incoming
Доступ: employer. Отклики на свои вакансии. Параметры: `skip`, `limit` (по умолчанию 0/50, максимум 200).

### PUT /applications/{id}/status
Доступ: employer (владелец вакансии). Тело: `{"status": "viewed" | "accepted" | "rejected"}`.

### PUT /applications/{id}/interview
Доступ: employer (владелец вакансии). Назначает интервью по принятому отклику. Тело:

```json
{"scheduled_at": "2026-10-20T14:30:00Z", "duration_minutes": 60, "format": "video", "link": "https://meet.example.com/x"}
```

`format` — `video` / `onsite` / `phone`; вместо `link` можно указать `address`. 409 — отклик ещё не принят; 422 — дата в прошлом. Кандидат видит назначенное интервью в «Моих откликах» как блок «Приглашение на интервью» с датой, длительностью, форматом и ссылкой.

## Задания к вакансии

Проверочные задания работодателя, привязанные к вакансии. Кандидат получает их после отклика и проходит под прокторингом, как тестирование. В сквозной балл кандидата задания не входят: результат виден работодателю в отклике по конкретной вакансии.

### POST /regular-tasks
Доступ: employer (владелец вакансии). Два способа, в обоих обязателен `vacancy_id`:

```json
{"vacancy_id": 3, "concept_id": 7}
```

```json
{"vacancy_id": 3, "statement": "Выберите верное утверждение", "options": ["да", "нет"], "correct_index": 0}
```

Вариант с концептом генерирует формулировку (LLM → fallback). 404 — вакансия не принадлежит работодателю. 422 — некорректная комбинация полей.

### GET /regular-tasks/vacancy/{vacancy_id}
Доступ: candidate. Сводка по вакансии: число заданий и статус прохождения. 404 — у кандидата нет отклика на вакансию.

### POST /regular-tasks/vacancy/{vacancy_id}/session
Доступ: candidate. Начинает или продолжает попытку. Возвращает задания и `expires_at`. 404 — нет отклика или нет активных заданий. 409 — попытка уже завершена.

### POST /regular-tasks/sessions/{session_id}/answers
Доступ: candidate. Тело: `[{"regular_task_id": 1, "option_index": 0}]`. Одна попытка, повтор 409. Досрочное завершение (выход из fullscreen, потеря фокуса, истечение таймера) помечается `forced_finish`. Ответ: `{id, status, task_count, correct_count, result_score, forced_finish}`.

### GET /employer/regular-tasks
Доступ: employer. Свои задания, фильтр `?vacancy_id=`.

### GET /employer/regular-tasks/results
Доступ: employer (владелец вакансии). Результаты откликнувшихся кандидатов: `?vacancy_id=`.

### POST /employer/regular-tasks/{id}/close
Доступ: employer (владелец). Деактивирует задание.

## Коды ошибок

| Код | Ситуация |
|---|---|
| 400 | некорректный ввод (нет согласия 152-ФЗ, битый PDF) |
| 401 | нет/недействительный токен, неверный логин или пароль |
| 403 | неверная роль, неподтверждённый email |
| 404 | объект не найден или не принадлежит вызывающему |
| 409 | конфликт состояния: кулдаун грейда, повторный отклик/ответ, недопустимый переход статуса, занятый email |
| 422 | нарушение валидации схемы (диапазон зарплаты, состав полей) |

## Переменные окружения

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://syntax:syntax@db:5432/syntax` | подключение к БД |
| `JWT_SECRET` | dev-значение | подпись токенов (обязательно сменить в продакшене) |
| `JWT_EXPIRES_MINUTES` | 60 | срок жизни токена |
| `GRADE_COOLDOWN_MONTHS` | 3 | кулдаун смены грейда |
| `TASKS_PER_SESSION` | 20 | число задач в тест-сессии |
| `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` | пусто | OpenAI-совместимый провайдер генерации задач и парсинга резюме |
| `LLM_TIMEOUT_SECONDS` | 240 | таймаут запроса к LLM (думающие модели отвечают дольше минуты) |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` | пусто | отправка писем подтверждения |
| `APP_BASE_URL` | `http://localhost:8000` | база ссылок в письмах |
| `CORS_ORIGINS` | localhost:3000/5173 | разрешённые источники фронтенда |
### POST /auth/pvn

Обмен проверенного Keycloak/PVN OIDC bearer-токена на локальную сессию Syntax. Тело: `access_token`, `consent_accepted`; внешний issuer, audience, JWKS и claims проверяются по настройкам сервера. Внешний email не используется для автоматической привязки к локальному аккаунту.

Параметр `vacancy_id` включает подбор по вакансии владельца: 30% пересечения стека и 70% косинусной близости векторов вакансии и профиля. При недоступном embedding-провайдере ответ содержит `match_breakdown.mode=lexical`.

Ответ содержит `ats_delivery_status`, `ats_delivery_attempts`, `ats_delivery_error`, `ats_delivered_at`.

### ATS

- `GET /ats/config` — текущий адрес, доступные администраторские HTTPS-адреса и флаги подключения; секреты не возвращаются.
- `PUT /ats/config` — выбрать адрес из allowlist.
- `POST /ats/webhook` — повторить передачу только принятого отклика владельца вакансии.
