import os
import uuid

import pyttsx3
from gtts import gTTS

OUTPUT_FOLDER = "outputs"


def _synthesize_with_pyttsx3(text: str, output_path: str) -> None:
    engine = pyttsx3.init()
    engine.save_to_file(text, output_path)
    engine.runAndWait()
    engine.stop()


def synthesize_speech(text: str, lang: str = "en") -> str:
    """Returns the path to a generated audio file and its format ("mp3"/"wav")."""
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    # gTTS is the only engine here that can actually speak Hindi/Telugu/etc --
    # pyttsx3 only has whatever voices are installed on the OS (on Windows
    # that's typically English-only SAPI5 voices), so it's kept solely as an
    # offline fallback for English if gTTS's network call fails.
    try:
        output_path = os.path.join(OUTPUT_FOLDER, f"tts_{uuid.uuid4().hex}.mp3")
        gTTS(text=text, lang=lang).save(output_path)
        return output_path, "mp3"
    except Exception:
        if lang != "en":
            raise

        output_path = os.path.join(OUTPUT_FOLDER, f"tts_{uuid.uuid4().hex}.wav")
        _synthesize_with_pyttsx3(text, output_path)
        return output_path, "wav"
