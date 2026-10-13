import difflib
import re

# Accuracy view: shows exactly what the correction step changed in the raw
# OCR text, why, and -- when the user supplies the true text of the
# document -- measures real OCR accuracy (CER/WER) before and after
# correction.

_TOKEN_RE = re.compile(r"(\S+)(\s*)")


def _tokens(text: str) -> list[tuple[str, str, int, int]]:
    # (word, following whitespace, start, end of word). Words are compared on
    # their own so a pure whitespace cleanup isn't counted as an OCR fix,
    # while the whitespace is kept for displaying line breaks.
    return [(m.group(1), m.group(2), m.start(1), m.end(1)) for m in _TOKEN_RE.finditer(text or "")]


def _join(tokens: list) -> str:
    return "".join(token[0] + token[1] for token in tokens)


def _span(tokens: list, a0: int, a1: int, text_len: int) -> tuple[int, int]:
    # Character range a diff segment covers in the raw OCR text; an insert
    # (a0 == a1) is a zero-width point before token a0.
    if a0 < a1:
        return tokens[a0][2], tokens[a1 - 1][3]
    point = tokens[a0][2] if a0 < len(tokens) else text_len
    return point, point


def _attach_fixes(span: tuple[int, int], corrections: list[dict]) -> list[dict]:
    # Every fix whose range in the raw text overlaps this segment -- one
    # segment can absorb neighbouring fixes ("recieved the the" ->
    # "received the" carries both the spelling and the repeated-word fix).
    start, end = span
    attached = []
    for fix in corrections:
        if fix.get("_used"):
            continue
        overlaps = (fix["start"] < end and start < fix["end"]) if start < end else fix["start"] <= start <= fix["end"]
        if overlaps:
            fix["_used"] = True
            attached.append(fix)
    return attached


def build_accuracy_report(extracted: str, corrected: str, correction_report: dict) -> dict:
    corrections = [dict(c) for c in correction_report.get("corrections", [])]
    before_tokens = _tokens(extracted)
    after_tokens = _tokens(corrected)

    matcher = difflib.SequenceMatcher(
        a=[t[0] for t in before_tokens], b=[t[0] for t in after_tokens], autojunk=False
    )

    segments = []
    changed_words = 0
    fixes_by_category: dict[str, int] = {}

    for op, a0, a1, b0, b1 in matcher.get_opcodes():
        before = _join(before_tokens[a0:a1])
        after = _join(after_tokens[b0:b1])

        if op == "equal":
            segments.append({"type": "equal", "text": after})
            continue

        changed_words += max(a1 - a0, b1 - b0)
        fixes = _attach_fixes(_span(before_tokens, a0, a1, len(extracted)), corrections)
        for fix in fixes:
            fixes_by_category[fix["category"]] = fixes_by_category.get(fix["category"], 0) + 1
        if not fixes:
            fixes_by_category["Cleanup"] = fixes_by_category.get("Cleanup", 0) + 1

        segments.append({
            "type": op,  # replace | insert | delete
            "before": before,
            "after": after,
            "category": fixes[0]["category"] if fixes else "Cleanup",
            "reasons": list(dict.fromkeys(f["message"] for f in fixes)) or ["Formatting cleanup"],
        })

    total_words = len(before_tokens)

    unresolved = correction_report.get("unresolved", 0)

    # Without the true text these are proxies, labelled "estimated" in the
    # UI: "before" = share of words the corrector did not need to touch,
    # "after" = share of words with no issue left flagged by LanguageTool.
    def pct(bad: int) -> float:
        return round(100 * (1 - bad / total_words), 1) if total_words else 100.0

    return {
        "segments": segments,
        "stats": {
            "total_words": total_words,
            "changed_words": changed_words,
            "change_rate": round(100 * changed_words / total_words, 1) if total_words else 0.0,
            "estimated_accuracy_before": pct(changed_words),
            "estimated_accuracy_after": pct(min(unresolved, total_words)),
            "unresolved_issues": unresolved,
            "fixes_by_category": fixes_by_category,
            "protected": correction_report.get("protected", {}),
        },
    }


# ------------------------------------------------- reference evaluation

def _edit_distance(a: list, b: list) -> int:
    # Shared prefix/suffix never costs an edit; trimming it first makes the
    # usual case (OCR output mostly matching the reference) much faster.
    while a and b and a[0] == b[0]:
        a, b = a[1:], b[1:]
    while a and b and a[-1] == b[-1]:
        a, b = a[:-1], b[:-1]

    # Classic Levenshtein, two rows of memory.
    if len(a) < len(b):
        a, b = b, a
    previous = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        current = [i]
        for j, y in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (x != y)))
        previous = current
    return previous[-1]


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _error_rates(reference: str, hypothesis: str) -> dict:
    ref, hyp = _normalize(reference), _normalize(hypothesis)
    ref_words, hyp_words = ref.split(), hyp.split()
    cer = _edit_distance(list(ref), list(hyp)) / max(len(ref), 1)
    wer = _edit_distance(ref_words, hyp_words) / max(len(ref_words), 1)
    return {
        "cer": round(100 * cer, 2),
        "wer": round(100 * wer, 2),
        "character_accuracy": round(max(0.0, 100 * (1 - cer)), 2),
        "word_accuracy": round(max(0.0, 100 * (1 - wer)), 2),
    }


def _improvement(before: float, after: float) -> float:
    return round(100 * (before - after) / before, 1) if before else 0.0


def evaluate_against_reference(reference: str, extracted: str, corrected: str) -> dict:
    before = _error_rates(reference, extracted)
    after = _error_rates(reference, corrected)
    return {
        "before": before,
        "after": after,
        "cer_improvement": _improvement(before["cer"], after["cer"]),
        "wer_improvement": _improvement(before["wer"], after["wer"]),
    }
