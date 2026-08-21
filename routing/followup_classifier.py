import ollama
import time

MODEL_NAME = "qwen3:4b-instruct"


def is_similar_recipe_followup(
    user_message: str,
    blocked_recipe: dict,
) -> bool:

    # ========================================================
    # Fast deterministic handling for simple confirmations.
    #
    # This avoids an unnecessary LLM call for common replies
    # such as "yes", "sure", or "okay".
    # ========================================================

    normalized = (
        user_message
        .lower()
        .strip()
        .replace(".", "")
        .replace("!", "")
        .replace("?", "")
    )

    affirmative_replies = {
        "yes",
        "yes please",
        "yeah",
        "yep",
        "sure",
        "okay",
        "ok",
        "please",
        "go ahead",
        "sounds good",
    }

    if normalized in affirmative_replies:

        print(
            "\nFollow-up classifier label: "
            "SIMILAR_RECIPE "
            "(deterministic)"
        )

        return True

    title = blocked_recipe.get(
        "title",
        "the previous recipe",
    )

    cuisine = blocked_recipe.get(
        "cuisine",
        "Unknown",
    )

    prompt = f"""
You are the follow-up intent classifier for ChefAI.

Previous situation:

The user asked for this recipe:
"{title}"

Cuisine:
"{cuisine}"

ChefAI refused that recipe or request because it conflicted with the
user's saved allergies or dietary preferences.

ChefAI then asked:

"Would you like me to suggest a similar safe recipe instead?"

The user's NEW message is:

"{user_message}"


Your job is to determine what the user means.

Return EXACTLY ONE of these labels:

SIMILAR_RECIPE
NEW_RECIPE_REQUEST
OTHER


============================================================
SIMILAR_RECIPE
============================================================

Use SIMILAR_RECIPE only when the user is accepting or requesting
a safe alternative to the PREVIOUS blocked recipe.

Examples:

"yes"
"yes please"
"sure"
"okay"
"give me something similar"
"recommend something similar"
"find me a safe alternative"
"another similar recipe"
"what is a similar safe option?"
"give me something else like that"


============================================================
NEW_RECIPE_REQUEST
============================================================

Use NEW_RECIPE_REQUEST when the user starts a new recipe search
or gives new meaningful constraints.

This includes:

- naming a new recipe
- naming a cuisine
- naming ingredients
- naming a dish type
- asking for soup, noodles, rice, chicken, beef, etc.
- asking a broad recommendation question
- changing what they want to eat

Examples:

"Give me a Chinese noodle recipe."
"I want Sweet and Sour Chicken."
"Give me something Japanese."
"Find me something with beef."
"What can I eat today?"
"I want a soup."
"Give me something vegetarian."
"I want chicken and rice."
"Can I make ramen?"
"Give me a Chinese recipe without peanuts."


IMPORTANT:

A message is NEW_RECIPE_REQUEST if the user introduces a new
specific preference or search constraint, even if ChefAI just
offered a similar safe alternative.

For example:

Previous blocked recipe:
Kung Pao Chicken

User says:
"Give me a Chinese noodle recipe."

Correct label:
NEW_RECIPE_REQUEST

It is NOT SIMILAR_RECIPE just because it came after the offer.


============================================================
OTHER
============================================================

Use OTHER when the message is unrelated to accepting the alternative
and is not a new recipe request.

Examples:

"no"
"not now"
"stop"
"thank you"
"why is it unsafe?"
"what allergy caused the problem?"


Return ONLY the label.

Do not explain.
Do not add punctuation.
Do not output anything except one of the three labels.
"""
    start = time.perf_counter()
    response = ollama.chat(
        model=MODEL_NAME,
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
        options={
            "temperature": 0,
            "num_ctx": 2048,
        },
        think=False,
        keep_alive="30m",
    )

    elapsed = (
        time.perf_counter()
        - start
    )

    print(
        f"[TIMING] follow-up classifier: "
        f"{elapsed:.2f} seconds"
    )

    label = (
        response["message"]["content"]
        .strip()
        .upper()
    )

    print(
        "\nFollow-up classifier label:",
        label,
    )

    return (
        label == "SIMILAR_RECIPE"
    )