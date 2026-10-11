from backend.core.domain_matching import similarity
from backend.core.labels import concept_domains_for_specialization

PROOF_VERIFIED = "verified"
PROOF_CLAIMED = "claimed"

CONCEPT_DOMAINS: tuple[str, ...] = (
    "algorithms",
    "databases",
    "backend",
    "frontend",
    "devops",
    "design",
)

STACK_DOMAIN_KEYWORDS: dict[str, tuple[str, ...]] = {
    "databases": (
        "postgres",
        "mysql",
        "sqlite",
        "oracle",
        "sql server",
        "mssql",
        "mongodb",
        "redis",
        "clickhouse",
        "cassandra",
        "elasticsearch",
        "sql",
        "database",
        "бд",
    ),
    "devops": (
        "kubernetes",
        "k8s",
        "docker",
        "terraform",
        "ansible",
        "jenkins",
        "gitlab ci",
        "github actions",
        "ci/cd",
        "nginx",
        "prometheus",
        "grafana",
    ),
    "frontend": (
        "react",
        "angular",
        "svelte",
        "nuxt",
        "html",
        "scss",
        "sass",
        "tailwind",
        "webpack",
        "vite",
        "typescript",
        "javascript",
        "redux",
        "jquery",
    ),
    "backend": (
        "fastapi",
        "django",
        "flask",
        "spring",
        "express",
        "laravel",
        "rails",
        "graphql",
        "grpc",
        "python",
        "java",
        "kotlin",
        "php",
    ),
    "algorithms": (
        "algorithms",
        "алгоритмы",
        "data structures",
        "leetcode",
    ),
    "design": (
        "figma",
        "sketch",
        "photoshop",
        "illustrator",
        "prototyping",
    ),
}

KEYWORD_MATCH_THRESHOLD = 0.82

EXACT_SKILL_DOMAINS: dict[str, str] = {
    "node": "backend",
    "node.js": "backend",
    "nodejs": "backend",
    "nest.js": "backend",
    "next.js": "frontend",
    "c#": "backend",
    "c++": "algorithms",
    "go": "backend",
    "golang": "backend",
    "spring boot": "backend",
    ".net": "backend",
    "asp.net": "backend",
    "nextjs": "frontend",
    "rest": "backend",
    "rest api": "backend",
    "бд": "databases",
    "sql": "databases",
    "css": "frontend",
    "vue": "frontend",
    "ux": "design",
    "ui": "design",
}


def _field(record, name):
    if isinstance(record, dict):
        return record.get(name)
    return getattr(record, name, None)


def verified_domains(answers) -> set[str]:
    found: set[str] = set()
    for answer in answers or []:
        if not _field(answer, "is_correct"):
            continue
        domain = _field(answer, "domain")
        if domain:
            found.add(str(domain).strip().lower())
    return found


def keyword_domain_for(skill: str) -> str | None:
    if not skill:
        return None
    exact = EXACT_SKILL_DOMAINS.get(skill.strip().lower())
    if exact is not None:
        return exact
    best_domain = None
    best_score = 0.0
    for domain, keywords in STACK_DOMAIN_KEYWORDS.items():
        for keyword in keywords:
            score = similarity(skill, keyword)
            if score > best_score:
                best_domain, best_score = domain, score
    if best_domain is not None and best_score >= KEYWORD_MATCH_THRESHOLD:
        return best_domain
    return None


def specialization_domain(skill: str, specialization: str | None, domains_verified: set[str]) -> str | None:
    allowed = concept_domains_for_specialization(specialization)
    verified_here = [domain for domain in allowed if domain in domains_verified]
    if not verified_here:
        return None
    best_domain = None
    best_score = 0.0
    for domain in verified_here:
        score = similarity(skill, domain)
        if score > best_score:
            best_domain, best_score = domain, score
    return best_domain


def stack_proof_map(
    stack: list[str],
    specialization: str | None,
    domains_verified: set[str],
) -> list[dict]:
    result = []
    for raw_skill in stack or []:
        skill = (raw_skill or "").strip()
        if not skill:
            continue
        domain = keyword_domain_for(skill)
        if domain is None:
            domain = specialization_domain(skill, specialization, domains_verified)
        if domain is None or domain not in domains_verified:
            result.append({"stack": skill, "domain": None, "proof": PROOF_CLAIMED})
            continue
        result.append({"stack": skill, "domain": domain, "proof": PROOF_VERIFIED})
    return result
