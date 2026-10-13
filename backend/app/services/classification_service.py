import re

from transformers import pipeline

_classifier = None

LABELS = ["Invoice", "Resume", "Prescription", "Receipt", "ID Card", "Notes", "Presentation"]

# Zero-shot NLI models (tested both a small distilled model and the much
# larger facebook/bart-large-mnli) rank the correct label lowest on sparse,
# fragment-like OCR text — names, codes, roll numbers don't read as natural
# language, so entailment-based scoring struggles regardless of model size.
# These six document types are fixed and structurally distinctive, so
# keyword/pattern matching is more reliable and is tried first; zero-shot
# only kicks in when nothing matches.
_KEYWORD_PATTERNS: dict[str, list[str]] = {
    "Invoice": [r"invoice", r"bill to", r"subtotal", r"\bqty\b", r"unit price", r"po\s*#"],
    "Receipt": [
        r"receipt", r"\bcash\b", r"change due", r"cashier", r"thank you for (your purchase|shopping)",
        r"fee receipt", r"receipt no\b", r"receipt number", r"payment mode", r"amount paid",
    ],
    "Resume": [r"resume", r"curriculum vitae", r"work experience", r"\bobjective\b", r"references", r"\bskills\b"],
    "Prescription": [r"prescription", r"\brx\b", r"dosage", r"\btablet\b", r"physician", r"\bpatient\b"],
    # "college"/"university"/"autonomous"/a roll-number shape are NOT
    # reserved to ID cards -- fee receipts, hall tickets, and marksheets
    # issued by the same institutions carry the identical letterhead and
    # HT/roll numbers, so those signals were making every college document
    # misclassify as "ID Card". Only match on phrases that are actually
    # specific to an identity card.
    "ID Card": [
        r"id\s*card", r"identity card", r"student id card", r"employee id card",
        r"valid (upto|until|till)", r"blood group", r"date of birth", r"\bdob\b",
    ],
    "Notes": [r"\bnotes\b", r"to-?do", r"reminder"],
}


def _keyword_scores(text: str) -> dict[str, int]:
    lower = text.lower()
    return {
        label: sum(1 for pattern in patterns if re.search(pattern, lower))
        for label, patterns in _KEYWORD_PATTERNS.items()
    }


def _get_classifier():
    global _classifier

    if _classifier is None:
        _classifier = pipeline(
            "zero-shot-classification",
            model="typeform/distilbert-base-uncased-mnli"
        )

    return _classifier


def classify_document(text: str, is_presentation: bool = False) -> str:
    if is_presentation:
        return "Presentation"

    if not text or not text.strip():
        return "Unknown"

    scores = _keyword_scores(text)
    best_label = max(scores, key=scores.get)

    if scores[best_label] > 0:
        return best_label

    classifier = _get_classifier()
    result = classifier(text[:2000], LABELS)

    return result["labels"][0]
