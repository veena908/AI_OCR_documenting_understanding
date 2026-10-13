import io
import logging
import os
import time

import requests
from dotenv import load_dotenv
from PIL import Image

logger = logging.getLogger(__name__)

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

READ_PATH = "/vision/v3.2/read/analyze"

# The free (F0) tier rejects uploads over 4 MB. 3000px on the long edge
# keeps phone photos well under that while leaving handwriting sharp.
MAX_IMAGE_EDGE = 3000

# Read is asynchronous: submit, then poll for the result. A page typically
# finishes in 1-3s; give up well before the user would think it's stuck.
POLL_INTERVAL_SECONDS = 1.0
MAX_WAIT_SECONDS = 30
REQUEST_TIMEOUT_SECONDS = 20


def _config() -> tuple[str, str] | None:
    endpoint = os.getenv("AZURE_VISION_ENDPOINT", "").strip().rstrip("/")
    key = os.getenv("AZURE_VISION_KEY", "").strip()

    return (endpoint, key) if endpoint and key else None


def is_available() -> bool:
    # Opt-in: images leave the machine only when an Azure endpoint and key
    # are set in backend/.env. Otherwise callers fall back to local OCR.
    return _config() is not None


def _encode_image(image_path: str) -> bytes:
    image = Image.open(image_path).convert("RGB")
    image.thumbnail((MAX_IMAGE_EDGE, MAX_IMAGE_EDGE))

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=90)

    return buffer.getvalue()


def transcribe_image(image_path: str) -> str | None:
    """
    Returns the transcribed text, or None when Azure OCR isn't configured or
    the request failed — the caller should then use local OCR instead.
    """
    config = _config()

    if config is None:
        return None

    endpoint, key = config

    try:
        submit = requests.post(
            endpoint + READ_PATH,
            params={"readingOrder": "natural"},
            headers={
                "Ocp-Apim-Subscription-Key": key,
                "Content-Type": "application/octet-stream",
            },
            data=_encode_image(image_path),
            timeout=REQUEST_TIMEOUT_SECONDS,
        )

        if submit.status_code != 202:
            logger.error(
                "Azure OCR rejected the request (%s): %s; using local OCR",
                submit.status_code, submit.text[:300],
            )
            return None

        result_url = submit.headers["Operation-Location"]
        deadline = time.monotonic() + MAX_WAIT_SECONDS

        while time.monotonic() < deadline:
            time.sleep(POLL_INTERVAL_SECONDS)

            poll = requests.get(
                result_url,
                headers={"Ocp-Apim-Subscription-Key": key},
                timeout=REQUEST_TIMEOUT_SECONDS,
            )

            if poll.status_code == 429:
                # Free tier allows 20 calls/minute; polls count too.
                continue

            poll.raise_for_status()
            result = poll.json()
            status = result.get("status")

            if status == "succeeded":
                pages = result["analyzeResult"]["readResults"]
                text = "\n\n".join(
                    "\n".join(line["text"] for line in page.get("lines", []))
                    for page in pages
                ).strip()

                return text or None

            if status == "failed":
                logger.error("Azure OCR failed to read the image; using local OCR")
                return None

        logger.error("Azure OCR timed out after %ss; using local OCR", MAX_WAIT_SECONDS)
        return None

    except (requests.RequestException, KeyError, ValueError):
        logger.exception("Azure OCR request failed; using local OCR")
        return None
