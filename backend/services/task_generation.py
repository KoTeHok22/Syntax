import hashlib
import json
import random
from dataclasses import dataclass

from openai import OpenAIError

from backend.services.llm import StubLLMClient, get_llm_client

TASK_GENERATION_PROMPT = """Сгенерируй задачу на концепт "{concept_name}" для грейда {grade}.
Ограничения по сложности: {difficulty_params}.
Формат: {task_format}.
Сформулируй условие коротко: 2–4 предложения, только прикладной контекст, данные и вопрос.
Оформляй условие удобно для чтения: разделяй абзацы пустой строкой (символ \n\n), а данные
(журнал операций, список, таблица, фрагмент кода) выноси отдельной строкой или блоком кода
в тройных обратных кавычках с указанием языка. Вопрос ставь в последнем абзаце отдельной строкой.
КАТЕГОРИЧЕСКИ запрещено подсказывать решение: не называй алгоритм, структуру данных,
паттерн или метод, который является ответом, и не описывай ход решения в условии.
Дай только постановку задачи и данные. Варианты ответа формулируй как равноправные гипотезы.
Верни JSON с ключами: statement, options, reference_answer. Для формата multiple_choice
options — список из 4 строк, reference_answer — индекс верного варианта (0-3).
Для формата code reference_answer — эталонное решение строкой, options — пустой список.
Ответ должен быть строго валидным JSON без markdown-обёртки и пояснений."""


class _SafeFormat(dict):
    def __missing__(self, key):
        return "{" + key + "}"


@dataclass
class TaskDraft:
    statement: str
    task_format: str
    options: list
    reference_answer: object


def build_prompt(concept, grade: str) -> str:
    return TASK_GENERATION_PROMPT.format(
        concept_name=concept.name,
        grade=grade,
        difficulty_params=json.dumps(concept.difficulty_params, ensure_ascii=False),
        task_format=concept.task_format,
    )


DESIGN_DOMAINS = {"design"}


def is_design_concept(concept) -> bool:
    return getattr(concept, "domain", None) in DESIGN_DOMAINS


def parse_llm_response(raw: str, task_format: str) -> TaskDraft | None:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    try:
        data = json.loads(text)
        return TaskDraft(
            statement=data["statement"],
            task_format=task_format,
            options=data.get("options", []),
            reference_answer=data["reference_answer"],
        )
    except (json.JSONDecodeError, KeyError, TypeError):
        return None


def fallback_task(concept, seed: str, context_labels: list[str]) -> TaskDraft | None:
    if not concept.question_template or not concept.correct_answer:
        return None
    digest = hashlib.sha256(f"{concept.id}:{concept.name}:{seed}".encode("utf-8")).digest()
    ticket = 10000 + int.from_bytes(digest[7:11], "big") % 89999
    if context_labels:
        company = context_labels[digest[0] % len(context_labels)]
    else:
        company = f"проект №{ticket}"
    values = _SafeFormat(
        company=company,
        n=100 + int.from_bytes(digest[1:3], "big") % 900,
    )
    statement = concept.question_template.format_map(values) + f" Детали инцидента: тикет #{ticket}."
    options = [concept.correct_answer.format_map(values)] + [
        d.format_map(values) for d in concept.distractors
    ]
    order = list(range(len(options)))
    random.Random(int.from_bytes(digest[3:7], "big")).shuffle(order)
    shuffled = [options[i] for i in order]
    task_format = concept.task_format if is_design_concept(concept) else "multiple_choice"
    return TaskDraft(
        statement=statement,
        task_format=task_format,
        options=shuffled,
        reference_answer=order.index(0),
    )


async def llm_task(concept, grade: str) -> TaskDraft | None:
    if is_design_concept(concept):
        return None
    client = get_llm_client()
    if isinstance(client, StubLLMClient):
        return None
    try:
        raw = await client.complete(build_prompt(concept, grade))
    except OpenAIError:
        return None
    if not raw:
        return None
    return parse_llm_response(raw, concept.task_format)


async def generate_task(concept, grade: str, seed: str = "", context_labels: list[str] | None = None) -> TaskDraft | None:
    draft = await llm_task(concept, grade)
    if draft is not None:
        return draft
    return fallback_task(concept, seed, context_labels or [])


def check_answer(task, submission) -> bool:
    if task.task_format in {"multiple_choice", "design_choice"}:
        return submission.option_index is not None and submission.option_index == task.reference_answer
    return submission.answer is not None and submission.answer.strip() == str(task.reference_answer).strip()
