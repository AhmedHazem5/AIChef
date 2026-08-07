from llm.local_llm import ask_chef
from memory.context import build_memory_context
from memory.memory_manager import load_memory
from memory.cooking_session import get_current_recipe


def chat_node(state):

    memory = load_memory()

    memory_context = build_memory_context(memory)

    current_recipe = get_current_recipe()

    recipe_context = ""

    if current_recipe:

        title = current_recipe.get(
            "title",
            "Current recipe"
        )

        steps = current_recipe.get(
            "steps",
            []
        )

        current_step_index = current_recipe.get(
            "current_step",
            0
        )

        current_step = None

        if (
            steps
            and 0 <= current_step_index < len(steps)
        ):
            current_step = steps[current_step_index]

        recipe_context = f"""

CURRENT COOKING SESSION

Recipe:
{title}

Current step:
{current_step_index + 1}

Current step instructions:
{current_step}

All recipe steps:
"""

        for index, step in enumerate(steps, start=1):
            recipe_context += (
                f"\nStep {index}: {step}"
            )

    enhanced_message = f"""
You are ChefAI, a personal cooking assistant.

{memory_context}

{recipe_context}

USER MESSAGE:
{state["user_message"]}

IMPORTANT RULES:

1. If the user is asking about the current recipe,
   answer using the current recipe information above.

2. Do NOT invent ingredients or instructions that are not
   supported by the current recipe unless you clearly explain
   that you are giving a general cooking suggestion.

3. If the user asks whether they can substitute an ingredient,
   explain the practical effect of the substitution.

4. If the user asks why a step is necessary, explain the purpose
   of that step in the context of the current recipe.

5. Do NOT start a different recipe.

6. Do NOT perform a new recipe search.

7. If the user asks for a completely new recipe, answer normally.

8. Respect the user's stored allergies and dislikes.

9. Keep spoken answers concise and natural because this assistant
   is voice-controlled.
"""

    answer = ask_chef(
        user_message=enhanced_message,
        conversation_history=state["conversation_history"],
    )

    return {
        "answer": answer,
        "memory": memory,
    }