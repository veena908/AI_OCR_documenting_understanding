from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.lex_rank import LexRankSummarizer

_summarizer = LexRankSummarizer()

SENTENCE_COUNT = 4


def summarize_text(text: str) -> str:
    if not text or not text.strip():
        return ""

    parser = PlaintextParser.from_string(text, Tokenizer("english"))
    sentence_count = min(SENTENCE_COUNT, len(parser.document.sentences))

    if sentence_count == 0:
        return text.strip()

    summary_sentences = _summarizer(parser.document, sentence_count)

    if not summary_sentences:
        return text.strip()

    return " ".join(str(sentence) for sentence in summary_sentences)
