import random
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from backend.auth.security import hash_password
from backend.core.categorization import assign_category
from backend.core.testing import adaptive_verdict, result_score
from backend.db import Base, SessionLocal, engine, ensure_vector_extension
from backend.models import (
    Application,
    CandidateProfile,
    EmployerProfile,
    PvnAchievement,
    Invitation,
    RegularTask,
    TestSession,
    User,
    Vacancy,
)
from backend.core.matching import (
    APPLICATION_STATUSES,
    INVITATION_ACCEPTED,
    INVITATION_REJECTED,
    INVITATION_SENT,
    INVITATION_VIEWED,
)

DEMO_PASSWORD = "demo-password"

SPECIALIZATIONS = ["backend", "frontend", "data", "devops"]
STACKS = {
    "backend": ["python", "fastapi", "django", "postgresql", "redis", "docker"],
    "frontend": ["javascript", "typescript", "react", "vue", "css", "vite"],
    "data": ["python", "sql", "airflow", "spark", "pandas", "clickhouse"],
    "devops": ["linux", "docker", "kubernetes", "terraform", "ansible", "ci"],
}
GRADES = ["junior", "middle", "senior"]
ABILITY_BY_GRADE = {"junior": 0.55, "middle": 0.7, "senior": 0.85}

FIRST_NAMES = ["Анна", "Борис", "Вера", "Глеб", "Дарья", "Егор", "Жанна", "Захар", "Ирина", "Кирилл", "Лидия", "Марк", "Надежда", "Олег", "Полина"]
LAST_NAMES = ["Абрамов", "Белов", "Волкова", "Громов", "Дмитриева", "Ефимов", "Зайцева", "Иванов", "Крылов", "Лебедева", "Морозов", "Никитина", "Орлов", "Панова", "Романов"]
SOFT_SKILLS = ["командная работа", "коммуникация", "ответственность", "обучаемость", "тайм-менеджмент", "критическое мышление"]

ACHIEVEMENT_TYPES = [("олимпиада", "золото", 40.0), ("олимпиада", "серебро", 30.0), ("олимпиада", "бронза", 20.0), ("хакатон", "победитель", 35.0), ("хакатон", "финалист", 25.0), ("проект", "куратор", 15.0)]

VACANCY_TITLES = {
    "backend": "Backend-разработчик",
    "frontend": "Frontend-разработчик",
    "data": "Инженер данных",
    "devops": "DevOps-инженер",
}

VACANCY_TITLE_ACCUSATIVE = {
    "backend": "Backend-разработчика",
    "frontend": "Frontend-разработчика",
    "data": "инженера данных",
    "devops": "DevOps-инженера",
}

VACANCY_DESCRIPTION = {
    "backend": "Сервисы на Python и PostgreSQL, нагрузка растёт вместе с числом клиентов. Нужно держать API быстрым и предсказуемым.",
    "frontend": "Продуктовый интерфейс для тысяч пользователей. Работаем над скоростью загрузки, доступностью и единой дизайн-системой.",
    "data": "Пайплайны на Airflow и Spark, витрины для аналитики и отчётности. Данные приходят из десятков источников каждый час.",
    "devops": "Инфраструктура в Kubernetes, деплой несколько раз в день. Задача — короткий цикл релиза и надёжные алерты.",
}
SALARY_BY_GRADE = {"junior": (60000, 120000), "middle": (150000, 250000), "senior": (250000, 400000)}
EMPLOYERS = [
    ("demo-employer@example.com", "ООО Вектор Диджитал", "Продуктовая разработка высоконагруженных сервисов"),
    ("demo-employer2@example.com", "ООО Гелион Софт", "Финтех-платформа для корпоративных клиентов"),
    ("demo-employer3@example.com", "ООО Оникс Платформа", "Инфраструктурные решения и облачные сервисы"),
]


