import cv2
import numpy as np
import os

MIN_TARGET_WIDTH = 1200
MAX_UPSCALE = 2.5
LOW_CONTRAST_STD = 45

# A detected page-boundary quad must cover at least this fraction of the
# frame to be trusted — guards against misfiring on already-tightly-cropped
# images (scans, screenshots, ID card photos) where no real background
# border exists and a spurious quad (a shadow, a card edge) could otherwise
# get "corrected" into a wrong shape.
MIN_PAGE_AREA_RATIO = 0.35


def _order_points(pts: np.ndarray) -> np.ndarray:
    rect = np.zeros((4, 2), dtype="float32")

    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]

    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]

    return rect


def _find_page_corners(gray: np.ndarray):
    """
    Look for a large quadrilateral (the photographed page) against its
    background — the same technique mobile "document scanner" apps use to
    flatten a page shot at an angle. Only returns a result when a clearly
    page-sized quad is found, so already-tightly-cropped images are left
    untouched rather than risk a bad warp.
    """
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edged = cv2.dilate(cv2.Canny(blurred, 50, 150), None, iterations=2)

    contours, _ = cv2.findContours(edged, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

    if not contours:
        return None

    image_area = gray.shape[0] * gray.shape[1]

    for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:5]:
        if cv2.contourArea(contour) < image_area * MIN_PAGE_AREA_RATIO:
            continue

        perimeter = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * perimeter, True)

        if len(approx) == 4:
            return approx.reshape(4, 2).astype("float32")

    return None


def _warp_to_page(image: np.ndarray, corners: np.ndarray) -> np.ndarray:
    rect = _order_points(corners)
    (tl, tr, br, bl) = rect

    width = max(int(np.linalg.norm(br - bl)), int(np.linalg.norm(tr - tl)))
    height = max(int(np.linalg.norm(tr - br)), int(np.linalg.norm(tl - bl)))

    if width < 50 or height < 50:
        return image

    dst = np.array(
        [[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]],
        dtype="float32"
    )
    matrix = cv2.getPerspectiveTransform(rect, dst)

    return cv2.warpPerspective(image, matrix, (width, height))


def _deskew_angle(gray: np.ndarray) -> float:
    """Estimate skew angle using the text mask's minimum-area rectangle."""
    mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    coords = np.column_stack(np.where(mask > 0))

    if coords.shape[0] < 20:
        return 0.0

    angle = cv2.minAreaRect(coords)[-1]

    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle

    # A large "skew" usually means the mask picked up background/noise rather
    # than real text, so treat anything outside a plausible range as failure.
    if abs(angle) < 0.5 or abs(angle) > 15:
        return 0.0

    return angle


def _rotate(image: np.ndarray, angle: float) -> np.ndarray:
    if angle == 0.0:
        return image

    (h, w) = image.shape[:2]
    center = (w // 2, h // 2)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)

    return cv2.warpAffine(
        image, matrix, (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE
    )


def _upscale_if_small(image: np.ndarray) -> np.ndarray:
    h, w = image.shape[:2]

    if w >= MIN_TARGET_WIDTH:
        return image

    scale = min(MIN_TARGET_WIDTH / w, MAX_UPSCALE)

    return cv2.resize(image, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC)


def preprocess_image(image_path: str) -> tuple[str, str]:
    """
    Preprocess image for better OCR accuracy.

    EasyOCR (a deep-learning recognizer) performs best on grayscale, well-lit
    images and noticeably *worse* on hard black/white binarized images — the
    binarization step that classic engines like Tesseract rely on actually
    destroys texture cues EasyOCR uses, so it is deliberately avoided here.

    CLAHE contrast enhancement is also skipped unless the image is genuinely
    low-contrast (e.g. a washed-out or unevenly lit photo): applying it
    unconditionally was found to actively degrade already well-lit photos by
    over-amplifying local contrast around fine/decorative text.

    Pipeline: perspective-correct a photographed page if one is detected ->
    deskew -> upscale small images -> grayscale + mild denoise -> conditional
    CLAHE. The deskew/upscale geometric transforms are applied to a color
    copy too (saved alongside, same dimensions as the OCR output), since
    downstream steps (e.g. the handwriting-retry heuristics in
    ocr_service.py) need real color/saturation information that grayscale
    conversion discards, but must still line up pixel-for-pixel with the
    bounding boxes EasyOCR reports against the grayscale image.
    """

    image = cv2.imread(image_path)

    if image is None:
        raise Exception("Unable to read image.")

    corners = _find_page_corners(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY))

    if corners is not None:
        image = _warp_to_page(image, corners)

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    angle = _deskew_angle(gray)

    color = _upscale_if_small(_rotate(image, angle))
    gray = _upscale_if_small(_rotate(gray, angle))

    gray = cv2.fastNlMeansDenoising(gray, h=10, templateWindowSize=7, searchWindowSize=21)

    if gray.std() < LOW_CONTRAST_STD:
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gray = clahe.apply(gray)

    output_folder = "outputs"
    os.makedirs(output_folder, exist_ok=True)

    base_name = os.path.basename(image_path)
    processed_path = os.path.join(output_folder, "processed_" + base_name)
    color_path = os.path.join(output_folder, "color_" + base_name)

    cv2.imwrite(processed_path, gray)
    cv2.imwrite(color_path, color)

    return processed_path, color_path
