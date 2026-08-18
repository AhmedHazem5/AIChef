from pathlib import Path
import time

from audio.recorder import record_until_silence
from audio.speech_to_text import transcribe_audio
from audio.text_to_speech import TextToSpeech
from audio.wake_word import wait_for_wake_word

from hardware.weight_parser import (
    extract_weight,
)

from hardware.weight_sensor import (
    get_weight_sensor,
)

from memory.cooking_session import (
    get_current_recipe,
)

from graph.chef_graph import (
    run_chef_graph,
)

from ui.display_manager import (
    DisplayManager,
)

from timers.timer_manager import (
    extract_duration,
    get_timer_manager,
)


PROJECT_ROOT = (
    Path(__file__).resolve().parent
)

TEMP_DIRECTORY = (
    PROJECT_ROOT
    / "temp"
)


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
    "okay, thanks",
    "ok, thanks",
    "thanks, bye",
    "okay, bye",
    "ok, bye"
}


YES_PHRASES = {
    "yes",
    "yeah",
    "yep",
    "sure",
    "okay",
    "ok",
    "start it",
    "yes please",
    "please do",
    "do it",
}


NO_PHRASES = {
    "no",
    "no thanks",
    "no thank you",
    "not now",
    "don't",
    "do not",
}


def normalize_text(
    text: str,
) -> str:

    normalized = (
        text.lower()
        .strip()
    )

    for character in (
        ".,!?;:"
    ):

        normalized = (
            normalized.replace(
                character,
                "",
            )
        )

    return " ".join(
        normalized.split()
    )


def should_end_session(
    text: str,
) -> bool:

    return (
        normalize_text(text)
        in END_SESSION_PHRASES
    )


def is_yes(
    text: str,
) -> bool:

    return (
        normalize_text(text)
        in YES_PHRASES
    )


def is_no(
    text: str,
) -> bool:

    return (
        normalize_text(text)
        in NO_PHRASES
    )

def is_weight_command(
    text: str,
) -> bool:

    normalized = normalize_text(
        text
    )

    weight_keywords = (
        "weigh",
        "weight",
        "measure",
        "scale",
    )

    return any(
        keyword in normalized
        for keyword in weight_keywords
    )

def handle_direct_weight_command(
    text: str,
    tts: TextToSpeech,
    display: DisplayManager,
) -> bool:
    """
    Handle direct scale commands such as:

        weigh 200 grams
        help me weigh 14 ounces
        measure half a pound
        I want to weigh 1 kilogram

    Returns True if this was handled
    as a scale request.
    """

    if not is_weight_command(
        text
    ):
        return False

    weight = extract_weight(
        text
    )

    if weight is None:

        response = (
            "I heard a weighing request, "
            "but I could not understand "
            "the target weight."
        )

        print(
            f"\nChefAI: {response}"
        )

        tts.speak(
            response
        )

        return True

    target_grams = (
        weight[
            "grams"
        ]
    )

    # ----------------------------------------
    # Use metric for scale guidance.
    # ----------------------------------------

    if target_grams >= 1000:

        target_spoken = (
            f"{target_grams / 1000:.2f}"
            .rstrip("0")
            .rstrip(".")
            + " kilograms"
        )

    else:

        target_spoken = (
            f"{target_grams:.0f} grams"
        )

    scale = get_weight_sensor()

    message = (
        "Place your empty bowl or container "
        "on the scale. Say ready when "
        "you have placed it."
    )

    print(
        f"\nChefAI: {message}"
    )

    tts.speak(
        message
    )

    time.sleep(
        0.5
    )

    # ----------------------------------------
    # WAIT FOR USER TO CONFIRM CONTAINER
    # ----------------------------------------

    while True:

        print(
            "\n[SCALE] Waiting for "
            "container confirmation..."
        )

        response = listen_for_user(
            filename="scale_ready.wav"
        )

        if not response:
            # Stay in scale setup mode.
            # Do NOT return to wake-word mode.
            continue

        normalized_response = (
            normalize_text(
                response
            )
        )

        print(
            f"[SCALE] User: {response}"
        )

        ready_phrases = {
            "ready",
            "done",
            "i am ready",
            "im ready",
            "i added it",
            "i put it",
            "i placed it",
            "its there",
            "it is there",
            "container ready",
            "bowl ready",
            "yes",
            "okay",
            "ok",
        }

        if (
            normalized_response
            in ready_phrases
        ):

            break

        reminder = (
            "Say ready when the empty "
            "container is on the scale."
        )

        print(
            f"ChefAI: {reminder}"
        )

        tts.speak(
            reminder
        )

        time.sleep(
            0.5
        )


    tare_message = (
        "Okay. I will tare "
        "the scale now."
    )

    print(
        f"ChefAI: {tare_message}"
    )

    tts.speak(
        tare_message
    )

    scale.tare()

    start_message = (
        f"Okay. Start adding "
        f"the ingredient. "
        f"The target is "
        f"{target_spoken}."
    )

    print(
        f"ChefAI: {start_message}"
    )

    tts.speak(
        start_message
    )

    tolerance = max(
        3.0,
        target_grams * 0.03,
    )

    final_weight = (
        scale.wait_for_target(
            target_grams=(
                target_grams
            ),
            tolerance_grams=(
                tolerance
            ),
            display=display,
        )
    )

    if final_weight >= 1000:

        final_spoken = (
            f"{final_weight / 1000:.2f}"
            .rstrip("0")
            .rstrip(".")
            + " kilograms"
        )

    else:

        final_spoken = (
            f"{final_weight:.0f} grams"
        )

    complete_message = (
        f"That's enough. "
        f"You've reached approximately "
        f"{final_spoken}."
    )

    print(
        f"\nChefAI: "
        f"{complete_message}"
    )

    tts.speak(
        complete_message
    )

    return True

