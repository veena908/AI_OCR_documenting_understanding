import re

from app.services.extraction_service import EMAIL_RE

# Privacy Shield: finds personal/sensitive data in the OCR text, scores how
# risky the document is to share, and produces a redacted copy. Everything
# runs locally with patterns + checksums -- no text is sent anywhere -- which
# is the point: a general chatbot will happily accept an Aadhaar card or bank
# statement pasted into it, this warns the user *before* they share it.

SEVERITY_HIGH = "High"
SEVERITY_MEDIUM = "Medium"
SEVERITY_LOW = "Low"

# A "Label: value" pair can sit on the same line or wrap onto the next one,
# and OCR often drops/duplicates the colon -- allow any short gap of
# separators between the label and the value.
_LABEL_GAP = r"[\s:.\-#=]{0,6}"

_AADHAAR_RE = re.compile(r"(?<!\d)[2-9]\d{3}[ -]?\d{4}[ -]?\d{4}(?!\d)")
_AADHAAR_LABEL_RE = re.compile(r"aadha+r|uidai|\bUID\b|आधार", re.IGNORECASE)
_PAN_RE = re.compile(r"\b[A-Z]{3}[ABCFGHLJPT][A-Z]\d{4}[A-Z]\b")
_CARD_RE = re.compile(r"(?<!\d)\d(?:[ -]?\d){12,18}(?!\d)")
_IFSC_RE = re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b")
_BANK_ACCOUNT_RE = re.compile(
    r"(?:a/?c|account)\s*(?:no|number|num)?" + _LABEL_GAP + r"(\d{9,18})(?!\d)",
    re.IGNORECASE,
)
_PASSPORT_RE = re.compile(
    r"passport\s*(?:no|number)?" + _LABEL_GAP + r"([A-Z][0-9]{7})\b",
    re.IGNORECASE,
)
_DOB_RE = re.compile(
    r"(?:\bDOB\b|date\s+of\s+birth|birth\s*date)" + _LABEL_GAP
    + r"(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}|\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})",
    re.IGNORECASE,
)
# Indian mobiles (optionally +91/0 prefixed) and generic 10-digit numbers.
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?91[ -]?|0)?[6-9]\d{4}[ -]?\d{5}(?!\d)")

_RECOMMENDATIONS = {
    "Aadhaar Number": "Never share a full Aadhaar number - use a Masked Aadhaar from UIDAI instead.",
    "PAN Number": "PAN can be misused for loans and tax fraud - share only with verified institutions.",
    "Card Number": "Card numbers should never appear in shared documents - redact before sending.",
    "Bank Account": "Bank account details together with IFSC enable fraudulent debit mandates.",
    "Passport Number": "Passport numbers are prime identity-theft targets - redact unless required.",
    "Date of Birth": "Date of birth is often used as a security question - avoid sharing publicly.",
    "Phone Number": "Phone numbers attract spam and SIM-swap attempts - share only where needed.",
    "IFSC Code": "IFSC alone is public, but combined with an account number it is sensitive.",
    "Email Address": "Email addresses attract phishing - consider redacting before posting publicly.",
    "Person Name": "Names link the document to a real person - redact for anonymous sharing.",
}

