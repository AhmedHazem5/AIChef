from pathlib import Path
import time

from audio.recorder import record_until_silence
from audio.speech_to_text import transcribe_audio
from audio.text_to_speech import TextToSpeech
from audio.wake_word import wait_for_wake_word
from memory.cooking_session import get_current_recipe
from graph.chef_graph import run_chef_graph
from ui.display_manager import DisplayManager

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
    "thanks bye",
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


def update_recipe_display(display: DisplayManager) -> bool:
    """
    Show the current cooking step on the TFT.

    Returns True if an active recipe was displayed.
    """

    recipe = get_current_recipe()

    if recipe is None:
        return False

    steps = recipe.get("steps", [])

    if not steps:
        return False

    current_step = recipe.get(
        "current_step",
        0,
    )

    if (
        current_step < 0
        or current_step >= len(steps)
    ):
        return False

    display.show_cooking_step(
        recipe_title=recipe.get(
            "title",
            "Recipe",
        ),
        step_number=current_step + 1,
        total_steps=len(steps),
        step_text=steps[current_step],
    )

    return True


def main() -> None:
    print("ChefAI starting...")

    TEMP_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Load Piper once
    tts = TextToSpeech()

    display = DisplayManager()

    while True:

        # --------------------------------
        # WAKE WORD MODE
        # --------------------------------
        wait_for_wake_word()

        display.show_idle()

        print("Yes?")
        tts.speak("How can I help you?")

        # Give speaker playback a moment to fully stop
        time.sleep(0.5)

        # Short-term conversation memory
        conversation_history: list[dict[str, str]] = []

        display.show_listening()

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

            display.show_thinking()

            try:

                # --------------------------------
                # LANGGRAPH
                # --------------------------------
                thinking_start = time.perf_counter()
                result = run_chef_graph(
                    user_message=user_message,
                    conversation_history=conversation_history,
                )

                thinking_time = (
                    time.perf_counter()
                    - thinking_start
                )

                print(
                    f"\n[TIMING] ChefAI reasoning: "
                    f"{thinking_time:.2f} seconds"
                )

                answer = result["answer"]
                intent = result["intent"]

                update_recipe_display(display)

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
            tts_start = time.perf_counter()

            tts.speak(answer)

            tts_time = (
                time.perf_counter()
                - tts_start
            )

            print(
                f"[TIMING] TTS + playback: "
                f"{tts_time:.2f} seconds"
            )

            # Avoid detecting ChefAI's own voice
            time.sleep(0.5)

            # --------------------------------
            # LISTEN FOR FOLLOW-UP
            # No wake word needed
            # --------------------------------
            print(
                "\nListening for your response..."
            )

            display.show_listening()

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

        display.show_idle()

        print(
            "\nReturning to wake-word mode...\n"
        )


if __name__ == "__main__":
    main()