import re
from decimal import Decimal

from app.models import JudgeMode, QuestionType


def normalize_output(text: str | None) -> str:
    if text is None:
        return ""
    return text.rstrip().replace("\r\n", "\n")


def grade_choice(answer: dict | None, config: dict) -> tuple[Decimal, bool]:
    if not answer:
        return Decimal("0"), False
    selected = set(answer.get("selected", []))
    correct = set(config.get("correct", []))
    if selected == correct:
        return Decimal("1"), True
    return Decimal("0"), False


def grade_short_answer(answer: dict | None, config: dict) -> tuple[Decimal, bool]:
    if not answer:
        return Decimal("0"), False
    text = (answer.get("text") or "").strip()
    mode = config.get("mode", "exact")
    accepted = config.get("accepted", [])
    tolerance = config.get("tolerance", 0.01)

    for acc in accepted:
        if mode == "exact" and text == acc:
            return Decimal("1"), True
        if mode == "normalized" and text.lower().strip() == acc.lower().strip():
            return Decimal("1"), True
        if mode == "numeric":
            try:
                if abs(float(text) - float(acc)) <= tolerance:
                    return Decimal("1"), True
            except ValueError:
                pass
        if mode == "regex" and re.fullmatch(acc, text):
            return Decimal("1"), True
    return Decimal("0"), False


def compare_stdout(actual: str, expected: str) -> bool:
    return normalize_output(actual) == normalize_output(expected)


def partial_coding_score(passed_weight: int, total_weight: int) -> Decimal:
    if total_weight == 0:
        return Decimal("0")
    return Decimal(passed_weight) / Decimal(total_weight)