def is_timer_command(
    text: str,
) -> bool:

    normalized = normalize_text(
        text
    )

    timer_keywords = (
        "timer",
        "set a timer",
        "start a timer",
        "start timer",
    )

    return any(
        keyword in normalized
        for keyword in timer_keywords
    )

def handle_direct_timer_command(
    text: str,
    tts: TextToSpeech,
    display: DisplayManager,
) -> bool:
    """
    Handle commands like:

        start a timer for 5 seconds
        set a timer for three minutes
        start timer for 1 hour

    Returns True if the message was
    handled as a timer command.
    """

    if not is_timer_command(
        text
    ):
        return False

    duration = extract_duration(
        text
    )

    if duration is None:

        response = (
            "I heard a timer request, "
            "but I could not understand "
            "the duration."
        )

        print(
            f"\nChefAI: {response}"
        )

        tts.speak(
            response
        )

        return True

    duration_seconds = (
        duration[
            "seconds"
        ]
    )

    spoken_duration = (
        duration[
            "spoken"
        ]
    )

    timer_manager = (
        get_timer_manager()
    )

    timer_manager.start_timer(
        duration_seconds=(
            duration_seconds
        ),
        label=(
            f"{spoken_duration} timer"
        ),
        display=display,
    )

    response = (
        f"Okay. I started a "
        f"{spoken_duration} timer."
    )

    print(
        f"\nChefAI: {response}"
    )

    tts.speak(
        response
    )

    return True

def listen_for_user(
    filename: str,
) -> str:

    audio_path = (
        record_until_silence(
            filename=str(
                TEMP_DIRECTORY
                / filename
            ),
            start_timeout=8.0,
        )
    )

    if audio_path is None:

        return ""

    return (
        transcribe_audio(
            audio_path
        )
        .strip()
    )


def get_current_step():
    """
    Return information about the
    currently active cooking step.
    """

    recipe = get_current_recipe()

    if recipe is None:

        return None

    steps = recipe.get(
        "steps",
        [],
    )

    if not steps:

        return None

    current_step = recipe.get(
        "current_step",
        0,
    )

    if (
        current_step < 0
        or current_step >= len(steps)
    ):

        return None

    return {
        "recipe":
            recipe,

        "step_number":
            current_step + 1,

        "step_text":
            steps[current_step],

        "total_steps":
            len(steps),
    }


def update_recipe_display(
    display: DisplayManager,
) -> bool:

    step_info = (
        get_current_step()
    )

    if step_info is None:

        return False

    recipe = (
        step_info[
            "recipe"
        ]
    )

    display.show_cooking_step(
        recipe_title=recipe.get(
            "title",
            "Recipe",
        ),
        step_number=(
            step_info[
                "step_number"
            ]
        ),
        total_steps=(
            step_info[
                "total_steps"
            ]
        ),
        step_text=(
            step_info[
                "step_text"
            ]
        ),
    )

    return True


