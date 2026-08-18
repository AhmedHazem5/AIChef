import queue
import re
import tempfile
import time
import os

import numpy as np
import sounddevice as sd
import soundfile as sf

from audio.speech_to_text import (
    transcribe_audio,
)


# ============================================================
# Raspberry Pi microphone configuration
# ============================================================

MIC_DEVICE_INDEX = 0

SAMPLE_RATE = 48_000
CHANNELS = 1

BLOCK_DURATION = 0.1
BLOCK_SIZE = int(
    SAMPLE_RATE * BLOCK_DURATION
)


# ============================================================
# Speech / silence settings
# ============================================================

SILENCE_DURATION = 1.0

MAX_UTTERANCE_DURATION = 5.0

AMBIENT_CALIBRATION_SECONDS = 1.0

SPEECH_THRESHOLD_MULTIPLIER = 1.6

MIN_SPEECH_THRESHOLD = 0.01


# ============================================================
# Wake phrase variants
# ============================================================

WAKE_WORD_VARIANTS = [
    "hey chef",
    "hey chief",
]


def normalize_text(
    text: str,
) -> str:

    text = text.lower()

    text = re.sub(
        r"[^\w\s]",
        "",
        text,
    )

    return text.strip()


def contains_wake_word(
    text: str,
) -> bool:

    normalized = normalize_text(
        text
    )

    for variant in WAKE_WORD_VARIANTS:

        if variant in normalized:
            return True

    return False


# ============================================================
# Ambient noise calibration
# ============================================================

def calibrate_noise(
    stream,
) -> float:

    print(
        "Calibrating wake-word microphone..."
    )

    calibration_blocks = int(
        AMBIENT_CALIBRATION_SECONDS
        / BLOCK_DURATION
    )

    noise_levels = []

    for _ in range(
        calibration_blocks
    ):

        audio_block, overflowed = (
            stream.read(
                BLOCK_SIZE
            )
        )

        if overflowed:

            print(
                "Warning: microphone "
                "audio overflow."
            )

        volume = float(
            np.sqrt(
                np.mean(
                    np.square(
                        audio_block
                    )
                )
            )
        )

        noise_levels.append(
            volume
        )

    ambient_noise = float(
        np.median(
            noise_levels
        )
    )

    speech_threshold = max(
        MIN_SPEECH_THRESHOLD,
        ambient_noise
        * SPEECH_THRESHOLD_MULTIPLIER,
    )

    print(
        f"Wake-word ambient noise: "
        f"{ambient_noise:.4f}"
    )

    print(
        f"Wake-word speech threshold: "
        f"{speech_threshold:.4f}"
    )

    return speech_threshold


# ============================================================
# Wake-word listener
# ============================================================

def wait_for_wake_word():

    print(
        "Waiting for wake word..."
    )

    speech_started = False

    frames = []

    silence_start = None

    utterance_start = None

    with sd.InputStream(
        device=MIC_DEVICE_INDEX,
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32",
        blocksize=BLOCK_SIZE,
    ) as stream:

        speech_threshold = (
            calibrate_noise(
                stream
            )
        )

        print(
            f"Using wake-word microphone "
            f"device {MIC_DEVICE_INDEX} "
            f"at {SAMPLE_RATE} Hz."
        )

        while True:

            audio_block, overflowed = (
                stream.read(
                    BLOCK_SIZE
                )
            )

            if overflowed:

                print(
                    "Warning: microphone "
                    "audio overflow."
                )

            volume = float(
                np.sqrt(
                    np.mean(
                        np.square(
                            audio_block
                        )
                    )
                )
            )

            # =================================================
            # Waiting for speech
            # =================================================

            if not speech_started:

                if (
                    volume
                    > speech_threshold
                ):

                    speech_started = True

                    frames = [
                        audio_block.copy()
                    ]

                    silence_start = None

                    utterance_start = (
                        time.monotonic()
                    )

                continue

            # =================================================
            # Recording active utterance
            # =================================================

            frames.append(
                audio_block.copy()
            )

            if (
                volume
                > speech_threshold
            ):

                silence_start = None

            else:

                if silence_start is None:

                    silence_start = (
                        time.monotonic()
                    )

                elif (
                    time.monotonic()
                    - silence_start
                    >= SILENCE_DURATION
                ):

                    text = (
                        process_utterance(
                            frames
                        )
                    )

                    speech_started = False

                    frames = []

                    silence_start = None

                    utterance_start = None

                    if (
                        text
                        and contains_wake_word(
                            text
                        )
                    ):

                        print(
                            "Wake word detected!"
                        )

                        return

                    print(
                        "Waiting for wake word..."
                    )

            # =================================================
            # Maximum utterance duration
            # =================================================

            if (
                utterance_start
                is not None
                and (
                    time.monotonic()
                    - utterance_start
                    >= MAX_UTTERANCE_DURATION
                )
            ):

                text = (
                    process_utterance(
                        frames
                    )
                )

                speech_started = False

                frames = []

                silence_start = None

                utterance_start = None

                if (
                    text
                    and contains_wake_word(
                        text
                    )
                ):

                    print(
                        "Wake word detected!"
                    )

                    return

                print(
                    "Waiting for wake word..."
                )


# ============================================================
# Process one possible wake-word utterance
# ============================================================

def process_utterance(
    frames,
):

    if not frames:
        return ""

    audio = np.concatenate(
        frames,
        axis=0,
    )

    temp_filename = None

    try:

        with tempfile.NamedTemporaryFile(
            suffix=".wav",
            delete=False,
        ) as temp_file:

            temp_filename = (
                temp_file.name
            )

        sf.write(
            temp_filename,
            audio,
            SAMPLE_RATE,
        )

        text = transcribe_audio(
            temp_filename
        )

        if text:

            print(
                "Heard:",
                text,
            )

        return text or ""

    finally:

        if (
            temp_filename
            and os.path.exists(
                temp_filename
            )
        ):

            try:

                os.remove(
                    temp_filename
                )

            except PermissionError:

                pass