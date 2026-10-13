import re

import spacy

_nlp = None

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"(\+?\d{1,3}[\s.-]?)?(\(?\d{3,4}\)?[\s.-]?)\d{3,4}[\s.-]?\d{3,4}")
AMOUNT_RE = re.compile(r"(?:₹|\$|Rs\.?|INR|USD)\s?[\d,]+(?:\.\d{1,2})?")

# spaCy's DATE label is unreliable on noisy OCR text -- it sometimes swallows
# URL/handle fragments sitting next to digits (e.g. a LinkedIn link beside a
# roll number) as a "date". A real date always has a digit and never looks
# like a link, so validate before trusting the label.
_URL_LIKE_RE = re.compile(r"https?://|www\.|\.com\b|\.in\b|\.org\b|linkedin|github", re.IGNORECASE)

# Common document field-labels that spaCy's small NER model frequently
# mistakes for PERSON entities on short, label-heavy OCR text.
_NAME_STOPWORDS = {
    "bill", "email", "date", "total", "phone", "item", "name", "address",
    "invoice", "receipt", "notes", "subtotal", "tax", "amount", "due",
    "from", "to", "signature", "id", "card",
    # Resume/CV skill, course, and certification vocabulary -- Title-Case
    # phrases like "Deep Learning", "Advanced Training", "Java -Oracle" sit
    # right next to a real name in skills/certifications sections and the
    # small NER model's PROPN tagging mistakes them for PERSON just as
    # readily as it does the applicant's actual name.
    "learning", "training", "algorithm", "algorithms", "java", "python",
    "oracle", "deep", "machine", "advanced", "intern", "internship",
    "development", "management", "database", "databases", "programming",
    "science", "structures", "structure", "systems", "operations",
    "networks", "network", "security", "analytics", "visualization",
    "simulation", "certification", "certifications", "module", "modules",
    "framework", "frameworks", "stack",
}

# Institution-name words that occasionally get tagged PERSON alongside a
# real name once all-caps banner text is title-cased for NER.
_INSTITUTION_WORDS = {
    "college", "university", "institute", "school", "technology",
    "engineering", "autonomous", "academy",
}

# spaCy's small model is inconsistent on short, label-heavy OCR text (it can
# miss the same name pattern depending on what surrounds it), so a line-shape
# fallback catches names on their own line — very common on ID cards, forms,
# and certificates — when the model finds nothing.
_LINE_NAME_RE = re.compile(r"^[A-Z][a-zA-Z']*(?:\s+[A-Z][a-zA-Z']*){1,3}$")
_SINGLE_WORD_RE = re.compile(r"^[A-Z][a-zA-Z']*$")

# Matches runs of 2+ all-caps *words* (i.e. at least two of them) anywhere in
# a line, not just when the whole line is uppercase -- forms and receipts
# routinely put a label and an all-caps value on the same line
# ("Name : AKUTHOTA VEENA"), which the whole-line check below would
# otherwise leave untouched, hiding the name from spaCy (its small model
# needs Title Case to tag PERSON reliably). Requiring 2+ words (not 1+)
# keeps lone acronyms like "SQL", "HTML", "AIML" upper-case -- title-casing
# them to "Sql"/"Html"/"Aiml" made spaCy mistake them for PERSON entities.
_ALLCAPS_RUN_RE = re.compile(r"\b[A-Z]{2,}(?:[ \t][A-Z]{2,})+\b")


def _get_nlp():
    global _nlp

    if _nlp is None:
        _nlp = spacy.load("en_core_web_sm")

    return _nlp


def _normalize_for_ner(text: str) -> str:
    """
    spaCy's small English model leans heavily on casing to spot names, so it
    reliably finds "Akuthota Veena" but misses "AKUTHOTA VEENA" entirely —
    exactly the all-caps style used on most ID cards and forms. Title-casing
    lines that are fully uppercase (and leaving everything else untouched)
    fixes this without disturbing mixed-case text.
    """
    lines = text.split("\n")

    return "\n".join(
        line.title() if line.strip() and line.isupper()
        else _ALLCAPS_RUN_RE.sub(lambda m: m.group(0).title(), line)
        for line in lines
    )