def wait_for_scale_container(
    tts: TextToSpeech,
) -> None:
    """
    Wait until the user confirms that the empty
    bowl/container is on the scale.
    """

    message = (
        "Place your empty bowl or container "
        "on the scale. Say ready when "
        "you have placed it."
    )

    print(
        f"\nChefAI: {message}"
    )

    tts.speak(
        message
    )

    time.sleep(
        0.5
    )

    ready_phrases = {
        "ready",
        "done",
        "i am ready",
        "im ready",
        "i added it",
        "i put it",
        "i placed it",
        "its there",
        "it is there",
        "container ready",
        "bowl ready",
        "yes",
        "okay",
        "ok",
    }

    while True:

        print(
            "\n[SCALE] Waiting for "
            "container confirmation..."
        )

        response = listen_for_user(
            filename="scale_ready.wav"
        )

        if not response:
            continue

        normalized_response = (
            normalize_text(
                response
            )
        )

        print(
            f"[SCALE] User: {response}"
        )

        if (
            normalized_response
            in ready_phrases
        ):

            return

        reminder = (
            "Say ready when the empty "
            "container is on the scale."
        )

        print(
            f"ChefAI: {reminder}"
        )

        tts.speak(
            reminder
        )

        time.sleep(
            0.5
        )

def maybe_offer_scale(
    tts: TextToSpeech,
    display: DisplayManager,
    last_weight_step_key,
):
    """
    Detect a weight amount in the current
    cooking step and offer to start the scale.

    Returns the updated step key.
    """

    step_info = (
        get_current_step()
    )

    if step_info is None:

        return (
            last_weight_step_key
        )

    recipe = (
        step_info[
            "recipe"
        ]
    )

    step_number = (
        step_info[
            "step_number"
        ]
    )

    step_text = (
        step_info[
            "step_text"
        ]
    )

    recipe_id = (
        recipe.get(
            "id",
            recipe.get(
                "title",
                "recipe",
            ),
        )
    )

    step_key = (
        f"{recipe_id}:"
        f"{step_number}"
    )

    if (
        step_key
        == last_weight_step_key
    ):

        return (
            last_weight_step_key
        )

    weight = (
        extract_weight(
            step_text
        )
    )

    if weight is None:

        return (
            last_weight_step_key
        )

    target_grams = (
        weight[
            "grams"
        ]
    )

    if target_grams >= 1000:

        target_spoken = (
            f"{target_grams / 1000:.2f}"
            .rstrip("0")
            .rstrip(".")
            + " kilograms"
        )

    else:

        target_spoken = (
            f"{target_grams:.0f} grams"
        )

    question = (
        f"This step requires "
        f"{target_spoken}. "
        f"Would you like me "
        f"to start the scale?"
    )

    print(
        f"\nChefAI: "
        f"{question}"
    )

    tts.speak(
        question
    )

    time.sleep(
        0.5
    )

    display.show_listening()

    response = (
        listen_for_user(
            filename=(
                "scale_confirmation.wav"
            )
        )
    )

    if not response:

        print(
            "[SCALE] "
            "No confirmation received."
        )

        return step_key

    print(
        f"[SCALE RESPONSE] "
        f"{response}"
    )

    if is_no(
        response
    ):

        print(
            "[SCALE] "
            "User declined scale."
        )

        return step_key

    if not is_yes(
        response
    ):

        print(
            "[SCALE] "
            "Confirmation unclear."
        )

        return step_key

    # ----------------------------------------
    # User accepted the scale.
    # ----------------------------------------

    scale = (
        get_weight_sensor()
    )

    wait_for_scale_container(
        tts=tts
    )

    tare_message = (
        "Okay. I will tare "
        "the scale now."
    )

    print(
        f"ChefAI: "
        f"{tare_message}"
    )

    tts.speak(
        tare_message
    )

    scale.tare()

    start_message = (
        f"Okay. Start adding "
        f"the ingredient. "
        f"The target is "
        f"{target_spoken}."
    )

    print(
        f"ChefAI: "
        f"{start_message}"
    )

    tts.speak(
        start_message
    )

    tolerance = max(
        3.0,
        target_grams * 0.03,
    )

    final_weight = (
        scale.wait_for_target(
            target_grams=(
                target_grams
            ),
            tolerance_grams=(
                tolerance
            ),
            display=display,
        )
    )

    if final_weight >= 1000:

        final_spoken = (
            f"{final_weight / 1000:.2f}"
            .rstrip("0")
            .rstrip(".")
            + " kilograms"
        )

    else:

        final_spoken = (
            f"{final_weight:.0f} grams"
        )

    complete_message = (
        f"That's enough. "
        f"You've reached approximately "
        f"{final_spoken}."
    )

    print(
        f"\nChefAI: "
        f"{complete_message}"
    )

    tts.speak(
        complete_message
    )

    return step_key

