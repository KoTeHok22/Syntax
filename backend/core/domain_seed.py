from sqlalchemy.orm import Session

from backend.core.domain_matching import canonical_key
from backend.models import Domain

CURATED_DOMAINS: list[tuple[str, str, list[str]]] = [
    ("backend", "Backend", ["серверная разработка", "бэкенд", "server-side", "api разработка", "backend developer"]),
    ("frontend", "Frontend", ["фронтенд", "клиентская разработка", "верстка", "ui разработка", "web интерфейс"]),
    ("fullstack", "Fullstack", ["фуллстек", "full stack", "универсальный разработчик"]),
    ("mobile", "Мобильная разработка", ["мобильные приложения", "android", "ios", "мобильный разработчик", "kotlin", "swift"]),
    ("databases", "Базы данных", ["база данных", "субд", "postgres", "postgresql", "sql", "mysql", "oracle", "хранилище данных", "dwh", "массив данных", "информационная система", "реляционные базы данных", "nosql", "mongodb", "clickhouse", "бд"]),
    ("data engineering", "Data Engineering", ["инженерия данных", "etl", "data pipeline", "дата инженер", "потоковая обработка", "kafka", "spark", "airflow", "озеро данных"]),
    ("data science", "Data Science", ["анализ данных", "дата саентист", "ml", "машинное обучение", "ml engineer", "аналитик данных", "data analyst", "pandas", "нейронные сети"]),
    ("devops", "DevOps", ["девопс", "инфраструктура", "ci cd", "docker", "kubernetes", "sre", "эксплуатация", "облачные технологии", "cloud", "надежность сервисов"]),
    ("qa", "QA", ["тестирование", "тестировщик", "quality assurance", "автотесты", "ручное тестирование", "тест инженер"]),
    ("security", "Информационная безопасность", ["безопасность", "иб", "appsec", "пентест", "защита информации", "кибербезопасность"]),
    ("algorithms", "Алгоритмы и структуры данных", ["алгоритмы", "структуры данных", "олимпиадное программирование", "leetcode", "сложность алгоритмов"]),
    ("architecture", "Архитектура ПО", ["системный дизайн", "архитектор", "проектирование систем", "микросервисы", "highload", "масштабирование"]),
    ("product", "Продукт", ["продакт менеджер", "продуктовый менеджер", "product manager", "управление продуктом"]),
    ("analytics", "Аналитика", ["бизнес аналитик", "продуктовая аналитика", "системный аналитик", "bi", "аналитик"]),
    ("project management", "Управление проектами", ["менеджер проектов", "scrum master", "product owner", "agile", "руководитель проектов"]),
    ("design", "Дизайн", ["ux", "ui", "продуктовый дизайнер", "интерфейсы", "дизайнер"]),
    ("support", "Техподдержка", ["поддержка", "technical support", "сопровождение", "helpdesk"]),
    ("1c", "1С", ["1с", "1c", "бухгалтерия", "erp"]),
    ("cpp", "C/C++", ["c++", "cpp", "системное программирование", "низкоуровневое программирование", "embedded"]),
    ("gamedev", "GameDev", ["разработка игр", "геймдев", "unity", "unreal", "игровой движок"]),
]


def seed_domains(db: Session) -> int:
    existing = {domain.slug: domain for domain in db.query(Domain).all()}
    created = 0
    for slug, title, aliases in CURATED_DOMAINS:
        key = canonical_key(slug)
        found = existing.get(key)
        if found is not None:
            if not found.is_curated:
                found.is_curated = True
                found.title = title
                found.aliases = aliases
            continue
        domain = Domain(slug=key, title=title, aliases=aliases, is_curated=True)
        db.add(domain)
        existing[key] = domain
        created += 1
    db.flush()
    return created
