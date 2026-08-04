from faster_whisper import WhisperModel


print("Loading Whisper...")

model = WhisperModel(
    "base.en",
    device="cpu",
    compute_type="int8"
)

print("Whisper loaded.")


def transcribe_audio(filename):

    segments, info = model.transcribe(
        filename,
        beam_size=1,
        vad_filter=True,
        condition_on_previous_text=False
    )

    text_parts = []

    for segment in segments:
        text_parts.append(segment.text.strip())

    return " ".join(text_parts).strip()