def maybe_offer_timer(
    tts: TextToSpeech,
    display: DisplayManager,
    last_timer_step_key,
):
    """
    Inspect the current recipe step.

    If it contains a duration and we have
    not already asked about this particular
    step, ask the user whether a timer
    should be started.

    Returns:
        updated last_timer_step_key
    """

    step_info = (
        get_current_step()
    )

    if step_info is None:

        return (
            last_timer_step_key
        )

    recipe = (
        step_info[
            "recipe"
        ]
    )

    step_number = (
        step_info[
            "step_number"
        ]
    )

    step_text = (
        step_info[
            "step_text"
        ]
    )

    recipe_id = (
        recipe.get(
            "id",
            recipe.get(
                "title",
                "recipe",
            ),
        )
    )

    step_key = (
        f"{recipe_id}:"
        f"{step_number}"
    )

    # We already offered a timer
    # for this exact step.
    if (
        step_key
        == last_timer_step_key
    ):

        return (
            last_timer_step_key
        )

    duration = (
        extract_duration(
            step_text
        )
    )

    # No timer in this step.
    if duration is None:

        return (
            last_timer_step_key
        )

    spoken_duration = (
        duration[
            "spoken"
        ]
    )

    duration_seconds = (
        duration[
            "seconds"
        ]
    )

    question = (
        f"This step has a "
        f"{spoken_duration} timer. "
        f"Should I start it?"
    )

    print(
        f"\nChefAI: {question}"
    )

    tts.speak(
        question
    )

    time.sleep(
        0.5
    )

    display.show_listening()

    response = listen_for_user(
        filename=(
            "timer_confirmation.wav"
        )
    )

    # --------------------------------------------------------
    # Silence here does NOT end the session.
    # We simply don't start the timer.
    # --------------------------------------------------------

    if not response:

        print(
            "[TIMER] No confirmation "
            "received."
        )

        return step_key

    print(
        f"[TIMER RESPONSE] "
        f"{response}"
    )

    if is_yes(
        response
    ):

        timer_manager = (
            get_timer_manager()
        )

        timer_manager.start_timer(
            duration_seconds=(
                duration_seconds
            ),
            label=(
                f"{recipe.get('title', 'Recipe')} "
                f"- Step {step_number}"
            ),
            display=display,
        )

        confirmation = (
            f"Okay. I started a "
            f"{spoken_duration} timer."
        )

        print(
            f"ChefAI: {confirmation}"
        )

        tts.speak(
            confirmation
        )

    elif is_no(
        response
    ):

        print(
            "[TIMER] User declined timer."
        )

    else:

        print(
            "[TIMER] Confirmation "
            "was unclear. Timer not started."
        )

    return step_key


def wait_for_follow_up(
) -> str:
    """
    Keep listening until the user speaks.

    Silence no longer ends the session.
    """

    while True:

        print(
            "\nListening for your response..."
        )

        user_message = (
            listen_for_user(
                filename="follow_up.wav"
            )
        )

        if user_message:

            return user_message

        print(
            "No speech detected. "
            "Session remains active."
        )


