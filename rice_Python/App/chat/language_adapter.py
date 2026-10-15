import re

from .llm import llm


SUPPORTED_LANGUAGES = {"en", "zh"}


def normalize_language(language: str = None) -> str:
    value = (language or "en").strip().lower()
    if value in {"zh", "cn", "chinese", "zh-cn"}:
        return "zh"
    if value in {"en", "english", "en-us", "en-gb"}:
        return "en"
    return "en"


def adapt_answer_language(answer: str, question: str = "", language: str = "en") -> str:
    target_language = normalize_language(language)
    if target_language == "zh":
        return answer
    return translate_answer_to_english(answer, question)


def translate_answer_to_english(answer: str, question: str = "") -> str:
    if not answer:
        return answer
    if not _contains_chinese(answer):
        return answer
    if llm is None:
        return answer

    prompt = f"""Translate the rice genomics database answer below into English.

Rules:
- Return only the translated answer.
- Do not add, remove, or infer any facts.
- Keep gene IDs, transcript IDs, OGI IDs, SV IDs, accession names, chromosomes, coordinates, numbers, units, URLs, and Markdown links unchanged.
- Keep list numbering and Markdown formatting.
- Translate only natural-language text.

User question:
{question}

Answer:
{answer}

/no_think"""

    try:
        response = llm.invoke(prompt)
        translated = getattr(response, "content", response)
        translated = str(translated).strip()
        return _strip_code_fence(translated) or answer
    except Exception:
        return answer


def _contains_chinese(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text or ""))


def _strip_code_fence(text: str) -> str:
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 2:
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            return "\n".join(lines).strip()
    return text.strip()
