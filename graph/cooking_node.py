import re

from memory.cooking_session import (
    finish_recipe,
    get_current_recipe,
    get_current_step,
    has_active_recipe,
    next_step,
    previous_step,
    repeat_step,
    start_over,
)


# ============================================================
# Extract Step Number
# ============================================================

def extract_step_number(command: str):
    """
    Extract a step number from commands such as:

    repeat step 2
    repeat step two
    go to step 3
    """

    number_words = {
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
    }

    # Example: "repeat step 2"
    match = re.search(r"\bstep\s+(\d+)\b", command)

    if match:
        return int(match.group(1))

    # Example: "repeat step two"
    match = re.search(
        r"\bstep\s+(one|two|three|four|five|six|seven|eight|nine|ten)\b",
        command,
    )

    if match:
        return number_words[match.group(1)]

    return None


# ============================================================
# Cooking Node
# ============================================================

def cooking_node(state):

    command = state["user_message"].lower().strip()

    # --------------------------------------------------------
    # Normalize speech-recognition punctuation
    # --------------------------------------------------------

    command = command.replace('"', "")
    command = command.replace("'", "")

    command = re.sub(
        r"[.!?,;:]+",
        " ",
        command,
    )

    command = re.sub(
        r"\s+",
        " ",
        command,
    )

    command = command.strip()

    print(f"Cooking command: '{command}'")

    # ========================================================
    # No active recipe
    # ========================================================

    if not has_active_recipe():
        return {
            "answer": (
                "There is no active recipe right now. "
                "Ask me for a recipe first."
            )
        }

    # ========================================================
    # NEXT
    # ========================================================

    if command in {
        "next",
        "next step",
        "continue",
        "continue recipe",
        "go on",
        "go to next step",
    }:

        result = next_step()

        if result is None:
            return {
                "answer": "There is no active recipe right now."
            }

        return {
            "answer": result
        }

    # ========================================================
    # REPEAT CURRENT STEP
    # ========================================================

    if command in {
        "repeat",
        "repeat that",
        "repeat step",
        "repeat current step",
        "say that again",
    }:

        step = repeat_step()

        if step is None:
            return {
                "answer": "There is no active recipe right now."
            }

        return {
            "answer": step
        }

    # ========================================================
    # REPEAT SPECIFIC STEP
    # ========================================================

    step_number = extract_step_number(command)

    if (
        step_number is not None
        and "repeat" in command
    ):

        recipe = get_current_recipe()

        if recipe is None:
            return {
                "answer": "There is no active recipe right now."
            }

        steps = recipe.get("steps", [])

        if step_number < 1 or step_number > len(steps):
            return {
                "answer": (
                    f"This recipe only has {len(steps)} steps."
                )
            }

        return {
            "answer": steps[step_number - 1]
        }

    # ========================================================
    # PREVIOUS
    # ========================================================

    if command in {
        "previous",
        "previous step",
        "go back",
        "back",
        "go to previous step",
    }:

        step = previous_step()

        if step is None:
            return {
                "answer": "There is no active recipe right now."
            }

        return {
            "answer": step
        }

    # ========================================================
    # START OVER
    # ========================================================

    if command in {
        "start over",
        "restart",
        "restart recipe",
        "start recipe over",
        "start from beginning",
        "start from step one",
        "start the recipe from step one",
        "make it again",
        "cook it again",
    }:

        step = start_over()

        if step is None:
            return {
                "answer": "There is no active recipe right now."
            }

        return {
            "answer": (
                "Starting the recipe again.\n\n"
                f"Step 1:\n{step}"
            )
        }

    # ========================================================
    # FINISH
    # ========================================================

    if command in {
        "finish",
        "finish recipe",
        "stop recipe",
        "end recipe",
    }:

        finish_recipe()

        return {
            "answer": "Okay, I finished the recipe session."
        }

    # ========================================================
    # PAUSE
    # ========================================================

    if command in {
        "pause",
        "pause recipe",
    }:

        current_step = get_current_step()

        if current_step is None:
            return {
                "answer": "There is no active recipe right now."
            }

        finish_recipe()

        return {
            "answer": (
                "Okay, I paused the recipe. "
                "You can ask me for the recipe again when you're ready."
            )
        }

    # ========================================================
    # UNKNOWN COOKING COMMAND
    # ========================================================

    return {
        "answer": (
            "I can help with next, previous, repeat, "
            "start over, pause, or finish."
        )
    }