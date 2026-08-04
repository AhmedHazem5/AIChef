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
- When you ask the user a direct question, wait for their answer.
- Do not repeatedly ask whether the user has another question.
- Avoid markdown tables and excessive formatting.

Nutrition rules:
- Never estimate, calculate, guess, or invent calories or macros.
- Never provide protein, carbohydrate, fat, or calorie numbers unless
  the application explicitly supplies verified nutrition results.
- If the user asks for nutrition values before the nutrition tool is
  available, say that verified nutrition data is not available yet.
- Do not present approximate nutrition numbers from general knowledge.

Safety rules:
- Do not invent user allergies or dietary preferences.
- Do not claim that food is guaranteed allergen-free.
"""


def ask_chef(
    user_message: str,
    conversation_history: list[dict[str, str]],
) -> str:
    """
    Send the full conversation to the local Ollama model.

    conversation_history contains earlier user and assistant messages.
    """

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        }
    ]

    messages.extend(conversation_history)

    messages.append(
        {
            "role": "user",
            "content": user_message,
        }
    )

    response = ollama.chat(
        model=MODEL_NAME,
        messages=messages,
        options={
            "temperature": 0.3,
        },
    )

    answer = response["message"]["content"].strip()

    return answer