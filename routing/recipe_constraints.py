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
    "category": null
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


RULES:

1. Only extract constraints that the user clearly requested.

2. Do not guess a cuisine.

3. Do not guess a category if the user did not ask for a
   particular food type.

4. Map natural wording to the closest allowed category.

Examples:

"Give me a Chinese noodle recipe."
- cuisine = Chinese
- category = Noodles

"I want something Japanese."
- cuisine = Japanese
- category = null

"I want a soup."
- cuisine = null
- category = Soup

"Give me Chinese chicken."
- cuisine = Chinese
- category = Chicken

"Find me something with shrimp."
- cuisine = null
- category = Shrimp

"What can I eat today?"
- cuisine = null
- category = null

"Give me something Chinese with rice."
- cuisine = Chinese
- category = Rice

"I want Sweet and Sour Chicken."
This is a named recipe request, not a category request.
- cuisine = null
- category = null

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
        }

    cuisine = data.get(
        "cuisine"
    )

    category = data.get(
        "category"
    )

    if cuisine not in ALLOWED_CUISINES:
        cuisine = None

    if category not in ALLOWED_CATEGORIES:
        category = None

    constraints = {
        "cuisine":
            cuisine,

        "category":
            category,
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

    return constraints