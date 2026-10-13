import easyocr
import numpy as np
from PIL import Image

from app.services.handwriting_ocr_service import recognize_handwriting_batch

# Load only once
reader = easyocr.Reader(['en'])


# Real-world text (decorative logos, curved banners, stylized fonts) can
# legitimately score as low as ~0.2-0.4 confidence, overlapping the range
# genuine OCR noise scores in too — there's no clean threshold that
# separates them. Missing real content is worse for document understanding
# than a bit of noise the user can still read, so this only filters
# near-zero-confidence junk rather than trying to be a quality filter.
MIN_CONFIDENCE = 0.12

# Detections scoring between MIN_CONFIDENCE and this ceiling are "uncertain"
# rather than clean misses — EasyOCR's recognizer is biased toward printed
# text, so low confidence here often means handwriting or cursive script
# rather than noise. Those regions get a second opinion from TrOCR, which is
# trained specifically on handwriting, instead of being trusted or dropped.
HANDWRITING_RETRY_CEILING = 0.5

# If at least this fraction of a page's retry-eligible detections fall in the
# uncertain band, the page as a whole is treated as handwritten: every
# eligible detection (not just the uncertain ones) is routed through TrOCR,
# making it the primary recognizer for that page rather than a spot-check.
# EasyOCR's confident reads on a genuinely handwritten page still tend to be
# printed-text lookalikes (letterhead, form labels), so a full pass catches
# body text a narrower per-region check would leave on EasyOCR's reading.
HANDWRITTEN_PAGE_RATIO = 0.4

PADDING = 3

# EasyOCR's CRAFT detector defaults to a 2560px canvas, which took ~11s on a
# CPU for a single phone photo. Document text stays well above the detector's
# minimum size at 1600px, and detection drops to a few seconds.
DETECTION_CANVAS_SIZE = 1600

# A handwritten line wider than this many times its height is split at the
# widest word gap before going to TrOCR, which resizes every crop to a
# 384x384 square — very long lines get squashed past legibility.
MAX_SEGMENT_ASPECT = 10

# TrOCR is trained on plain ink-on-paper handwriting and produces confident
# hallucinated garbage on colorful banners/logos — which happen to fall in
# the same confidence range as genuine handwriting uncertainty. Mean HSV
# saturation cleanly tells them apart: a real ID card's blue banner measured
# ~128, plain document background ~11. Anything much above plain paper is
# treated as decorative/branded content and left to EasyOCR untouched.
MAX_RETRY_SATURATION = 45

# Phone photos taken under warm indoor light tint the whole page: plain
# notebook paper measured ~50 saturation, which the fixed ceiling above
# wrongly treated as "decorative" and kept EasyOCR's garbled reading for
# every handwritten line. The ceiling is therefore raised to sit this far
# above the page's own background saturation.
PAGE_SATURATION_MARGIN = 30


def _crop_region(image: Image.Image, bbox) -> Image.Image:
    xs = [point[0] for point in bbox]
    ys = [point[1] for point in bbox]

    left = max(0, int(min(xs)) - PADDING)
    top = max(0, int(min(ys)) - PADDING)
    right = min(image.width, int(max(xs)) + PADDING)
    bottom = min(image.height, int(max(ys)) + PADDING)

    return image.crop((left, top, right, bottom))


def _saturation_ceiling(image: Image.Image) -> float:
    page_saturation = float(np.median(np.array(image.convert("HSV"))[:, :, 1]))

    return max(MAX_RETRY_SATURATION, page_saturation + PAGE_SATURATION_MARGIN)


def _looks_like_plain_document(crop: Image.Image, ceiling: float) -> bool:
    hsv = np.array(crop.convert("HSV"))

    return hsv[:, :, 1].mean() <= ceiling


def _worth_retrying(text: str) -> bool:
    stripped = text.strip()

    if len(stripped) < 4:
        # Too short to be a meaningful handwritten phrase — more likely a
        # stray artifact (a signature squiggle, a barcode edge) that TrOCR
        # would just hallucinate something plausible-looking for.
        return False

    digit_ratio = sum(c.isdigit() for c in stripped) / len(stripped)

    # IDs, roll numbers, and codes aren't natural handwriting — TrOCR (tuned
    # on IAM's handwritten sentences/words) has no real edge here and can
    # make an already-imperfect digit reading worse.
    if digit_ratio > 0.3:
        return False

    # Source-code syntax (parens, semicolons, braces) is also out of TrOCR's
    # training distribution (natural English sentences, not code) — tested
    # against a real handwritten-code sample, retrying these produced wild
    # hallucinations (e.g. a "println(distance);" line became "primitive in
    # California"), while EasyOCR's raw guess, though imperfect, at least
    # stayed in the neighborhood of the actual text.
    if any(ch in stripped for ch in "(){};"):
        return False

    return True


def _bounds(bbox) -> tuple[float, float, float, float]:
    xs = [point[0] for point in bbox]
    ys = [point[1] for point in bbox]
    return min(xs), min(ys), max(xs), max(ys)


