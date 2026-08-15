import platform
import subprocess
import wave
from pathlib import Path

from piper import PiperVoice

import re


def clean_text_for_speech(text: str) -> str:
    """
    Convert display formatting into more natural spoken text.
    """

    if not text:
        return ""

    # ------------------------------------------
    # Bullet lists:
    #
    # - water
    # - salt
    #
    # becomes:
    #
    # water.
    # salt.
    # ------------------------------------------

    text = re.sub(
        r"(?m)^\s*-\s+",
        "",
        text,
    )

    # ------------------------------------------
    # Remove markdown emphasis if any.
    # ------------------------------------------

    text = text.replace(
        "**",
        "",
    )

    # ------------------------------------------
    # Make common units slightly more natural.
    # Optional but useful for recipes.
    # ------------------------------------------

    text = re.sub(
        r"\bC\.\b",
        "cups",
        text,
    )

    text = re.sub(
        r"\btbsp\b",
        "tablespoons",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"\btsp\b",
        "teaspoons",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"\boz\b",
        "ounces",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"\blb\b",
        "pounds",
        text,
        flags=re.IGNORECASE,
    )

    # ------------------------------------------
    # Collapse excessive whitespace.
    # ------------------------------------------

    text = re.sub(
        r"\n{3,}",
        "\n\n",
        text,
    )

    return text.strip()


PROJECT_ROOT = Path(__file__).resolve().parent.parent

VOICE_MODEL = (
    PROJECT_ROOT
    / "voices"
    / "en_US-lessac-medium.onnx"
)

OUTPUT_DIRECTORY = PROJECT_ROOT / "temp"
OUTPUT_FILE = OUTPUT_DIRECTORY / "chef_response.wav"


class TextToSpeech:
    def __init__(self) -> None:
        if not VOICE_MODEL.exists():
            raise FileNotFoundError(
                f"Piper voice model not found: {VOICE_MODEL}"
            )

        print("Loading Piper voice...")

        # The model is loaded only once.
        self.voice = PiperVoice.load(str(VOICE_MODEL))

        OUTPUT_DIRECTORY.mkdir(
            parents=True,
            exist_ok=True,
        )

        print("Piper voice loaded.")

    def speak(self, text: str) -> None:
        spoken_text = clean_text_for_speech(
            text
        )

        if not spoken_text:
            return

        # Generate WAV audio directly through Piper's Python API.
        with wave.open(str(OUTPUT_FILE), "wb") as wav_file:
            self.voice.synthesize_wav(
                spoken_text,
                wav_file,
            )

        self._play_audio(OUTPUT_FILE)

    @staticmethod
    def _play_audio(audio_path: Path) -> None:
        system = platform.system()

        if system == "Windows":
            import winsound

            winsound.PlaySound(
                str(audio_path),
                winsound.SND_FILENAME,
            )

        elif system == "Linux":
            # This will be used later on the Raspberry Pi.
            subprocess.run(
                [
            	 "aplay",
           	     "-D",
                 "plughw:CARD=Device,DEV=0",
           	 str(audio_path),
                ],
                check=True,
            )

        else:
            raise RuntimeError(
                f"Unsupported operating system: {system}"
            )
