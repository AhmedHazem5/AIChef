from pathlib import Path
import time

import numpy as np
import sounddevice as sd
import soundfile as sf


# ============================================================
# Raspberry Pi microphone configuration
# ============================================================

MIC_DEVICE_INDEX = 0

SAMPLE_RATE = 48_000
CHANNELS = 1

BLOCK_DURATION = 0.1

BLOCK_SIZE = int(
    SAMPLE_RATE
    * BLOCK_DURATION
)


AMBIENT_CALIBRATION_SECONDS = 1.0

SPEECH_THRESHOLD_MULTIPLIER = 1.6

MIN_SPEECH_THRESHOLD = 0.02

SILENCE_DURATION = 1.5

# Require 300 ms of continuous sound.
REQUIRED_SPEECH_BLOCKS = 2

MAX_RECORDING_DURATION = 30.0


# ============================================================
# Cached microphone calibration
# ============================================================

_cached_ambient_noise: (
    float | None
) = None

_cached_speech_threshold: (
    float | None
) = None


# ============================================================
# Calibration
# ============================================================

def calibrate_microphone(
) -> float:
    """
    Calibrate the microphone ONCE.

    The resulting speech threshold is cached
    and reused by every later recording.
    """

    global _cached_ambient_noise
    global _cached_speech_threshold

    # Already calibrated.
    if (
        _cached_speech_threshold
        is not None
    ):

        return (
            _cached_speech_threshold
        )

    print(
        "\nCalibrating microphone noise..."
    )

    with sd.InputStream(
        device=MIC_DEVICE_INDEX,
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype="float32",
        blocksize=BLOCK_SIZE,
    ) as stream:

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
                    "audio overflow during "
                    "calibration."
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

    _cached_ambient_noise = (
        ambient_noise
    )

    _cached_speech_threshold = (
        speech_threshold
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

    print(
        "Microphone calibration complete.\n"
    )

    return speech_threshold


# ============================================================
# Recording
# ============================================================

def record_until_silence(
    filename: str = "temp/question.wav",
    start_timeout: float = 8.0,
) -> str | None:
    """
    Wait for speech and record until sustained
    silence.

    Microphone calibration is reused rather
    than performed again for every recording.
    """

    # ----------------------------------------
    # Normally this was already performed
    # during ChefAI startup.
    #
    # This fallback makes the function safe
    # when used independently in tests.
    # ----------------------------------------

    speech_threshold = (
        calibrate_microphone()
    )

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
    # Open microphone
    # ========================================================

    with sd.InputStream(
        device=MIC_DEVICE_INDEX,
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype="float32",
        blocksize=BLOCK_SIZE,
    ) as stream:

        # ====================================================
        # Listen immediately.
        #
        # NO calibration here anymore.
        # ====================================================

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
            # Speech already active
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