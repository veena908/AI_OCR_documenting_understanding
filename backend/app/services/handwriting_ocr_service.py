import torch
from PIL import Image
from transformers import (
    RobertaTokenizer,
    TrOCRProcessor,
    VisionEncoderDecoderModel,
    ViTImageProcessor,
)

_processor = None
_model = None

MODEL_NAME = "microsoft/trocr-base-handwritten"

# Crops are encoded/decoded together in batches — on CPU this is several
# times faster than one generate() call per crop.
BATCH_SIZE = 8


def _get_model():
    global _processor, _model

    if _model is None:
        # TrOCRProcessor.from_pretrained() routes through transformers' new
        # AutoTokenizer dispatch, which can't convert this repo's legacy
        # vocab.json/merges.txt tokenizer on this transformers version.
        # Loading the tokenizer and image processor explicitly bypasses
        # that broken auto-dispatch path.
        tokenizer = RobertaTokenizer.from_pretrained(MODEL_NAME)
        image_processor = ViTImageProcessor.from_pretrained(MODEL_NAME)
        _processor = TrOCRProcessor(image_processor=image_processor, tokenizer=tokenizer)
        _model = VisionEncoderDecoderModel.from_pretrained(MODEL_NAME)
        _model.eval()

    return _processor, _model


def _max_new_tokens(crop: Image.Image) -> int:
    # TrOCR is a generative decoder — given more token budget than a crop's
    # text actually needs, it will keep generating and hallucinate extra
    # words. Bounding max_new_tokens by the crop's width relative to its
    # height (roughly one token per character-height of width) keeps it from
    # running past what the region could plausibly contain.
    return max(6, min(64, int(1.5 * crop.width / max(crop.height, 1)) + 4))


def recognize_handwriting_batch(crops: list[Image.Image]) -> list[str]:
    """
    Recognize cropped text regions with TrOCR, which is trained specifically
    on handwritten text lines (IAM dataset) — unlike EasyOCR's recognizer,
    which is biased toward printed text. Whole-line crops suit it best.
    """
    results = [""] * len(crops)
    valid = [i for i, crop in enumerate(crops) if crop.width >= 4 and crop.height >= 4]

    # Batch crops of similar length together: generate() runs until the
    # longest sequence in a batch finishes, so mixing one long line with
    # short words would make every short crop wait on it.
    valid.sort(key=lambda i: _max_new_tokens(crops[i]))

    if not valid:
        return results

    processor, model = _get_model()

    with torch.inference_mode():
        for start in range(0, len(valid), BATCH_SIZE):
            indexes = valid[start:start + BATCH_SIZE]
            batch = [crops[i].convert("RGB") for i in indexes]

            pixel_values = processor(images=batch, return_tensors="pt").pixel_values
            # The checkpoint's generation config ships with use_cache=False,
            # which recomputes the whole decoded sequence for every new
            # token — enabling the KV cache was measured ~6x faster.
            generated_ids = model.generate(
                pixel_values,
                max_new_tokens=max(_max_new_tokens(c) for c in batch),
                use_cache=True,
            )
            texts = processor.batch_decode(generated_ids, skip_special_tokens=True)

            for i, text in zip(indexes, texts):
                results[i] = text.strip()

    return results

