import json

import ollama


MODEL_NAME = "qwen3:4b-instruct"


ALLOWED_CUISINES = {
    "Chinese",
    "Japanese",
    "Indian",
    "Italian",
    "Mexican",
    "Thai",
}


ALLOWED_CATEGORIES = {
    "Appetizers",
    "Beef",
    "Chicken",
    "Crab",
    "Desserts",
    "Egg",
    "Fish",
    "Lamb",
    "Noodles",
    "Pork",
    "Rice",
    "Shrimp",
    "Soup",
    "Tofu",
    "Vegetable",
}


def extract_recipe_constraints(
    user_message: str,
) -> dict:

    prompt = f"""
You extract explicit recipe-search constraints for ChefAI.

User request:

"{user_message}"

Return ONLY valid JSON with exactly these keys:

{{
    "cuisine": null,
    "category": null,
    "required_ingredients": []
}}

Allowed cuisine values:

Chinese
Japanese
Indian
Italian
Mexican
Thai

Allowed category values:

Appetizers
Beef
Chicken
Crab
Desserts
Egg
Fish
Lamb
Noodles
Pork
Rice
Shrimp
Soup
Tofu
Vegetable


============================================================
RULES
============================================================

1. Only extract constraints the user clearly requested.

2. Do not guess a cuisine.

3. Do not guess a category unless the user clearly asks for
   a dish type or food category.

4. required_ingredients must contain foods or ingredients that
   the user explicitly wants the final recipe to contain.

5. If the user says "with X and Y", both X and Y should appear
   in required_ingredients.

6. Do NOT put general words such as:
   recipe
   food
   meal
   something
   dish

   inside required_ingredients.

7. If an ingredient is already represented by a category,
   it may still appear in required_ingredients if the user
   explicitly said they want the ingredient present.

Examples:

"Give me a Chinese noodle recipe."

{{
    "cuisine": "Chinese",
    "category": "Noodles",
    "required_ingredients": []
}}

"I want something with garlic and chicken."

{{
    "cuisine": null,
    "category": null,
    "required_ingredients": [
        "garlic",
        "chicken"
    ]
}}

"Give me a Chinese recipe with shrimp."

{{
    "cuisine": "Chinese",
    "category": null,
    "required_ingredients": [
        "shrimp"
    ]
}}

"I want chicken and rice."

{{
    "cuisine": null,
    "category": null,
    "required_ingredients": [
        "chicken",
        "rice"
    ]
}}

"I want a soup with mushrooms."

{{
    "cuisine": null,
    "category": "Soup",
    "required_ingredients": [
        "mushrooms"
    ]
}}

"What can I eat today?"

{{
    "cuisine": null,
    "category": null,
    "required_ingredients": []
}}

"I want Sweet and Sour Chicken."

This is a named recipe request.
Do not infer ingredient constraints from the title.

{{
    "cuisine": null,
    "category": null,
    "required_ingredients": []
}}

Return ONLY the JSON.
Do not explain.
"""

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
    )

    raw = (
        response["message"]["content"]
        .strip()
    )

    try:

        data = json.loads(
            raw
        )

    except json.JSONDecodeError:

        print(
            "\nRecipe constraint extraction failed."
        )

        print(
            f"Raw response: {raw}"
        )

        return {
            "cuisine": None,
            "category": None,
            "required_ingredients": [],
        }

    cuisine = data.get(
        "cuisine"
    )

    category = data.get(
        "category"
    )

    required_ingredients = data.get(
        "required_ingredients",
        [],
    )

    if cuisine not in ALLOWED_CUISINES:
        cuisine = None

    if category not in ALLOWED_CATEGORIES:
        category = None

    if not isinstance(
        required_ingredients,
        list,
    ):
        required_ingredients = []

    cleaned_ingredients = []

    for ingredient in required_ingredients:

        if not isinstance(
            ingredient,
            str,
        ):
            continue

        ingredient = (
            ingredient
            .strip()
            .lower()
        )

        if not ingredient:
            continue

        if ingredient not in cleaned_ingredients:

            cleaned_ingredients.append(
                ingredient
            )

    constraints = {
        "cuisine":
            cuisine,

        "category":
            category,

        "required_ingredients":
            cleaned_ingredients,
    }

    print(
        "\nRecipe search constraints:"
    )

    print(
        f"  Cuisine: "
        f"{constraints['cuisine']}"
    )

    print(
        f"  Category: "
        f"{constraints['category']}"
    )

    print(
        f"  Required ingredients: "
        f"{constraints['required_ingredients']}"
    )

    return constraints