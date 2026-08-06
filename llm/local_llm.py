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

    messages.extend(conversation_history)

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
Use the retrieved recipe information below to answer the user's question.

If the answer is contained in the context,
use it.

If the context does not contain enough information,
say that the recipe database does not contain the requested information.

Retrieved Context:

{retrieved_context}

User Question:

{question}
"""

    response = ollama.chat(
        model=MODEL_NAME,
        messages=build_messages(
            prompt,
            conversation_history,
        ),
        options={
            "temperature": 0.2,
        },
    )

    return response["message"]["content"].strip()