def main() -> None:

    print(
        "ChefAI starting..."
    )

    TEMP_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Load Piper once
    tts = TextToSpeech()

    display = (
        DisplayManager()
    )

    while True:

        # ====================================================
        # WAKE WORD MODE
        # ====================================================

        wait_for_wake_word()

        display.show_idle()

        print(
            "Yes?"
        )

        tts.speak(
            "How can I help you?"
        )

        # Give speaker playback
        # a moment to fully stop.
        time.sleep(
            0.5
        )

        conversation_history: list[
            dict[str, str]
        ] = []

        # Prevent repeatedly asking
        # about the same cooking step.
        last_timer_step_key = None
        last_weight_step_key = None

        display.show_listening()

        # ====================================================
        # FIRST QUESTION
        # ====================================================

        user_message = (
            listen_for_user(
                filename=(
                    "question.wav"
                )
            )
        )

        # ----------------------------------------------------
        # FIRST wake-word question is special:
        #
        # If the user wakes ChefAI but never says anything,
        # returning to wake-word mode is still reasonable.
        # ----------------------------------------------------

        if not user_message:

            print(
                "No question detected. "
                "Returning to "
                "wake-word mode.\n"
            )

            continue

        # ====================================================
        # ACTIVE SESSION
        # ====================================================

        while True:

            print(
                f"\nYou: "
                f"{user_message}"
            )

            # ------------------------------------------------
            # Explicit session ending ONLY.
            # ------------------------------------------------

            if should_end_session(
                user_message
            ):

                goodbye = (
                    "Okay. Call me "
                    "when you need me."
                )

                print(
                    f"\nChefAI: "
                    f"{goodbye}"
                )

                tts.speak(
                    goodbye
                )

                break

            # ------------------------------------------------
            # DIRECT TIMER COMMAND
            # ------------------------------------------------

            if handle_direct_timer_command(
                text=user_message,
                tts=tts,
                display=display,
            ):

                conversation_history.append(
                    {
                        "role": "user",
                        "content": user_message,
                    }
                )

                conversation_history.append(
                    {
                        "role": "assistant",
                        "content": (
                            "Timer started."
                        ),
                    }
                )

                time.sleep(
                    0.5
                )

                display.show_listening()

                user_message = (
                    wait_for_follow_up()
                )

                continue

            # ------------------------------------------------
            # DIRECT WEIGHT COMMAND
            # ------------------------------------------------

            if handle_direct_weight_command(
                text=user_message,
                tts=tts,
                display = display,
            ):

                conversation_history.append(
                    {
                        "role":
                            "user",

                        "content":
                            user_message,
                    }
                )

                conversation_history.append(
                    {
                        "role":
                            "assistant",

                        "content":
                            "Weight measurement completed.",
                    }
                )

                time.sleep(
                    0.5
                )

                display.show_listening()

                user_message = (
                    wait_for_follow_up()
                )

                continue




            print(
                "Thinking..."
            )

            display.show_thinking()

            try:

                # ============================================
                # LANGGRAPH
                # ============================================

                thinking_start = (
                    time.perf_counter()
                )

                result = run_chef_graph(
                    user_message=(
                        user_message
                    ),
                    conversation_history=(
                        conversation_history
                    ),
                )

                thinking_time = (
                    time.perf_counter()
                    - thinking_start
                )

                print(
                    f"\n[TIMING] ChefAI reasoning: "
                    f"{thinking_time:.2f} seconds"
                )

                answer = (
                    result[
                        "answer"
                    ]
                )

                intent = (
                    result[
                        "intent"
                    ]
                )

                update_recipe_display(
                    display
                )

            except Exception as error:

                print(
                    f"ChefAI graph error: "
                    f"{error}"
                )

                failure_message = (
                    "Sorry, I could not "
                    "process your question."
                )

                tts.speak(
                    failure_message
                )

                # --------------------------------------------
                # IMPORTANT:
                #
                # A graph failure also should not
                # automatically kill the cooking session.
                # --------------------------------------------

                user_message = (
                    wait_for_follow_up()
                )

                continue

            # =================================================
            # Debug output
            # =================================================

            print(
                f"\nIntent: "
                f"{intent}"
            )

            print(
                f"\nChefAI: "
                f"{answer}"
            )

            # =================================================
            # Store conversation
            # =================================================

            conversation_history.append(
                {
                    "role":
                        "user",

                    "content":
                        user_message,
                }
            )

            conversation_history.append(
                {
                    "role":
                        "assistant",

                    "content":
                        answer,
                }
            )

            # =================================================
            # Speak response
            # =================================================

            tts_start = (
                time.perf_counter()
            )

            tts.speak(
                answer
            )

            tts_time = (
                time.perf_counter()
                - tts_start
            )

            print(
                f"[TIMING] TTS + playback: "
                f"{tts_time:.2f} seconds"
            )

            time.sleep(
                0.5
            )

            # =================================================
            # TIMER CHECK
            # =================================================
            last_weight_step_key = (
                maybe_offer_scale(
                    tts=tts,
                    display=display,
                    last_weight_step_key=(
                        last_weight_step_key
                    ),
                )
            )

            last_timer_step_key = (
                maybe_offer_timer(
                    tts=tts,
                    display=display,
                    last_timer_step_key=(
                        last_timer_step_key
                    ),
                )
            )


            # =================================================
            # FOLLOW-UP
            #
            # Silence DOES NOT end session.
            # =================================================

            display.show_listening()

            user_message = (
                wait_for_follow_up()
            )

        # ====================================================
        # RETURN TO WAKE WORD
        # ====================================================

        display.show_idle()

        print(
            "\nReturning to "
            "wake-word mode...\n"
        )


if __name__ == "__main__":

    main()