# Сопроводительная документация — Syntax

Платформа обратного найма ИТ-специалистов с верифицированным профилем достижений ПВН (хакатон ПВН). Документация соответствует п. 3.4 ТЗ (8 разделов). Документация собирается локально `python -m scripts.build_docs_pdf`, в репозиторий не входит.

## Карта разделов

| Раздел ТЗ | Файл | Содержание |
|---|---|---|
| 1. Функциональная и компонентная архитектура | [01-architecture.md](01-architecture.md) | обзор решения, диаграмма компонентов, модули backend, структура frontend, модель данных, docker-compose, безопасность |
| 2. Механика тестирования и устойчивость к утечке | [02-testing-mechanics.md](02-testing-mechanics.md) | банк концептов с якорями сложности, каскад генерации (LLM → пул 240 → seed), обоснование устойчивости, адаптивный алгоритм, регулярные задания |
| 3. Механика подбора и категоризация | [03-matching-mechanics.md](03-matching-mechanics.md) | категория = специализация × грейд, анонимные карточки, формула скоринга с перенормировкой, ранжирование, фильтры, приглашения, вакансии/отклики |
| 4. Процедура валидации и результаты | [04-validation.md](04-validation.md) | синтетический adversarial suite, ограничения, воспроизведение и отдельные PostgreSQL/pgvector проверки |
| 5. Схема интеграции с реестром ПВН | [05-pvn-integration.md](05-pvn-integration.md) | текущее состояние (OIDC-совместимые claims), таблица соответствия полей, вебхуки достижений, SSO Keycloak |
| 6. За рамками MVP: антифрод и ATS | [06-antifraud-ats.md](06-antifraud-ats.md) | концепция верификации работодателей, грейды доверия, депозиты, REST/Webhook ATS-интеграция |
| 7. Сборка, развёртывание, локальный запуск | [07-deploy.md](07-deploy.md) | docker compose, сиды, порты, демо-аккаунты, запуск без docker, тесты, переменные окружения |
| 8. Библиотеки и компоненты | [08-libraries.md](08-libraries.md) | версии и лицензии backend, frontend, инфраструктуры |
| Описание API | [api.md](api.md) | все ключевые операции: запросы, ответы, коды ошибок, переменные окружения |
| Результаты валидации | [validation-results.md](validation-results.md) | полный отчёт метрик |

## Быстрый старт

```
cp .env.example .env
docker compose up --build
docker compose exec api python -m scripts.seed
docker compose exec api python -m scripts.generate_task_pool
docker compose exec api python -m scripts.generate_synthetic
```

API: http://localhost:8000 (Swagger: `/docs`), фронтенд: http://localhost:3000. Демо-аккаунты — в [07-deploy.md](07-deploy.md).
