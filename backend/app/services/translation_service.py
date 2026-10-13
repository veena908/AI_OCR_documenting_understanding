from deep_translator import GoogleTranslator, MyMemoryTranslator
from deep_translator.constants import MY_MEMORY_LANGUAGES_TO_CODES
from langdetect import LangDetectException, detect

_GOOGLE_CHUNK_SIZE = 4500
_MYMEMORY_CHUNK_SIZE = 480  # MyMemory's free tier caps requests at 500 chars

# MyMemory needs a region-tagged locale ("es-ES") rather than the plain ISO
# codes ("es"/"hi"/"te"...) the frontend, GoogleTranslator, and langdetect
# all use. Built from MyMemory's own ~320-entry language table (instead of a
# short hand-picked list) so any language langdetect can name -- not just
# the ones in the frontend's dropdown -- resolves to a working fallback
# locale; every non-English question currently routes through this fallback
# since Google's endpoint is blocked on this network. Several languages have
# multiple regional entries sharing one 2-letter prefix (French: "belgian
# french" -> fr-BE, "french" -> fr-FR, "french canada" -> fr-CA, ...) and the
# table's alphabetical-by-name order doesn't put the plain/unqualified name
# first for all of them -- "belgian" sorts before "french" -- so pick the
# shortest (fewest-word) name per prefix instead of the first one seen.
_MYMEMORY_BY_PREFIX: dict[str, list[str]] = {}
for _name, _code in MY_MEMORY_LANGUAGES_TO_CODES.items():
    _prefix = _code.split("-", 1)[0].lower()
    _MYMEMORY_BY_PREFIX.setdefault(_prefix, []).append(_name)

_MYMEMORY_LOCALE: dict[str, str] = {
    _prefix: MY_MEMORY_LANGUAGES_TO_CODES[min(_names, key=lambda n: len(n.split()))]
    for _prefix, _names in _MYMEMORY_BY_PREFIX.items()
}
del _name, _code, _prefix

# langdetect's codes for Chinese variants don't match the "zh-CN" code the
# rest of the app uses.
_LANG_CODE_ALIASES = {"zh-cn": "zh-CN", "zh-tw": "zh-CN"}


def _chunk(text: str, size: int):
    for i in range(0, len(text), size):
        yield text[i:i + size]


def _chunk_on_words(text: str, size: int):
    """Split on whitespace so a chunk never cuts a word in half -- MyMemory's
    500-char cap leaves little room to spare for a mid-word split."""
    words = text.split(" ")
    current = ""

    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) > size and current:
            yield current
            current = word
        else:
            current = candidate

    if current:
        yield current


def _resolve_source_locale(text: str, source_lang: str) -> str:
    # Unlike GoogleTranslator, MyMemory has no "auto" source -- it requires a
    # concrete language code, so detect it ourselves when the caller didn't
    # supply one.
    if source_lang == "auto":
        try:
            source_lang = _LANG_CODE_ALIASES.get(detect(text), detect(text))
        except LangDetectException:
            source_lang = "en"

    return _MYMEMORY_LOCALE.get(source_lang, source_lang)


def _translate_with_mymemory(text: str, target_lang: str, source_lang: str) -> str:
    mymemory_source = _resolve_source_locale(text, source_lang)
    mymemory_target = _MYMEMORY_LOCALE.get(target_lang, target_lang)
    translator = MyMemoryTranslator(source=mymemory_source, target=mymemory_target)

    if len(text) <= _MYMEMORY_CHUNK_SIZE:
        return translator.translate(text)

    return " ".join(
        translator.translate(chunk) for chunk in _chunk_on_words(text, _MYMEMORY_CHUNK_SIZE)
    )


def _translate_chunk(chunk: str, target_lang: str, source_lang: str) -> str:
    # Google's free endpoint is scrape-based and prone to network-level rate
    # limiting/blocking that has nothing to do with request volume from this
    # app -- fall back to MyMemory so translation still works when that
    # happens instead of surfacing a hard failure to the user.
    try:
        return GoogleTranslator(source=source_lang, target=target_lang).translate(chunk)
    except Exception:
        return _translate_with_mymemory(chunk, target_lang, source_lang)


def translate_text(text: str, target_lang: str, source_lang: str = "auto") -> str:
    if not text or not text.strip():
        return text

    if len(text) <= _GOOGLE_CHUNK_SIZE:
        return _translate_chunk(text, target_lang, source_lang)

    return "".join(
        _translate_chunk(chunk, target_lang, source_lang) for chunk in _chunk(text, _GOOGLE_CHUNK_SIZE)
    )
