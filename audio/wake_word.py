import queue
import re
import tempfile
import time
import os

import numpy as np
import sounddevice as sd
import soundfile as sf

from audio.speech_to_text import transcribe_audio


SAMPLE_RATE = 16000
CHANNELS = 1

# How long silence must last before we consider the utterance finished
SILENCE_DURATION = 1.0

# Minimum RMS volume to consider something speech/noise worth recording
SILENCE_THRESHOLD = 0.008

# Maximum length of one attempted utterance
MAX_UTTERANCE_DURATION = 5.0

WAKE_WORD_VARIANTS = [
    "hey chef",
    "hey chief",
]


def normalize_text(text):
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    return text.strip()


def contains_wake_word(text):
    normalized = normalize_text(text)

    for variant in WAKE_WORD_VARIANTS:
        if variant in normalized:
            return True

    return False


def wait_for_wake_word():
    print("Waiting for wake word...")

    audio_queue = queue.Queue()

    speech_started = False
    frames = []

    silence_start = None
    utterance_start = None

    block_duration = 0.1
    block_size = int(SAMPLE_RATE * block_duration)

    def audio_callback(indata, frames_count, time_info, status):
        if status:
            print("Audio status:", status)

        audio_queue.put(indata.copy())

    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype="float32",
        blocksize=block_size,
        callback=audio_callback
    ):

        while True:

            try:
                audio_block = audio_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            # RMS volume
            volume = np.sqrt(np.mean(audio_block ** 2))

            # -------------------------
            # Speech has NOT started
            # -------------------------
            if not speech_started:

                if volume > SILENCE_THRESHOLD:
                    speech_started = True

                    frames = [audio_block.copy()]

                    silence_start = None
                    utterance_start = time.time()

                continue

            # -------------------------
            # Speech HAS started
            # -------------------------

            frames.append(audio_block.copy())

            if volume > SILENCE_THRESHOLD:
                silence_start = None

            else:
                if silence_start is None:
                    silence_start = time.time()

                elif time.time() - silence_start >= SILENCE_DURATION:

                    text = process_utterance(frames)

                    # Reset immediately
                    speech_started = False
                    frames = []
                    silence_start = None
                    utterance_start = None

                    if text and contains_wake_word(text):
                        print("Wake word detected!")
                        return

                    print("Waiting for wake word...")

            # Safety timeout
            if (
                utterance_start is not None
                and time.time() - utterance_start >= MAX_UTTERANCE_DURATION
            ):

                text = process_utterance(frames)

                speech_started = False
                frames = []
                silence_start = None
                utterance_start = None

                if text and contains_wake_word(text):
                    print("Wake word detected!")
                    return

                print("Waiting for wake word...")


def process_utterance(frames):

    if not frames:
        return ""

    audio = np.concatenate(frames, axis=0)

    # Ignore very quiet recordings
    volume = np.sqrt(np.mean(audio ** 2))

    if volume < SILENCE_THRESHOLD:
        return ""

    temp_filename = None

    try:
        with tempfile.NamedTemporaryFile(
            suffix=".wav",
            delete=False
        ) as temp_file:
            temp_filename = temp_file.name

        sf.write(
            temp_filename,
            audio,
            SAMPLE_RATE
        )

        text = transcribe_audio(temp_filename)

        if text:
            print("Heard:", text)

        return text

    finally:
        if temp_filename and os.path.exists(temp_filename):
            try:
                os.remove(temp_filename)
            except PermissionError:
                pass