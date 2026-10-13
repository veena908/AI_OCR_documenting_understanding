import base64
import io
import logging
import os

import anthropic
from dotenv import load_dotenv
from PIL import Image

logger = logging.getLogger(__name__)

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

MODEL = "claude-opus-5-5"
MAX_TOKENS = 16000

# Claude's vision encoder downsamples anything larger than ~1568px on the
# long edge anyway, so resizing first costs no accuracy but shrinks the
# upload (phone photos are often 3-4000px) and the request latency.
MAX_IMAGE_EDGE = 1568

TRANSCRIPTION_PROMPT = (
    "Transcribe all text in this image exactly as written, including both "
    "printed and handwritten text. Preserve the original line breaks, "
    "numbering, and bullet points. Keep the writer's own wording and "
    "spelling. Output only the transcribed text - no commentary, "
    "explanation, headers, or markdown formatting."
)

_client = None


def is_available() -> bool:
    # Opt-in: document images leave the machine only when the user has
    # deliberately put an API key in backend/.env. Without one, callers fall
    # back to the fully local EasyOCR/TrOCR pipeline.
    return bool(os.getenv("ANTHROPIC_API_KEY"))


def _get_client() -> anthropic.Anthropic:
    global _client

    if _client is None:
        _client = anthropic.Anthropic(timeout=90.0)

    return _client


def _encode_image(image_path: str) -> str:
    image = Image.open(image_path).convert("RGB")
    image.thumbnail((MAX_IMAGE_EDGE, MAX_IMAGE_EDGE))

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=90)

    return base64.standard_b64encode(buffer.getvalue()).decode("utf-8")


def transcribe_image(image_path: str) -> str | None:
    """
    Returns the transcribed text, or None when vision OCR isn't configured
    or the request failed — the caller should then use local OCR instead.
    """
    if not is_available():
        return None

    try:
        response = _get_client().beta.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            # Transcription needs reading, not reasoning — low effort keeps
            # latency down without hurting accuracy.
            output_config={"effort": "low"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": _encode_image(image_path),
                        },
                    },
                    {"type": "text", "text": TRANSCRIPTION_PROMPT},
                ],
            }],
        )
    except anthropic.AuthenticationError:
        logger.error("Vision OCR: ANTHROPIC_API_KEY in backend/.env is invalid; using local OCR")
        return None
    except (anthropic.APIStatusError, anthropic.APIConnectionError):
        logger.exception("Vision OCR request failed; using local OCR")
        return None

    if response.stop_reason == "refusal":
        logger.warning("Vision OCR declined this image; using local OCR")
        return None

    text = "".join(block.text for block in response.content if block.type == "text").strip()

    return text or None
