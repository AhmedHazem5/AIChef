from pathlib import Path
import time

import numpy as np
import sounddevice as sd
import soundfile as sf


# ============================================================
# Raspberry Pi microphone configuration
# ============================================================

MIC_DEVICE_INDEX = 1

SAMPLE_RATE = 48_000
CHANNELS = 1

BLOCK_DURATION = 0.1
BLOCK_SIZE = int(
    SAMPLE_RATE * BLOCK_DURATION
)

AMBIENT_CALIBRATION_SECONDS = 1.0
SPEECH_THRESHOLD_MULTIPLIER = 1.6
MIN_SPEECH_THRESHOLD = 0.02

SILENCE_DURATION = 1.5

# Require 300 ms of continuous sound before considering
# speech to have started.
REQUIRED_SPEECH_BLOCKS = 3

MAX_RECORDING_DURATION = 30.0


def record_until_silence(
    filename: str = "temp/question.wav",
    start_timeout: float = 8.0,
) -> str | None:
    """
    Wait for the user to start speaking, then record until
    sustained silence.

    Returns the WAV filename, or None when no speech starts
    before the timeout.
    """

    output_path = Path(
        filename
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    print(
        "Listening for question..."
    )

    recorded_frames: list[
        np.ndarray
    ] = []

    possible_speech_frames: list[
        np.ndarray
    ] = []

    speech_started = False

    consecutive_speech_blocks = 0

    listening_started_at = (
        time.monotonic()
    )

    recording_started_at: (
        float | None
    ) = None

    silence_started_at: (
        float | None
    ) = None

    # ========================================================
    # Open the correct USB microphone
    # ========================================================

    with sd.InputStream(
        device=MIC_DEVICE_INDEX,
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32",
        blocksize=BLOCK_SIZE,
    ) as stream:

        print("Calibrating microphone noise...")

        calibration_blocks = int(
            AMBIENT_CALIBRATION_SECONDS
            / BLOCK_DURATION
        )

        noise_levels = []

        for _ in range(
            calibration_blocks
        ):

            audio_block, _ = stream.read(
                BLOCK_SIZE
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
            f"Ambient noise: "
            f"{ambient_noise:.4f}"
        )

        print(
            f"Speech threshold: "
            f"{speech_threshold:.4f}"
        )

        print(
            f"Using microphone device "
            f"{MIC_DEVICE_INDEX} "
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

            # ================================================
            # Waiting for genuine speech
            # ================================================

            if not speech_started:

                if (
                    volume
                    > speech_threshold
                ):

                    consecutive_speech_blocks += 1

                    possible_speech_frames.append(
                        audio_block.copy()
                    )

                    if (
                        consecutive_speech_blocks
                        >= REQUIRED_SPEECH_BLOCKS
                    ):

                        speech_started = True

                        recording_started_at = (
                            time.monotonic()
                        )

                        recorded_frames.extend(
                            possible_speech_frames
                        )

                        possible_speech_frames = []

                        silence_started_at = None

                        print(
                            "Speech detected."
                        )

                else:

                    consecutive_speech_blocks = 0

                    possible_speech_frames = []

                if (
                    time.monotonic()
                    - listening_started_at
                    >= start_timeout
                ):

                    print(
                        "No speech detected."
                    )

                    return None

                continue

            # ================================================
            # Speech is already active
            # ================================================

            recorded_frames.append(
                audio_block.copy()
            )

            if (
                volume
                > speech_threshold
            ):

                silence_started_at = None

            else:

                if (
                    silence_started_at
                    is None
                ):

                    silence_started_at = (
                        time.monotonic()
                    )

                elif (
                    time.monotonic()
                    - silence_started_at
                    >= SILENCE_DURATION
                ):

                    break

            # ================================================
            # Maximum recording duration
            # ================================================

            if (
                recording_started_at
                is not None
                and (
                    time.monotonic()
                    - recording_started_at
                    >= MAX_RECORDING_DURATION
                )
            ):

                print(
                    "Maximum recording "
                    "duration reached."
                )

                break

    # ========================================================
    # Save WAV
    # ========================================================

    if not recorded_frames:

        return None

    audio = np.concatenate(
        recorded_frames,
        axis=0,
    )

    sf.write(
        str(output_path),
        audio,
        SAMPLE_RATE,
    )

    print(
        "Finished listening."
    )

    return str(
        output_path
    )