def _group_into_lines(items: list) -> list[list]:
    """Cluster detections whose vertical centers overlap into text lines,
    ordered top-to-bottom, each line ordered left-to-right."""
    lines: list[list] = []

    for item in sorted(items, key=lambda it: sum(_bounds(it[0])[1::2]) / 2):
        _, top, _, bottom = _bounds(item[0])
        center, height = (top + bottom) / 2, bottom - top

        for line in lines:
            line_top = sum(_bounds(it[0])[1] for it in line) / len(line)
            line_bottom = sum(_bounds(it[0])[3] for it in line) / len(line)

            if abs(center - (line_top + line_bottom) / 2) < 0.5 * min(height, line_bottom - line_top):
                line.append(item)
                break
        else:
            lines.append([item])

    for line in lines:
        line.sort(key=lambda it: _bounds(it[0])[0])

    return lines


def _split_line(line: list) -> list[list]:
    segments = [[line[0]]]

    for item in line[1:]:
        current = segments[-1] + [item]
        left = _bounds(current[0][0])[0]
        right = _bounds(item[0])[2]
        top = min(_bounds(it[0])[1] for it in current)
        bottom = max(_bounds(it[0])[3] for it in current)

        if right - left > MAX_SEGMENT_ASPECT * (bottom - top):
            segments.append([item])
        else:
            segments[-1].append(item)

    return segments


def _crop_segment(image: Image.Image, segment: list) -> Image.Image:
    left = min(_bounds(it[0])[0] for it in segment)
    top = min(_bounds(it[0])[1] for it in segment)
    right = max(_bounds(it[0])[2] for it in segment)
    bottom = max(_bounds(it[0])[3] for it in segment)
    pad = max(PADDING, int(0.15 * (bottom - top)))

    return image.crop((
        max(0, int(left) - pad), max(0, int(top) - pad),
        min(image.width, int(right) + pad), min(image.height, int(bottom) + pad),
    ))


def _read_handwritten_page(image: Image.Image, kept: list) -> str:
    """
    TrOCR is trained on whole handwritten lines (IAM), so it reads far more
    accurately with a line's context than word by word — and a page has a
    few dozen lines versus a couple of hundred words, so it's faster too.
    """
    ceiling = _saturation_ceiling(image)
    segments_per_line = [_split_line(line) for line in _group_into_lines(kept)]

    # Only plain ink-on-paper text goes to TrOCR; colorful logos/banners and
    # IDs/code keep EasyOCR's reading (see _looks_like_plain_document and
    # _worth_retrying). Filtering before recognition avoids wasting TrOCR
    # time on crops whose output would be discarded anyway.
    pending = {}

    for segs in segments_per_line:
        for seg in segs:
            crop = _crop_segment(image, seg)
            original = " ".join(it[1].strip() for it in seg)

            if _looks_like_plain_document(crop, ceiling) and _worth_retrying(original):
                pending[id(seg)] = crop

    texts = dict(zip(pending, recognize_handwriting_batch(list(pending.values()))))

    output_lines = []

    for segs in segments_per_line:
        parts = []

        for seg in segs:
            text = texts.get(id(seg))
            parts.append(text or " ".join(it[1].strip() for it in seg))

        output_lines.append(" ".join(parts))

    return "\n".join(output_lines)


def extract_text(image_path: str, color_image_path: str | None = None) -> str:
    """
    color_image_path should be a color image with identical dimensions to
    image_path (same geometric transforms applied, just not converted to
    grayscale) — see image_preprocessing.preprocess_image(). It's used only
    for the handwriting-retry heuristics below, which need real color/
    saturation information that grayscale conversion discards. Without it,
    those heuristics fall back to the grayscale image, where saturation is
    always ~0 and can't distinguish plain document backgrounds from anything
    else.
    """
    results = reader.readtext(
        image_path, detail=1, paragraph=False, canvas_size=DETECTION_CANVAS_SIZE
    )

    kept = [
        [bbox, text, conf]
        for bbox, text, conf in results
        if conf >= MIN_CONFIDENCE and text.strip()
    ]

    retry_candidates = [item for item in kept if _worth_retrying(item[1])]
    uncertain = [item for item in retry_candidates if item[2] < HANDWRITING_RETRY_CEILING]

    handwritten_page = bool(retry_candidates) and (
        len(uncertain) / len(retry_candidates) >= HANDWRITTEN_PAGE_RATIO
    )

    if handwritten_page:
        try:
            image = Image.open(color_image_path or image_path).convert("RGB")
            return _read_handwritten_page(image, kept)
        except Exception:
            # Best-effort: if TrOCR isn't available, fall through to
            # EasyOCR's own reading below.
            pass

    if uncertain:
        try:
            image = Image.open(color_image_path or image_path).convert("RGB")
            ceiling = _saturation_ceiling(image)
            pool = []

            for item in uncertain:
                crop = _crop_region(image, item[0])

                if _looks_like_plain_document(crop, ceiling):
                    pool.append((item, crop))

            texts = recognize_handwriting_batch([crop for _, crop in pool])

            for (item, _), retry_text in zip(pool, texts):
                if retry_text:
                    item[1] = retry_text
        except Exception:
            # Best-effort: if TrOCR isn't available or a crop fails, keep
            # EasyOCR's original (lower-confidence) reading for that region.
            pass

    # Rebuild natural reading order line by line, so words on the same line
    # stay together instead of each detection landing on its own line.
    return "\n".join(
        " ".join(item[1].strip() for item in line)
        for line in _group_into_lines(kept)
    )
