import ollama


MODEL_NAME = "qwen3:4b-instruct"


INTENT_PROMPT = """
You classify requests for a personal chef assistant.

Choose exactly ONE of these categories:

RECIPE_SEARCH
- The user wants a recipe, meal, food idea, recommendation, or dish.
- Includes requests based on ingredients, calories, protein, macros,
  cuisine, meal type, preferences, or vague requests such as
  "what should I eat today?"

MEMORY_UPDATE
- The user states a long-term personal preference or asks the assistant
  to remember something.
- Includes likes, dislikes, allergies, dietary preferences, food goals,
  or favorite foods.

COOKING_COMMAND
- The user is currently cooking and wants to control the recipe session.
- Examples: next step, repeat, go back, pause, continue.

GENERAL_QUESTION
- A cooking or food question that does not require finding a recipe,
  updating memory, or controlling an active cooking session.

Examples:

"What should I eat today?"
RECIPE_SEARCH

"I want something high in protein."
RECIPE_SEARCH

"I feel like having something light tonight."
RECIPE_SEARCH

"I really hate mushrooms."
MEMORY_UPDATE

"Peanuts are dangerous for me."
MEMORY_UPDATE

"Next step."
COOKING_COMMAND

"What does sauté mean?"
GENERAL_QUESTION

Return ONLY the category name.
"""


VALID_INTENTS = {
    "RECIPE_SEARCH",
    "MEMORY_UPDATE",
    "COOKING_COMMAND",
    "GENERAL_QUESTION",
}


def classify_with_qwen(user_message: str) -> str:
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
    )

    intent = (
        response["message"]["content"]
        .strip()
        .upper()
    )

    if intent not in VALID_INTENTS:
        return "GENERAL_QUESTION"

    return intent