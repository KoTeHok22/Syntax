# Бенчмарк ранжирования на размеченном наборе пар «вакансия–кандидат»

Воспроизводимый offline-бенчмарк: ранжирование считается реальным backend `build_card`, метрики — по ручной разметке релевантности, независимой от формулы скоринга.
Набор синтетический (командная разметка на синтетике, не экспертная). Критерии — в `docs/pairs-dataset.md`.

## Состав набора
- Вакансий: 12, кандидатов: 74.
- Метрики: Precision@5, NDCG@5, MRR, Recall@10; порог релевантности — grade≥2.

## Метрики
| Режим | Hard-gate | Precision@5 | NDCG@5 | MRR | Recall@10 |
|---|---|---|---|---|---|
| lexical | без gate | 0.400 | 1.000 | 1.000 | 1.000 |
| lexical | с gate | 0.400 | 1.000 | 1.000 | 1.000 |
| semantic | без gate | 0.400 | 0.693 | 0.500 | 1.000 |
| semantic | с gate | 0.400 | 1.000 | 1.000 | 1.000 |

## Дельта от hard-gate
- lexical: Precision@5 0.400 → 0.400 (+0.000), NDCG@5 1.000 → 1.000 (+0.000), MRR 1.000 → 1.000 (+0.000).
- semantic: Precision@5 0.400 → 0.400 (+0.000), NDCG@5 0.693 → 1.000 (+0.307), MRR 0.500 → 1.000 (+0.500).

## Ранжирование по вакансиям (gate=on)
| Вакансия | P@5 | NDCG@5 | MRR | Top-5 |
|---|---|---|---|---|
| Backend Python | 0.40 | 1.00 | 1.00 | python-strong-2, python-strong, python-partial, go-strong, backend-manager |
| Backend Go | 0.40 | 1.00 | 1.00 | go-senior-2, go-senior, go-mid, java-senior, data-mismatch |
| Frontend React | 0.40 | 1.00 | 1.00 | react-strong-2, react-strong, react-partial, vue-strong, backend-mismatch |
| Frontend TypeScript | 0.40 | 1.00 | 1.00 | ts-senior-2, ts-senior, ts-mid, js-only, backend-mismatch |
| Data Engineer | 0.40 | 1.00 | 1.00 | de-strong-2, de-strong, de-partial, analyst, frontend-mismatch |
| Data Engineer Spark | 0.40 | 1.00 | 1.00 | spark-strong-2, spark-strong, spark-mid, kafka-mid, backend-mismatch |
| DevOps Engineer | 0.40 | 1.00 | 1.00 | devops-strong-2, devops-strong, devops-partial, sre-mid, backend-mismatch |
| Cloud Engineer | 0.40 | 1.00 | 1.00 | cloud-strong-2, cloud-strong, cloud-mid, azure-mid, frontend-mismatch |
| Android Developer | 0.40 | 1.00 | 1.00 | android-strong-2, android-strong, android-partial, java-android, backend-mismatch |
| QA Automation | 0.40 | 1.00 | 1.00 | qa-strong-2, qa-strong, qa-partial, manual-qa, backend-mismatch |
| ML Engineer | 0.40 | 1.00 | 1.00 | ml-strong-2, ml-strong, ml-partial, datascience, frontend-mismatch |
| Product Designer | 0.40 | 1.00 | 1.00 | design-strong-2, design-strong, design-partial, graphic-designer, frontend-mismatch |

## Ограничения
Разметка — командная и выполнена на синтетических профилях, а не экспертами на реальных резюме. Набор небольшой (12 вакансий), профили внутри вакансии пересекаются по стеку, поэтому метрики нельзя трактовать как рыночное качество подбора. Hard-gate по тиру (verified/claimed) меняет порядок только там, где рядом стоят профили разных тиров; его эффект измерен и приведён выше, включая случаи, где он не помогает или ухудшает порядок.

## Воспроизведение
`python -m scripts.validate_pairs` перезаписывает этот отчёт; `python -m pytest tests/test_pairs_validation.py -q`.