def create_demo_users(db: Session, count: int, rng: random.Random) -> int:
    password_hash = hash_password(DEMO_PASSWORD)
    created = 0
    for i in range(1, count + 1):
        email = f"demo.candidate.{i:03d}@example.com"
        if db.query(User).filter(User.email == email).first() is not None:
            continue
        specialization = SPECIALIZATIONS[i % len(SPECIALIZATIONS)]
        grade = GRADES[rng.randrange(0, 64) // 24]
        first = FIRST_NAMES[rng.randrange(len(FIRST_NAMES))]
        last = LAST_NAMES[rng.randrange(len(LAST_NAMES))]
        stack = rng.sample(STACKS[specialization], k=rng.randint(3, 5))
        user = User(
            email=email,
            password_hash=password_hash,
            role="candidate",
            consent_accepted=True,
            pvn_id=f"PVN-{100000 + i}" if rng.random() < 0.4 else None,
            is_email_confirmed=True,
        )
        db.add(user)
        db.flush()
        profile = CandidateProfile(
            user_id=user.id,
            full_name=f"{first} {last}",
            contacts={"email": email, "phone": f"+7900{rng.randrange(1000000, 9999999)}"},
            stack=stack,
            years_of_experience=round(rng.uniform(0, 12), 1),
            soft_skills=rng.sample(SOFT_SKILLS, k=rng.randint(2, 4)),
            specialization=specialization,
            grade=grade,
            is_visible=True,
        )
        db.add(profile)
        db.flush()
        assign_category(db, profile, specialization, grade)
        create_history(db, profile, grade, rng)
        if rng.random() < 0.45:
            create_achievements(db, profile, rng)
        created += 1
    return created


def create_history(db: Session, profile: CandidateProfile, grade: str, rng: random.Random) -> None:
    ability = min(0.95, max(0.15, ABILITY_BY_GRADE[grade] + rng.uniform(-0.25, 0.2)))
    task_count = 5
    correct = sum(1 for _ in range(task_count) if rng.random() < ability)
    completed_at = datetime.now(timezone.utc) - timedelta(days=rng.randint(10, 120))
    session = TestSession(
        candidate_profile_id=profile.id,
        grade=grade,
        task_count=task_count,
        correct_count=correct,
        result_score=result_score(correct, task_count),
        verdict=adaptive_verdict(correct, task_count),
        status="completed",
        completed_at=completed_at,
    )
    db.add(session)


def create_achievements(db: Session, profile: CandidateProfile, rng: random.Random) -> None:
    for _ in range(rng.randint(1, 3)):
        achievement_type, level, score = ACHIEVEMENT_TYPES[rng.randrange(len(ACHIEVEMENT_TYPES))]
        db.add(
            PvnAchievement(
                candidate_profile_id=profile.id,
                achievement_type=achievement_type,
                level=level,
                achieved_at=date.today() - timedelta(days=rng.randint(30, 500)),
                score=score,
            )
        )


def create_demo_employers_and_vacancies(db: Session, rng: random.Random) -> int:
    password_hash = hash_password(DEMO_PASSWORD)
    created = 0
    for email, company_name, description in EMPLOYERS:
        if db.query(User).filter(User.email == email).first() is None:
            user = User(
                email=email,
                password_hash=password_hash,
                role="employer",
                consent_accepted=True,
                is_email_confirmed=True,
            )
            db.add(user)
            db.flush()
            db.add(
                EmployerProfile(
                    user_id=user.id,
                    company_name=company_name,
                    description=description,
                    contacts={"email": email, "hr": f"hr@{email.split('@')[1]}"},
                )
            )
    db.commit()
    employer_profiles = db.query(EmployerProfile).all()
    for i in range(20):
        specialization = SPECIALIZATIONS[i % len(SPECIALIZATIONS)]
        grade = GRADES[i % len(GRADES)]
        salary_from, salary_to = SALARY_BY_GRADE[grade]
        if db.query(Vacancy).filter(Vacancy.title == f"{VACANCY_TITLES[specialization]} ({grade}) #{i + 1}").first() is not None:
            continue
        employer = employer_profiles[i % len(employer_profiles)]
        db.add(
            Vacancy(
                employer_profile_id=employer.id,
                title=f"{VACANCY_TITLES[specialization]} ({grade}) #{i + 1}",
                description=description_placeholder(specialization, grade),
                stack=rng.sample(STACKS[specialization], k=rng.randint(2, 4)),
                specialization=specialization,
                grade=grade,
                salary_from=salary_from,
                salary_to=salary_to + rng.randrange(0, 50000, 5000),
                status="open",
            )
        )
        created += 1
    return created


INVITATION_STATUS_CYCLE = [INVITATION_SENT, INVITATION_VIEWED, INVITATION_ACCEPTED, INVITATION_REJECTED]
APPLICATION_STATUS_CYCLE = APPLICATION_STATUSES

REGULAR_TASKS = [
    ("Спроектируйте кеширование для эндпоинта, который отдаёт список товаров, и назовите главный риск устаревания данных.", ["Кешировать на 1 год без инвалидации", "Кеш с TTL и инвалидацией при изменении", "Не кешировать вообще", "Кешировать только на клиенте"], 1),
    ("Какой индекс PostgreSQL ускорит запрос WHERE status = 'open' ORDER BY created_at DESC?", ["Индекс по id", "Составной индекс (status, created_at)", "Индекс по description", "Отсутствие индекса — оптимальнее"], 1),
    ("Какой подход лучше для миграции схемы без простоя?", ["Удалить колонку и добавить новую сразу", "Expand-contract: сначала добавить, потом перенести, потом удалить", "Остановить сервис на ночь", "Менять схему только в тестовой БД"], 1),
]


def create_demo_invitations(db: Session, rng: random.Random) -> int:
    employers = db.query(EmployerProfile).order_by(EmployerProfile.id).all()
    candidates = db.query(CandidateProfile).order_by(CandidateProfile.id).limit(30).all()
    if not employers or not candidates:
        return 0
    created = 0
    for index, candidate in enumerate(candidates[:20]):
        if db.query(Invitation).filter(Invitation.candidate_profile_id == candidate.id).first() is not None:
            continue
        employer = employers[index % len(employers)]
        salary_from, salary_to = SALARY_BY_GRADE[candidate.grade or "junior"]
        db.add(
            Invitation(
                employer_profile_id=employer.id,
                candidate_profile_id=candidate.id,
                message=f"Приглашаем на позицию {VACANCY_TITLE_ACCUSATIVE.get(candidate.specialization, 'разработчика')}. Обсудим задачи и условия.",
                salary_from=salary_from,
                salary_to=salary_to,
                company_name=employer.company_name,
                contact_method=employer.contacts.get("hr", "hr@example.com") if employer.contacts else "hr@example.com",
                status=INVITATION_STATUS_CYCLE[index % len(INVITATION_STATUS_CYCLE)],
            )
        )
        created += 1
    db.flush()
    return created


def create_demo_applications(db: Session, rng: random.Random) -> int:
    vacancies = db.query(Vacancy).filter(Vacancy.status == "open").order_by(Vacancy.id).limit(10).all()
    candidates = db.query(CandidateProfile).order_by(CandidateProfile.id).limit(30).all()
    created = 0
    for index, vacancy in enumerate(vacancies):
        candidate = candidates[(index + 10) % len(candidates)]
        if db.query(Application).filter(Application.vacancy_id == vacancy.id, Application.candidate_profile_id == candidate.id).first() is not None:
            continue
        db.add(
            Application(
                vacancy_id=vacancy.id,
                candidate_profile_id=candidate.id,
                message="Заинтересован в вакансии, готов к собеседованию.",
                status=APPLICATION_STATUS_CYCLE[index % len(APPLICATION_STATUS_CYCLE)],
            )
        )
        created += 1
    db.flush()
    return created


def create_demo_regular_tasks(db: Session) -> int:
    employer = db.query(EmployerProfile).order_by(EmployerProfile.id).first()
    if employer is None:
        return 0
    created = 0
    for statement, options, reference_answer in REGULAR_TASKS:
        if db.query(RegularTask).filter(RegularTask.statement == statement).first() is not None:
            continue
        db.add(
            RegularTask(
                employer_profile_id=employer.id,
                statement=statement,
                task_format="multiple_choice",
                options=options,
                reference_answer=reference_answer,
                is_active=True,
            )
        )
        created += 1
    db.flush()
    return created


def description_placeholder(specialization: str, grade: str) -> str:
    return VACANCY_DESCRIPTION.get(specialization, "Продуктовая команда, задачи с реальными пользователями.")


def main() -> None:
    ensure_vector_extension(engine)
    Base.metadata.create_all(bind=engine)
    rng = random.Random(2026)
    db = SessionLocal()
    try:
        candidates = create_demo_users(db, 100, rng)
        db.commit()
        vacancies = create_demo_employers_and_vacancies(db, rng)
        db.commit()
        invitations = create_demo_invitations(db, rng)
        applications = create_demo_applications(db, rng)
        regular_tasks = create_demo_regular_tasks(db)
        db.commit()
        print(f"Создано кандидатов: {candidates}")
        print(f"Создано вакансий: {vacancies}")
        print(f"Создано приглашений: {invitations}")
        print(f"Создано откликов: {applications}")
        print(f"Создано регулярных заданий: {regular_tasks}")
        print(f"Демо-пароль для всех аккаунтов: {DEMO_PASSWORD}")
        print("Работодатели: " + ", ".join(email for email, _, _ in EMPLOYERS))
        print("Кандидаты: demo.candidate.001@example.com ... demo.candidate.100@example.com")
    finally:
        db.close()


if __name__ == "__main__":
    main()