_VERHOEFF_D = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
    [2, 3, 4, 0, 1, 7, 8, 9, 5, 6], [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
    [4, 0, 1, 2, 3, 9, 5, 6, 7, 8], [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
    [6, 5, 9, 8, 7, 1, 0, 4, 3, 2], [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
    [8, 7, 6, 5, 9, 3, 2, 1, 0, 4], [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
]
_VERHOEFF_P = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
    [5, 8, 0, 3, 7, 9, 6, 1, 4, 2], [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
    [9, 4, 5, 3, 1, 2, 6, 8, 7, 0], [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
    [2, 7, 9, 3, 8, 0, 6, 4, 1, 5], [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
]


def _digits(value: str) -> str:
    return re.sub(r"\D", "", value)


def _verhoeff_valid(number: str) -> bool:
    # Every real Aadhaar number carries a Verhoeff check digit, so this
    # separates genuine Aadhaar numbers from arbitrary 12-digit runs
    # (order IDs, phone numbers with country code, etc.).
    c = 0
    for i, digit in enumerate(reversed(number)):
        c = _VERHOEFF_D[c][_VERHOEFF_P[i % 8][int(digit)]]
    return c == 0


def _luhn_valid(number: str) -> bool:
    total = 0
    for i, digit in enumerate(reversed(number)):
        n = int(digit)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


def _mask(value: str, kind: str) -> str:
    if kind == "Email Address":
        local, _, domain = value.partition("@")
        return f"{local[:1]}{'*' * max(len(local) - 1, 3)}@{domain}"

    if kind == "Person Name":
        return " ".join(f"{word[:1]}{'*' * (len(word) - 1)}" for word in value.split())

    # Numbers / IDs: keep only the last 4 characters visible.
    visible = 4
    chars = [ch for ch in value if ch.isalnum()]
    if len(chars) <= visible:
        return "*" * len(chars)
    return "X" * (len(chars) - visible) + "".join(chars[-visible:])


class _Collector:
    """Gathers findings while rejecting spans that overlap an earlier,
    higher-priority finding (e.g. an Aadhaar number must not also be
    reported as a phone or card number)."""

    def __init__(self, text: str):
        self.text = text
        self.findings: list[dict] = []
        self._spans: list[tuple[int, int]] = []

    def _overlaps(self, start: int, end: int) -> bool:
        return any(start < s_end and s_start < end for s_start, s_end in self._spans)

    def add(self, kind: str, severity: str, start: int, end: int) -> None:
        if start >= end or self._overlaps(start, end):
            return
        self._spans.append((start, end))
        self.findings.append({
            "type": kind,
            "severity": severity,
            "value": self.text[start:end],
            "start": start,
            "end": end,
        })


def _near_label(text: str, start: int, label_re: re.Pattern, window: int = 60) -> bool:
    return bool(label_re.search(text[max(0, start - window):start]))


def detect_sensitive_data(text: str, names: list[str] | None = None) -> dict:
    if not text or not text.strip():
        return {"risk_level": "None", "risk_score": 0, "findings": [], "redacted_text": text or "", "recommendations": []}

    collector = _Collector(text)

    # Label-anchored fields first: their labels make them unambiguous, so they
    # must claim their digits before the looser patterns below see them.
    for kind, pattern, severity in (
        ("Bank Account", _BANK_ACCOUNT_RE, SEVERITY_HIGH),
        ("Passport Number", _PASSPORT_RE, SEVERITY_HIGH),
        ("Date of Birth", _DOB_RE, SEVERITY_MEDIUM),
    ):
        for m in pattern.finditer(text):
            collector.add(kind, severity, m.start(1), m.end(1))

    for m in _AADHAAR_RE.finditer(text):
        number = _digits(m.group(0))
        # OCR can corrupt a single digit and break the checksum, so an
        # explicit "Aadhaar" label nearby is accepted as proof on its own.
        if _verhoeff_valid(number) or _near_label(text, m.start(), _AADHAAR_LABEL_RE):
            collector.add("Aadhaar Number", SEVERITY_HIGH, m.start(), m.end())

    for m in _PAN_RE.finditer(text):
        collector.add("PAN Number", SEVERITY_HIGH, m.start(), m.end())

    for m in _CARD_RE.finditer(text):
        number = _digits(m.group(0))
        if 13 <= len(number) <= 19 and _luhn_valid(number) and len(set(number)) > 1:
            collector.add("Card Number", SEVERITY_HIGH, m.start(), m.end())

    for m in _IFSC_RE.finditer(text):
        collector.add("IFSC Code", SEVERITY_MEDIUM, m.start(), m.end())

    for m in _PHONE_RE.finditer(text):
        collector.add("Phone Number", SEVERITY_MEDIUM, m.start(), m.end())

    for m in EMAIL_RE.finditer(text):
        collector.add("Email Address", SEVERITY_LOW, m.start(), m.end())

    # Names come from the NER step (title-cased for spaCy), so match them
    # back to the original text case-insensitively.
    for name in names or []:
        for m in re.finditer(r"\b" + re.escape(name) + r"\b", text, re.IGNORECASE):
            collector.add("Person Name", SEVERITY_LOW, m.start(), m.end())

    findings = sorted(collector.findings, key=lambda f: f["start"])

    redacted_parts = []
    cursor = 0
    for f in findings:
        redacted_parts.append(text[cursor:f["start"]])
        redacted_parts.append(f"[{f['type'].upper()} REDACTED]")
        cursor = f["end"]
    redacted_parts.append(text[cursor:])

    weights = {SEVERITY_HIGH: 35, SEVERITY_MEDIUM: 15, SEVERITY_LOW: 5}
    risk_score = min(100, sum(weights[f["severity"]] for f in findings))
    severities = {f["severity"] for f in findings}
    risk_level = next(
        (level for level in (SEVERITY_HIGH, SEVERITY_MEDIUM, SEVERITY_LOW) if level in severities),
        "None",
    )

    kinds_in_order = list(dict.fromkeys(f["type"] for f in findings))

    return {
        "risk_level": risk_level,
        "risk_score": risk_score,
        "findings": [
            {
                "type": f["type"],
                "severity": f["severity"],
                "value": f["value"],
                "masked_value": _mask(f["value"], f["type"]),
            }
            for f in findings
        ],
        "redacted_text": "".join(redacted_parts),
        "recommendations": [_RECOMMENDATIONS[k] for k in kinds_in_order],
    }
