import ollama
import time

MODEL_NAME = "qwen3:4b-instruct"


INTENT_PROMPT = """
You classify requests for a personal chef assistant.

Choose exactly ONE of these categories:


RECIPE_SEARCH

- The user wants a new recipe, meal, food idea, recommendation, or dish.
- This includes requests containing temporary meal constraints such as:
  cuisine, ingredients, calories, protein, carbohydrates, fat,
  or other nutrition preferences.
- Statements such as "I want something..." or "Give me something..."
  are RECIPE_SEARCH when they describe what the user wants to eat now.
- A nutrition preference in a recipe request is NOT automatically
  a MEMORY_UPDATE.

Examples:
  "Give me a pasta recipe."
  "Recommend a Mexican meal."
  "I want something spicy."
  "What should I eat tonight?"
  "I want something high in protein."
  "I want something low calorie."
  "We want to eat something with low calories."
  "Give me something low fat."
  "I want a low carb meal."
  "Give me a recipe under 1000 calories."
  "I want chicken and garlic under 1500 calories."
  "Give me a Chinese recipe with at least 80 grams of protein."


RECIPE_QUESTION

- The user is asking a question about a recipe they are currently
  cooking.
- This does NOT mean they want a new recipe.

Examples:
  "Can I replace the olive oil?"
  "I don't have garlic, what can I use instead?"
  "Why do I need to peel the tomatoes?"
  "How long should I cook this?"
  "Can I skip this ingredient?"
  "What temperature should I use?"
  "Can I use butter instead?"


MEMORY_UPDATE

- The user explicitly states a long-term personal preference,
  personal dietary fact, allergy, goal, or asks the assistant
  to remember something for future requests.
- Use MEMORY_UPDATE when the statement is about the USER,
  not merely about the meal they currently want.
- Explicit phrases such as "remember that", "from now on",
  "I always prefer", "my goal is", "I am allergic to","Remember that"
  and persistent likes/dislikes strongly indicate MEMORY_UPDATE.
- Do NOT classify a current recipe request as MEMORY_UPDATE
  merely because it contains words such as low calorie,
  high protein, low fat, or low carb.

Examples:
  "Remember that I prefer low-calorie meals."
  "My goal is to eat more protein."
  "From now on, I want to eat low-fat meals."
  "I hate mushrooms."
  "I am allergic to peanuts."
  "I love spicy food."


MEMORY_QUERY

- The user asks what the assistant remembers about them.

Examples:
  "What do I dislike?"
  "What are my allergies?"
  "List my preferences."
  "What do you know about me?"


COOKING_COMMAND

- The user is currently cooking and wants to control the recipe session.

Examples:
  "Next."
  "Continue."
  "Repeat that."
  "Go back."
  "Pause."
  "Finish."


GENERAL_QUESTION

- A cooking or food question that does not require a new recipe,
  memory update/query, or control of the cooking session.

Examples:
  "What does sauté mean?"
  "What is al dente?"
  "What is the difference between basil and oregano?"


IMPORTANT DISTINCTION:

"I want something low calorie."
-> RECIPE_SEARCH

"Give me a high-protein meal."
-> RECIPE_SEARCH

"Find me something low fat."
-> RECIPE_SEARCH

"Remember that I prefer low-calorie meals."
-> MEMORY_UPDATE

"My long-term goal is to eat more protein."
-> MEMORY_UPDATE


Return ONLY the category name.
"""

VALID_INTENTS = {
    "RECIPE_SEARCH",
    "RECIPE_QUESTION",
    "MEMORY_UPDATE",
    "MEMORY_QUERY",
    "COOKING_COMMAND",
    "GENERAL_QUESTION",
}


def classify_with_qwen(
    user_message: str,
) -> str:

    normalized = (
        user_message
        .lower()
        .strip()
    )

    # --------------------------------------------------------
    # Fast deterministic rules
    # --------------------------------------------------------

    memory_update_triggers = (
        "remember that",
        "from now on",
        "i always prefer",
        "i always like",
        "i always dislike",
        "my goal is",
        "my long-term goal is",
        "i am allergic to",
        "i'm allergic to",
        "i hate ",
        "i love ",
        "i like ",
        "i dislike ",
    )

    memory_query_triggers = (
        "what do you remember",
        "what do you know about me",
        "what are my preferences",
        "what are my allergies",
        "what do i dislike",
        "what do i like",
        "list my preferences",
    )

    if any(
        trigger in normalized
        for trigger in memory_query_triggers
    ):
        return "MEMORY_QUERY"

    if any(
        trigger in normalized
        for trigger in memory_update_triggers
    ):
        return "MEMORY_UPDATE"

    # --------------------------------------------------------
    # Qwen classification
    # --------------------------------------------------------

    start = time.perf_counter()

    response = ollama.chat(
        model=MODEL_NAME,
        messages=[
            {
                "role": "system",
                "content": INTENT_PROMPT,
            },
            {
                "role": "user",
                "content": user_message,
            },
        ],
        options={
            "temperature": 0,
        },
        think=False,
        keep_alive="30m",
    )

    elapsed = (
        time.perf_counter()
        - start
    )

    print(
        f"[TIMING] intent classifier: "
        f"{elapsed:.2f} seconds"
    )

    if (
        not response
        or "message"
        not in response
    ):
        return "GENERAL_QUESTION"

    intent = (
        response[
            "message"
        ][
            "content"
        ]
        .strip()
        .upper()
    )

    if intent not in VALID_INTENTS:
        return "GENERAL_QUESTION"

    return intent