import re
import unicodedata

LATIN_TO_CYRILLIC = {
    "a": "а", "b": "в", "c": "с", "e": "е", "h": "н", "k": "к", "m": "м",
    "o": "о", "p": "р", "t": "т", "x": "х", "y": "у",
}

STOPWORDS = {
    "и", "в", "во", "на", "с", "со", "по", "для", "из", "от", "до", "или",
    "the", "and", "of", "for", "with",
}

TOKEN_RE = re.compile(r"[a-zа-я0-9+#.]+")

RU_ENDINGS = (
    "иями", "ями", "ами", "ий", "ия", "ии", "ые", "ых", "ой", "ей", "ов",
    "ам", "ям", "ах", "ях", "ий", "ый", "ая", "ое", "ее", "ие", "ия", "ью",
    "и", "ы", "а", "о", "е", "у", "ю", "я", "ь",
)


def normalize(value: str) -> str:
    text = unicodedata.normalize("NFKC", value or "").lower().strip()
    text = text.replace("ё", "е")
    text = re.sub(r"[«»\"'`]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def stem(token: str) -> str:
    if len(token) <= 3:
        return token
    for ending in RU_ENDINGS:
        if token.endswith(ending) and len(token) - len(ending) >= 3:
            return token[: -len(ending)]
    return token


def canonical_key(value: str) -> str:
    return re.sub(r"[^a-zа-я0-9]+", "-", normalize(value)).strip("-")


def transliterate(token: str) -> str:
    return "".join(LATIN_TO_CYRILLIC.get(char, char) for char in token)


CYRILLIC_TO_LATIN = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ж": "zh",
    "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n",
    "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f",
    "х": "h", "ц": "c", "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "", "ы": "y",
    "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


def to_latin(value: str) -> str:
    return "".join(CYRILLIC_TO_LATIN.get(char, char) for char in value)


def tokens(value: str) -> list[str]:
    found = TOKEN_RE.findall(normalize(value))
    result = []
    for token in found:
        if token in STOPWORDS or len(token) < 2:
            continue
        result.append(stem(token))
    return result


def token_set(value: str) -> set[str]:
    return set(tokens(value))


def dice_coefficient(left: str, right: str) -> float:
    if left == right:
        return 1.0
    if len(left) < 2 or len(right) < 2:
        return 0.0
    left_pairs = {left[i : i + 2] for i in range(len(left) - 1)}
    right_pairs = {right[i : i + 2] for i in range(len(right) - 1)}
    intersection = left_pairs & right_pairs
    return 2 * len(intersection) / (len(left_pairs) + len(right_pairs))


def similarity(query: str, target: str) -> float:
    normalized_query = normalize(query)
    normalized_target = normalize(target)
    if normalized_query == "" or normalized_target == "":
        return 0.0
    if normalized_query == normalized_target:
        return 1.0
    score = 0.0
    shorter, longer = sorted((normalized_query, normalized_target), key=len)
    if len(shorter) >= 4 and (shorter in longer):
        score = max(score, 0.75)
    q_tokens = token_set(normalized_query)
    t_tokens = token_set(normalized_target)
    if q_tokens and t_tokens:
        overlap = len(q_tokens & t_tokens)
        if overlap:
            score = max(score, 0.6 + 0.4 * overlap / max(len(q_tokens), len(t_tokens)))
    if len(shorter) >= 4:
        score = max(score, dice_coefficient(normalized_query, normalized_target))
    else:
        score = max(score, dice_coefficient(normalized_query, normalized_target) * 0.5)
    q_latin = to_latin(normalized_query)
    t_latin = to_latin(normalized_target)
    latin_shorter, latin_longer = sorted((q_latin, t_latin), key=len)
    if len(latin_shorter) >= 4 and (latin_shorter in latin_longer):
        score = max(score, 0.7)
    return score


def domain_score(query: str, slug: str, title: str, aliases: list) -> float:
    best = max(similarity(query, slug), similarity(query, title))
    for alias in aliases or []:
        best = max(best, similarity(query, alias))
    return best


def rank_domains(query: str, domains: list, threshold: float = 0.55) -> list:
    scored = []
    for domain in domains:
        score = domain_score(query, domain.slug, domain.title, list(domain.aliases or []))
        if score >= threshold:
            scored.append((domain, score))
    scored.sort(key=lambda item: item[1], reverse=True)
    return scored


def terms_match_query(query: str, terms: list, threshold: float = 0.6) -> bool:
    for term in terms or []:
        if similarity(query, term) >= threshold:
            return True
    return False


def domain_matches_candidate(domain, specialization: str | None, stack: list) -> bool:
    terms = [domain.slug, domain.title, *(domain.aliases or [])]
    if specialization and terms_match_query(specialization, terms, threshold=0.6):
        return True
    for skill in stack or []:
        if terms_match_query(skill, terms, threshold=0.62):
            return True
    return False


def nearest_domain(query: str, domains: list, threshold: float = 0.34):
    best = None
    best_score = 0.0
    for domain in domains:
        score = domain_score(query, domain.slug, domain.title, list(domain.aliases or []))
        if score > best_score:
            best, best_score = domain, score
    if best is not None and best_score >= threshold:
        return best
    return None
