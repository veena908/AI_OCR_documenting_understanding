import re

import language_tool_python
from language_tool_python.utils import correct as apply_matches

_tool = None

# Emails, URLs, and decimals must survive spelling/grammar passes untouched.
# ALL-CAPS word runs (names on forms/IDs like "AKUTHOTA VEENA", headers,
# acronyms) and alphanumeric codes (roll numbers, reference IDs) are also
# protected -- LanguageTool's autocorrect treats them as misspelled English
# words and silently replaces them with an unrelated dictionary word (e.g.
# "AKUTHOTA VEENA" -> "AUTHOR VERNA"), corrupting the exact proper nouns and
# IDs that downstream extraction relies on.
_protect_re = re.compile(
    r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
    r"|https?://\S+"
    r"|\d+\.\d+"
    r"|\b[A-Z]{2,}(?:[ \t][A-Z]{2,})*\b"
    r"|\b(?=[A-Za-z0-9]*\d)(?=[A-Za-z0-9]*[A-Za-z])[A-Za-z0-9]{4,}\b"
)


def _get_tool() -> language_tool_python.LanguageTool:
    global _tool

    if _tool is None:
        # Spins up a local LanguageTool server (Java) on first use, so
        # grammar/spelling checking runs on-machine instead of sending OCR'd
        # document text -- which can contain personal or ID data -- to the
        # public LanguageTool API.
        _tool = language_tool_python.LanguageTool("en-US")

    return _tool


def _collapse_whitespace(text: str) -> str:
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


# LanguageTool's issue types, grouped into the buckets shown to the user.
_CATEGORY_LABELS = {
    "misspelling": "Spelling",
    "typographical": "Typo",
    "duplication": "Typo",
    "grammar": "Grammar",
    "inconsistency": "Grammar",
    "whitespace": "Punctuation",
    "style": "Style",
}


def _classify_protected(value: str) -> str:
    if "@" in value:
        return "Emails"
    if value.lower().startswith("http"):
        return "Links"
    if any(ch.isdigit() for ch in value):
        return "IDs & numbers"
    return "Names & headings"


def correct_text_with_report(text: str) -> tuple[str, dict]:
    """Same as correct_text, but also returns every fix applied (with
    LanguageTool's reason), the issues it flagged but could not fix, and the
    values that were deliberately shielded from correction."""
    report = {"corrections": [], "unresolved": 0, "protected": {}}

    if not text or not text.strip():
        return text, report

    placeholders: dict[str, str] = {}
    # (start in protected text, placeholder length, original length) for each
    # stash, used to map LanguageTool's offsets back onto the raw OCR text.
    shifts: list[tuple[int, int, int]] = []
    growth = 0

    def stash(match: re.Match) -> str:
        nonlocal growth
        # Sentinel wraps the index in Unicode Private Use Area code points so
        # the key can never collide with a substring that legitimately
        # occurs elsewhere in the text -- a plain digit key like "1" would
        # also match inside an unrelated number such as "10" during the
        # final restore pass, corrupting it.
        key = f"{len(placeholders)}"
        placeholders[key] = match.group(0)
        shifts.append((match.start() + growth, len(key), len(match.group(0))))
        growth += len(key) - len(match.group(0))
        return key

    def to_original(offset: int) -> int:
        delta = 0
        for start, key_len, original_len in shifts:
            if start >= offset:
                break
            delta += key_len - original_len
        return offset - delta

    def restore(value: str) -> str:
        for key, original in placeholders.items():
            value = value.replace(key, original)
        return value

    protected = _protect_re.sub(stash, text)

    try:
        matches = _get_tool().check(protected)
        corrected = apply_matches(protected, matches)
    except Exception:
        # LanguageTool server unreachable/failed to start -- fall back to the
        # (still whitespace-collapsed) original rather than dropping the OCR
        # result entirely.
        matches = []
        corrected = protected

    for match in matches:
        if not match.replacements:
            report["unresolved"] += 1
            continue
        report["corrections"].append({
            "start": to_original(match.offset),
            "end": to_original(match.offset + match.error_length),
            "original": restore(match.matched_text),
            "replacement": restore(match.replacements[0]),
            "category": _CATEGORY_LABELS.get(match.rule_issue_type, "Other"),
            "message": match.message,
        })

    for value in placeholders.values():
        bucket = _classify_protected(value)
        report["protected"][bucket] = report["protected"].get(bucket, 0) + 1

    return restore(_collapse_whitespace(corrected)), report


def correct_text(text: str) -> str:
    return correct_text_with_report(text)[0]
