import ollama


MODEL_NAME = "qwen3:4b-instruct"


INTENT_PROMPT = """
You classify requests for a personal chef assistant.

Choose exactly ONE of these categories:

RECIPE_SEARCH

- The user wants a new recipe, meal, food idea, recommendation, or dish.
- Examples:
  "Give me a pasta recipe."
  "Recommend a Mexican meal."
  "I want something spicy."
  "What should I eat tonight?"

RECIPE_QUESTION

- The user is asking a question about a recipe they are currently
  cooking.
- This does NOT mean they want a new recipe.
- Examples:
  "Can I replace the olive oil?"
  "I don't have garlic, what can I use instead?"
  "Why do I need to peel the tomatoes?"
  "How long should I cook this?"
  "Can I skip this ingredient?"
  "What temperature should I use?"
  "Can I use butter instead?"

MEMORY_UPDATE

- The user states a long-term personal preference or asks the assistant
  to remember something.
- Includes likes, dislikes, allergies, dietary preferences, food goals,
  or favorite foods.
- Examples:
  "I hate mushrooms."
  "I am allergic to peanuts."
  "I love spicy food."

MEMORY_QUERY

- The user asks what the assistant remembers about them.
- Examples:
  "What do I dislike?"
  "What are my allergies?"
  "List my preferences."
  "What do you know about me?"

COOKING_COMMAND

- The user is currently cooking and wants to control the recipe session.
- Examples:
  "Next."
  "Continue."
  "Repeat that."
  "Go back."
  "Pause."
  "Finish."

GENERAL_QUESTION

- A cooking or food question that does not require a new recipe,
  memory update/query, or control of the cooking session.
- Examples:
  "What does sauté mean?"
  "What is al dente?"
  "What is the difference between basil and oregano?"

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

    if not response or "message" not in response:
        return "GENERAL_QUESTION"

    intent = (
        response["message"]["content"]
        .strip()
        .upper()
    )

    if intent not in VALID_INTENTS:
        return "GENERAL_QUESTION"

    return intent