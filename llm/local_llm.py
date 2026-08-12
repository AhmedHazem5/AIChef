import ollama


MODEL_NAME = "qwen3:4b-instruct"


SYSTEM_PROMPT = """
You are ChefAI, a fully local personal chef assistant.

Conversation rules:
- Give concise responses designed to be spoken aloud.
- Recommend one meal unless the user asks for several.
- Remember and use the supplied conversation history.
- Understand follow-ups such as "yes", "continue", "tell me more",
  "what is the next step?", and "repeat that".
- When you ask the user a direct question, wait for the user's answer.
- Do not repeatedly ask whether the user has another question.
- Avoid markdown tables and excessive formatting.

Nutrition rules:
- Never estimate, calculate, guess, or invent calories or macros.
- Never provide nutrition numbers unless verified data is supplied.
- If nutrition data is unavailable, clearly state that.

Safety rules:
- Do not invent allergies or preferences.
- Do not claim food is allergen-free.
"""


def build_messages(
    user_message: str,
    conversation_history: list[dict[str, str]],
):
    """
    Build the chat history sent to Qwen.
    """

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        }
    ]

    MAX_HISTORY = 12

    messages.extend(
        conversation_history[-MAX_HISTORY:]
    )

    messages.append(
        {
            "role": "user",
            "content": user_message,
        }
    )

    return messages


def ask_chef(
    user_message: str,
    conversation_history: list[dict[str, str]],
) -> str:
    """
     General conversation.
    Used for greetings, cooking questions,
    follow-up conversation, etc.
    """

    response = ollama.chat(
        model=MODEL_NAME,
        messages=build_messages(
            user_message,
            conversation_history,
        ),
        options={
            "temperature": 0.3,
        },
    )

    return response["message"]["content"].strip()


def answer_with_context(
    question: str,
    retrieved_context: str,
    conversation_history: list[dict[str, str]],
) -> str:
    """
    Answer using retrieved RAG context.

    The model must rely primarily on the supplied context.
    """
    prompt = f"""
You are ChefAI.

The retrieved context comes from a recipe database.

Never copy the recipe verbatim.

Instead:

- Summarize naturally.
- Keep ingredient names accurate.
- Present steps in a clean numbered order.
- Mention cooking tips if available.
- Respect the user's saved preferences.
- If information is missing, say so.
- Do not invent ingredients or cooking times.

==============================
Retrieved Recipe Context
==============================

{retrieved_context}

==============================
User Question
==============================

{question}
"""

    response = ollama.chat(
        model=MODEL_NAME,
        messages=build_messages(
            prompt,
            conversation_history,
        ),
        options={
            "temperature": 0,
        },
    )

    return response["message"]["content"].strip()


def generate_recipe_plan(
    user_message: str,
    retrieved_context: str,
    conversation_history: list[dict[str, str]],
) -> str:

    prompt = f"""
You are ChefAI.

Your task is to create ONE usable recipe from the retrieved recipe context.

Return ONLY valid JSON.

The JSON must have exactly this structure:

{{
    "title": "Recipe name",
    "ingredients": [
        "ingredient 1",
        "ingredient 2"
    ],
    "steps": [
        "step 1",
        "step 2"
    ]
}}

STRICT RULES:

- The retrieved context is the ONLY source of recipe information.
- Use ONLY ingredients explicitly present in the retrieved context.
- NEVER add ingredients based on your own cooking knowledge.
- NEVER invent substitutions.
- NEVER add optional ingredients.
- NEVER invent garnishes.
- NEVER add sauces, seasonings, oils, toppings, or side ingredients unless they explicitly appear in the retrieved context.

- Respect ALL allergies and dietary restrictions given in the user context.
- NEVER include an ingredient that conflicts with a saved allergy.
- If the retrieved context contains both safe and unsafe ingredients, use only the safe recipe information if that still forms a valid recipe.
- If removing an unsafe ingredient would fundamentally change the recipe, do not invent a replacement.

- The ingredients field MUST be a JSON list of strings.
- The steps field MUST be a JSON list of strings.
- The title MUST be a JSON string.
- Ingredients must not be empty if a usable safe recipe exists.
- Steps must not be empty if a usable safe recipe exists.
- Keep cooking steps short and clear.
- Put only actual cooking instructions inside the steps list.

- Do not output markdown.
- Do not use ```json.
- Do not output explanations before or after the JSON.
- Do not output comments.
- Do not add any keys besides title, ingredients, and steps.
- Do not calculate or estimate calories or macros.

If the retrieved context does NOT contain enough information to create a complete safe recipe, return exactly:

{{
    "title": "",
    "ingredients": [],
    "steps": []
}}

==============================
Retrieved Recipe Context
==============================

{retrieved_context}

==============================
User Request and Memory
==============================

{user_message}
"""

    response = ollama.chat(
        model=MODEL_NAME,
        messages=build_messages(
            prompt,
            conversation_history[-4:],
        ),
        options={
            "temperature": 0,
            "num_ctx": 8192,
        },
        format="json",
    )

    raw_response = (
        response["message"]["content"]
        .strip()
    )

    print("\nRAW RECIPE RESPONSE:")
    print(raw_response)
    print()

    return raw_response