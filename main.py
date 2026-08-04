from pathlib import Path
import time

from audio.recorder import record_until_silence
from audio.speech_to_text import transcribe_audio
from audio.text_to_speech import TextToSpeech
from audio.wake_word import wait_for_wake_word

from graph.chef_graph import run_chef_graph


PROJECT_ROOT = Path(__file__).resolve().parent
TEMP_DIRECTORY = PROJECT_ROOT / "temp"

END_SESSION_PHRASES = {
    "no",
    "no thanks",
    "no thank you",
    "nothing else",
    "that is all",
    "that's all",
    "i am done",
    "i'm done",
    "goodbye",
    "bye",
    "end session",
    "stop conversation",
    "that's it for now",
}


def normalize_text(text: str) -> str:
    normalized = text.lower().strip()

    for character in ".,!?;:":
        normalized = normalized.replace(character, "")

    return normalized


def should_end_session(text: str) -> bool:
    return normalize_text(text) in END_SESSION_PHRASES


def listen_for_user(filename: str) -> str:
    audio_path = record_until_silence(
        filename=str(TEMP_DIRECTORY / filename),
        start_timeout=8.0,
    )

    if audio_path is None:
        return ""

    return transcribe_audio(audio_path).strip()


def main() -> None:
    print("ChefAI starting...")

    TEMP_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Load Piper once
    tts = TextToSpeech()

    while True:

        # --------------------------------
        # WAKE WORD MODE
        # --------------------------------
        wait_for_wake_word()

        print("Yes?")
        tts.speak("How can I help you?")

        # Give speaker playback a moment to fully stop
        time.sleep(0.5)

        # Short-term conversation memory
        conversation_history: list[dict[str, str]] = []

        # --------------------------------
        # FIRST QUESTION
        # --------------------------------
        user_message = listen_for_user(
            filename="question.wav"
        )

        if not user_message:
            print(
                "No question detected. "
                "Returning to wake-word mode.\n"
            )
            continue

        # --------------------------------
        # CONVERSATION MODE
        # --------------------------------
        while True:

            print(f"\nYou: {user_message}")

            # User wants to end conversation
            if should_end_session(user_message):

                goodbye = (
                    "Okay. Call me when you need me."
                )

                print(f"\nChefAI: {goodbye}")
                tts.speak(goodbye)

                break

            print("Thinking...")

            try:

                # --------------------------------
                # LANGGRAPH
                # --------------------------------
                result = run_chef_graph(
                    user_message=user_message,
                    conversation_history=conversation_history,
                )

                answer = result["answer"]
                intent = result["intent"]

            except Exception as error:

                print(
                    f"ChefAI graph error: {error}"
                )

                failure_message = (
                    "Sorry, I could not process "
                    "your question."
                )

                tts.speak(failure_message)

                break

            # Debugging output
            print(f"\nIntent: {intent}")

            print(f"\nChefAI: {answer}")

            # --------------------------------
            # STORE SHORT-TERM CONVERSATION
            # --------------------------------
            conversation_history.append(
                {
                    "role": "user",
                    "content": user_message,
                }
            )

            conversation_history.append(
                {
                    "role": "assistant",
                    "content": answer,
                }
            )

            # --------------------------------
            # SPEAK RESPONSE
            # --------------------------------
            tts.speak(answer)

            # Avoid detecting ChefAI's own voice
            time.sleep(0.5)

            # --------------------------------
            # LISTEN FOR FOLLOW-UP
            # No wake word needed
            # --------------------------------
            print(
                "\nListening for your response..."
            )

            user_message = listen_for_user(
                filename="follow_up.wav"
            )

            # User stayed silent
            if not user_message:

                print(
                    "\nNo response detected. "
                    "Returning to wake-word mode."
                )

                break

        print(
            "\nReturning to wake-word mode...\n"
        )


if __name__ == "__main__":
    main()