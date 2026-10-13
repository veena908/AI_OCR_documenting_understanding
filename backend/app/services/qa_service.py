import re

import torch
from langdetect import LangDetectException, detect
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

from app.services.translation_service import translate_text

_tokenizer = None
_model = None

# Switched from an extractive span model (distilbert-base-cased-distilled-
# squad) to a generative one. The extractive model can only mark the
# highest-scoring contiguous span in the context -- it has no way to decide
# *which* of several similar entities (e.g. two colleges on one resume) the
# question actually means, and it was also notably fragile to ALL-CAPS OCR
# text and to unrelated text preceding the answer. A generative model reads
# the whole context and composes an answer, which handles exactly the
# disambiguation and phrasing cases the span model kept getting wrong.
MODEL_NAME = "google/flan-t5-base"
MAX_INPUT_TOKENS = 512

_INSTRUCTION_TEMPLATE = (
    "Answer the question using only the information in the context below. "
    "The context may be a form or receipt with explicit \"Label: Value\" "
    "fields (e.g. \"Name: John Smith\") -- when the question asks about one "
    "of those labels, use that field's value, not unrelated text elsewhere "
    "such as a letterhead or address. "
    "Copy names, emails, phone numbers, and IDs exactly as they appear in "
    "the context. "
    "If the context does not contain the answer, reply exactly: "
    "I couldn't find an answer in the document.\n\n"
    "Question: {question}\n\nContext: "
)
_ANSWER_CUE = "\n\nAnswer:"

# The model occasionally stops generating right after the first word of a
# multi-word ALL-CAPS proper noun (e.g. answers "GEETHANJALI" instead of
# "GEETHANJALI COLLEGE OF ENGINEERING AND TECHNOLOGY"). Forcing a longer
# minimum generation length "fixes" that case but corrupts every naturally
# short answer instead (a phone number like "9666173740" gets the model's
# own no-answer fallback phrase appended once forced past its natural stop
# point). Detecting this one specific pattern after normal generation --
# the answer is an exact prefix of a longer all-caps run in the context --
# and expanding it to that full run fixes the truncation without touching
# any answer that wasn't actually cut short.
_ALLCAPS_RUN_RE = re.compile(r"\b[A-Z]{2,}(?:[ \t][A-Z]{2,})*\b")


def _get_model():
    global _tokenizer, _model

    if _model is None:
        _tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
        _model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_NAME)
        _model.eval()

    return _tokenizer, _model


def _build_prompt(context: str, question: str, tokenizer) -> str:
    # The question must never be the part that gets cut when the prompt is
    # too long for the model -- letting the tokenizer's own truncation act on
    # "instructions + question + context" (in that order) silently clipped
    # the question and the "Answer:" cue off the end for any context over
    # ~512 tokens, leaving the model to blindly continue a dangling context
    # (it was answering *every* question with a random Academic Projects
    # bullet, having never seen the actual question). Only the context is
    # ever allowed to be trimmed, and only by exactly as much as it takes to
    # fit the fixed instruction+question+answer-cue text in the token budget.
    header = _INSTRUCTION_TEMPLATE.format(question=question)
    reserved = len(tokenizer(header + _ANSWER_CUE, add_special_tokens=True)["input_ids"])
    budget = max(MAX_INPUT_TOKENS - reserved, 0)

    context_ids = tokenizer(context, add_special_tokens=False)["input_ids"][:budget]
    truncated_context = tokenizer.decode(context_ids, skip_special_tokens=True)

    return header + truncated_context + _ANSWER_CUE


def _expand_truncated_allcaps(answer: str, context: str) -> str:
    if not answer:
        return answer

    for match in _ALLCAPS_RUN_RE.finditer(context):
        run = match.group(0)
        if len(run) > len(answer) and run.upper().startswith(answer.upper()):
            return run

    return answer


# langdetect's codes for Chinese variants don't match the "zh-CN" code the
# rest of the app (translation_service, frontend language list) uses.
_LANG_CODE_ALIASES = {"zh-cn": "zh-CN", "zh-tw": "zh-CN"}


def _detect_language(text: str) -> str:
    try:
        code = detect(text)
    except LangDetectException:
        return "en"

    return _LANG_CODE_ALIASES.get(code, code)


def _answer_question_en(context: str, question: str) -> str:
    tokenizer, model = _get_model()

    prompt = _build_prompt(context, question, tokenizer)
    inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=MAX_INPUT_TOKENS)

    with torch.no_grad():
        output_ids = model.generate(**inputs, max_new_tokens=64, do_sample=False)

    answer = tokenizer.decode(output_ids[0], skip_special_tokens=True).strip()
    answer = _expand_truncated_allcaps(answer, context)

    return answer if answer else "I couldn't find an answer in the document."


def answer_question(context: str, question: str) -> str:
    if not context or not context.strip():
        return "No document text available to answer from."

    # The underlying model (flan-t5-base) only reasons reliably in English,
    # so a non-English question is translated to English to ask it, and the
    # English answer is translated back to the question's own language --
    # letting the caller ask and receive an answer in any language without
    # the model itself needing to support it.
    question_lang = _detect_language(question)
    english_question = (
        question if question_lang == "en"
        else translate_text(question, "en", source_lang=question_lang)
    )

    answer = _answer_question_en(context, english_question)

    if question_lang != "en":
        answer = translate_text(answer, question_lang, source_lang="en")

    return answer