def _is_eligible_name_text(text: str) -> bool:
    lower = text.lower()

    if lower in _NAME_STOPWORDS or any(word in lower for word in _INSTITUTION_WORDS):
        return False

    return not any(word in _NAME_STOPWORDS for word in lower.split())


def _heuristic_line_names(normalized_text: str) -> list[str]:
    lines = [line.strip() for line in normalized_text.split("\n")]
    candidates = []
    i = 0

    while i < len(lines):
        line = lines[i]

        if not line:
            i += 1
            continue

        if _LINE_NAME_RE.match(line) and _is_eligible_name_text(line):
            candidates.append(line)
            i += 1
            continue

        # OCR sometimes splits a "First Last" name across two adjacent lines
        # (each a standalone Title-Case word) instead of keeping it on one —
        # merge two such lines back into a single name candidate.
        if (
            _SINGLE_WORD_RE.match(line) and len(line) >= 4 and _is_eligible_name_text(line)
            and i + 1 < len(lines)
        ):
            next_line = lines[i + 1]

            if _SINGLE_WORD_RE.match(next_line) and len(next_line) >= 4 and _is_eligible_name_text(next_line):
                candidates.append(f"{line} {next_line}")
                i += 2
                continue

        i += 1

    return candidates


def extract_structured_info(text: str) -> dict:
    if not text or not text.strip():
        return {"names": [], "dates": [], "emails": [], "phones": [], "amounts": []}

    nlp = _get_nlp()
    normalized = _normalize_for_ner(text[:20000])
    doc = nlp(normalized)

    def _clean_person_entity(ent) -> str | None:
        # A name should never span a newline -- forms routinely put the next
        # field on the very next line ("Akuthota Veena\nFee Amount : ..."),
        # and spaCy's small model sometimes merges the two into one PERSON
        # span. Keep only the tokens before the first line break.
        tokens = []
        for tok in ent:
            if "\n" in tok.text:
                break
            tokens.append(tok)

        while tokens and tokens[-1].pos_ == "PUNCT":
            tokens.pop()

        # Only keep spans where every remaining token is tagged as a proper
        # noun -- filters out common-noun/adjective phrases (e.g. "Machine
        # Learning", "Cheerful") that the small NER model occasionally
        # mislabels PERSON.
        if not tokens or not all(t.pos_ == "PROPN" for t in tokens):
            return None

        text = "".join(t.text_with_ws for t in tokens).strip()

        if not text or any(word in _NAME_STOPWORDS for word in text.lower().split()):
            return None
        if not (" " in text or len(text) >= 4):
            return None
        if any(word in text.lower() for word in _INSTITUTION_WORDS):
            return None
        # Real names are alphabetic -- reject spans that picked up digits,
        # "+", "-", or abbreviation periods (roll numbers, grades, "B.Tech",
        # or skill/certification lines like "SQL -Oracle").
        if any(ch.isdigit() for ch in text) or "+" in text or "." in text or "-" in text:
            return None

        return text

    names = sorted({
        cleaned
        for ent in doc.ents
        if ent.label_ == "PERSON"
        and (cleaned := _clean_person_entity(ent))
    })

    if not names:
        names = sorted(set(_heuristic_line_names(normalized)))

    def _is_valid_date_text(date_text: str) -> bool:
        cleaned = date_text.strip()
        if not cleaned or not any(ch.isdigit() for ch in cleaned):
            return False
        if EMAIL_RE.search(cleaned) or _URL_LIKE_RE.search(cleaned):
            return False
        return True

    dates = sorted({
        ent.text.strip()
        for ent in doc.ents
        if ent.label_ == "DATE" and _is_valid_date_text(ent.text)
    })

    emails = sorted(set(EMAIL_RE.findall(text)))
    phones = sorted({m.group(0).strip() for m in PHONE_RE.finditer(text) if len(re.sub(r"\D", "", m.group(0))) >= 7})
    amounts = sorted(set(AMOUNT_RE.findall(text)))

    return {
        "names": names,
        "dates": dates,
        "emails": emails,
        "phones": phones,
        "amounts": amounts,
    }
