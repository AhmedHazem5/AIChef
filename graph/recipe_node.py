from llm.local_llm import generate_recipe_plan

from memory.context import build_memory_context
from memory.cooking_session import start_recipe, get_current_step
from memory.memory_manager import load_memory
from rag.recipe_parser import parse_recipe_response
from rag.query_engine import (
    retrieve_recipe_context,
    recipe_database_is_empty,
)
from memory.cooking_session import get_current_recipe



def recipe_node(state):

    memory = load_memory()

    recipe_context = retrieve_recipe_context(
        state["user_message"]
    )

    if not recipe_context:

        if recipe_database_is_empty():

            return {
                "answer":
                "My recipe database is currently empty."
            }

        return {
            "answer":
            "I couldn't find that recipe."
        }

    memory_context = build_memory_context(memory)

    raw_recipe = generate_recipe_plan(
        user_message=memory_context +
        "\n\nUser Request:\n" +
        state["user_message"],

        retrieved_context=recipe_context,

        conversation_history=state["conversation_history"],
    )

    parsed_recipe = parse_recipe_response(raw_recipe)

    steps = parsed_recipe.get("steps", [])

    if not steps:
        return {
            "answer": "I found the recipe, but I couldn't parse the steps cleanly.",
            "memory": memory,
        }

    start_recipe(
    title=parsed_recipe.get("title", "Recipe"),
    ingredients=parsed_recipe.get("ingredients", []),
    steps=steps,
)
                  
    print("\nRecipe session created:")
    print(get_current_recipe())
    first_step = get_current_step()

    if not first_step:
        return {
            "answer": "I found the recipe, but I couldn't start the cooking session.",
            "memory": memory,
        }

    ingredients = parsed_recipe.get("ingredients", [])

    ingredients_text = ""

    if ingredients:
        ingredients_text = (
            "\n\nIngredients:\n- " +
            "\n- ".join(ingredients)
        )

    answer = (
        f"Let's make {parsed_recipe.get('title', 'this recipe')}."
        f"{ingredients_text}"
        f"\n\nStep 1:\n{first_step}"
        "\n\nSay \"next\" when you're ready."
    )

    return {
        "answer": answer,
        "memory": memory,
    }