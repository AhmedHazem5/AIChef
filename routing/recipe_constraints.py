import json
import re
import time

import ollama

MODEL_NAME = "qwen3:4b-instruct"


ALLOWED_CUISINES = {
    "American",
    "Argentine",
    "Asian",
    "Australian",
    "Austrian",
    "Belgian",
    "Brazilian",
    "British",
    "Cajun",
    "Canadian",
    "Caribbean",
    "Chinese",
    "Colombian",
    "Costa Rican",
    "Creole",
    "Danish",
    "Egyptian",
    "Filipino",
    "French",
    "German",
    "Greek",
    "Guatemalan",
    "Hawaiian",
    "Honduran",
    "Hungarian",
    "Indian",
    "Indonesian",
    "Iranian",
    "Irish",
    "Italian",
    "Jamaican",
    "Japanese",
    "Korean",
    "Latin American",
    "Mediterranean",
    "Mexican",
    "Moroccan",
    "Native American",
    "New Zealand",
    "Pakistani",
    "Polish",
    "Portuguese",
    "Puerto Rican",
    "Russian",
    "South African",
    "Spanish",
    "Swedish",
    "Swiss",
    "Thai",
    "Tunisian",
    "Turkish",
    "Ukrainian",
    "Venezuelan",
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


ALLOWED_NUTRITION_PREFERENCES = {
    "high_protein",
    "low_calorie",
    "low_fat",
    "low_carb",
}


def extract_recipe_constraints(
    user_message: str,
) -> dict:


    allowed_cuisines_text = "\n".join(
        sorted(ALLOWED_CUISINES)
    )   
    prompt = f"""
You extract explicit recipe-search constraints for ChefAI.

User request:

"{user_message}"

Return ONLY valid JSON with exactly these keys:

{{
    "cuisine": null,
    "category": null,
    "required_ingredients": [],
    "max_calories": null,
    "min_calories": null,
    "min_protein_g": null,
    "max_protein_g": null,
    "max_carbohydrates_g": null,
    "max_fat_g": null,
    "nutrition_preference": null
}}

Allowed cuisine values:
{allowed_cuisines_text}

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

8. Extract numeric nutrition constraints only when the user
   explicitly gives a number.

9. Examples of numeric nutrition constraints:

   "under 1000 calories"
   -> max_calories = 1000

   "at least 80 grams of protein"
   -> min_protein_g = 80

   "less than 30 grams of fat"
   -> max_fat_g = 30

   "under 100 grams of carbs"
   -> max_carbohydrates_g = 100

10. Do not invent numeric limits.

11. nutrition_preference is only for relative requests.

Allowed nutrition_preference values:

high_protein
low_calorie
low_fat
low_carb

Examples:

"I want something high in protein."
-> nutrition_preference = "high_protein"

"I want something low calorie."
-> nutrition_preference = "low_calorie"

"I want something low fat."
-> nutrition_preference = "low_fat"

"I want something low carb."
-> nutrition_preference = "low_carb"

12. If there is no nutrition request:
    nutrition_preference = null

13. Cuisine words must always be extracted when explicitly
    stated.

Examples:

"Egyptian recipe"
-> cuisine = "Egyptian"

"Brazilian food"
-> cuisine = "Brazilian"

"Give me a Moroccan chicken recipe"
-> cuisine = "Moroccan"

"Japanese food"
-> cuisine = "Japanese"

"Give me a Tunisian recipe under 800 calories"
-> cuisine = "Tunisian"
-> max_calories = 800

"Chinese recipe"
-> cuisine = "Chinese"

"Japanese food"
-> cuisine = "Japanese"

"Chinese recipe with at least 80 grams of protein"
-> cuisine = "Chinese"
-> min_protein_g = 80

14. Do NOT infer a category merely because an ingredient
    happens to share a category name.

Example:

"I want chicken and garlic."
-> category = null
-> required_ingredients = ["chicken", "garlic"]

But:

"I want a chicken recipe."
-> category = "Chicken"

15. A numeric nutrition constraint does NOT automatically
    imply nutrition_preference.

Example:

"under 1000 calories"
-> max_calories = 1000
-> nutrition_preference = null

"low calorie"
-> max_calories = null
-> nutrition_preference = "low_calorie"

"low calorie and under 1000 calories"
-> max_calories = 1000
-> nutrition_preference = "low_calorie"


============================================================
EXAMPLES
============================================================

"Give me a Chinese noodle recipe."

{{
    "cuisine": "Chinese",
    "category": "Noodles",
    "required_ingredients": [],
    "max_calories": null,
    "min_calories": null,
    "min_protein_g": null,
    "max_protein_g": null,
    "max_carbohydrates_g": null,
    "max_fat_g": null,
    "nutrition_preference": null
}}

"I want something with garlic and chicken."

{{
    "cuisine": null,
    "category": null,
    "required_ingredients": [
        "garlic",
        "chicken"
    ],
    "max_calories": null,
    "min_calories": null,
    "min_protein_g": null,
    "max_protein_g": null,
    "max_carbohydrates_g": null,
    "max_fat_g": null,
    "nutrition_preference": null
}}

"Give me a Chinese recipe with shrimp."

{{
    "cuisine": "Chinese",
    "category": null,
    "required_ingredients": [
        "shrimp"
    ],
    "max_calories": null,
    "min_calories": null,
    "min_protein_g": null,
    "max_protein_g": null,
    "max_carbohydrates_g": null,
    "max_fat_g": null,
    "nutrition_preference": null
}}

"I want chicken and rice."

{{
    "cuisine": null,
    "category": null,
    "required_ingredients": [
        "chicken",
        "rice"
    ],
    "max_calories": null,
    "min_calories": null,
    "min_protein_g": null,
    "max_protein_g": null,
    "max_carbohydrates_g": null,
    "max_fat_g": null,
    "nutrition_preference": null
}}

"I want a soup with mushrooms."

{{
    "cuisine": null,
    "category": "Soup",
    "required_ingredients": [
        "mushrooms"
    ],
    "max_calories": null,
    "min_calories": null,
    "min_protein_g": null,
    "max_protein_g": null,
    "max_carbohydrates_g": null,
    "max_fat_g": null,
    "nutrition_preference": null
}}

"What can I eat today?"

{{
    "cuisine": null,
    "category": null,
    "required_ingredients": [],
    "max_calories": null,
    "min_calories": null,
    "min_protein_g": null,
    "max_protein_g": null,
    "max_carbohydrates_g": null,
    "max_fat_g": null,
    "nutrition_preference": null
}}

"I want Sweet and Sour Chicken."

This is a named recipe request.
Do not infer ingredient constraints from the title.

{{
    "cuisine": null,
    "category": null,
    "required_ingredients": [],
    "max_calories": null,
    "min_calories": null,
    "min_protein_g": null,
    "max_protein_g": null,
    "max_carbohydrates_g": null,
    "max_fat_g": null,
    "nutrition_preference": null
}}

"Give me a recipe under 1000 calories."

{{
    "cuisine": null,
    "category": null,
    "required_ingredients": [],
    "max_calories": 1000,
    "min_calories": null,
    "min_protein_g": null,
    "max_protein_g": null,
    "max_carbohydrates_g": null,
    "max_fat_g": null,
    "nutrition_preference": null
}}

"I want chicken and garlic under 1500 calories."

{{
    "cuisine": null,
    "category": null,
    "required_ingredients": [
        "chicken",
        "garlic"
    ],
    "max_calories": 1500,
    "min_calories": null,
    "min_protein_g": null,
    "max_protein_g": null,
    "max_carbohydrates_g": null,
    "max_fat_g": null,
    "nutrition_preference": null
}}

"Give me a Chinese recipe with at least 80 grams of protein."

{{
    "cuisine": "Chinese",
    "category": null,
    "required_ingredients": [],
    "max_calories": null,
    "min_calories": null,
    "min_protein_g": 80,
    "max_protein_g": null,
    "max_carbohydrates_g": null,
    "max_fat_g": null,
    "nutrition_preference": null
}}

"I want something high in protein."

{{
    "cuisine": null,
    "category": null,
    "required_ingredients": [],
    "max_calories": null,
    "min_calories": null,
    "min_protein_g": null,
    "max_protein_g": null,
    "max_carbohydrates_g": null,
    "max_fat_g": null,
    "nutrition_preference": "high_protein"
}}

"I want something low fat."

{{
    "cuisine": null,
    "category": null,
    "required_ingredients": [],
    "max_calories": null,
    "min_calories": null,
    "min_protein_g": null,
    "max_protein_g": null,
    "max_carbohydrates_g": null,
    "max_fat_g": null,
    "nutrition_preference": "low_fat"
}}

Return ONLY the JSON.
Do not explain.
"""
    start = time.perf_counter()
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
            "num_ctx": 4096,
            "num_predict": 256,
        },
        think=False,
        keep_alive="30m",
        format="json",
    )

    elapsed = (
        time.perf_counter()
        - start
    )

    print(
        f"[TIMING] recipe constraints: "
        f"{elapsed:.2f} seconds"
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
            "max_calories": None,
            "min_calories": None,
            "min_protein_g": None,
            "max_protein_g": None,
            "max_carbohydrates_g": None,
            "max_fat_g": None,
            "nutrition_preference": None,
        }

    cuisine = data.get(
        "cuisine"
    )

    category = data.get(
        "category"
    )

    # ========================================================
    # Deterministic explicit cuisine detection
    #
    # Do not rely only on the LLM for obvious cuisine words.
    #
    # Example:
    # "Give me a Chinese recipe with at least 80g protein"
    # -> Chinese
    # ========================================================

    for allowed_cuisine in ALLOWED_CUISINES:

        if re.search(
            rf"\b{re.escape(allowed_cuisine)}\b",
            user_message,
            flags=re.IGNORECASE,
        ):

            cuisine = allowed_cuisine
            break

    required_ingredients = data.get(
        "required_ingredients",
        [],
    )

    max_calories = data.get(
        "max_calories"
    )

    min_calories = data.get(
        "min_calories"
    )

    min_protein_g = data.get(
        "min_protein_g"
    )

    max_protein_g = data.get(
        "max_protein_g"
    )

    max_carbohydrates_g = data.get(
        "max_carbohydrates_g"
    )

    max_fat_g = data.get(
        "max_fat_g"
    )

    nutrition_preference = data.get(
        "nutrition_preference"
    )
    # ========================================================
    # Deterministic nutrition preference detection
    #
    # Do not rely only on the LLM for obvious phrases.
    # ========================================================

    message_lower = user_message.lower()

    if (
        "high protein" in message_lower
        or "high in protein" in message_lower
    ):
        nutrition_preference = "high_protein"

    elif (
        "low calorie" in message_lower
        or "low calories" in message_lower
        or "low-calorie" in message_lower
    ):
        nutrition_preference = "low_calorie"

    elif (
        "low fat" in message_lower
        or "low-fat" in message_lower
    ):
        nutrition_preference = "low_fat"

    elif (
        "low carb" in message_lower
        or "low carbs" in message_lower
        or "low carbohydrate" in message_lower
        or "low carbohydrates" in message_lower
    ):
        nutrition_preference = "low_carb"
    # ========================================================
    # Validate cuisine/category
    # ========================================================

    if cuisine not in ALLOWED_CUISINES:
        cuisine = None

    if category not in ALLOWED_CATEGORIES:
        category = None

    # ========================================================
    # Validate ingredients
    # ========================================================

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

    # ========================================================
    # Validate numeric nutrition constraints
    # ========================================================

    numeric_constraints = {
        "max_calories":
            max_calories,

        "min_calories":
            min_calories,

        "min_protein_g":
            min_protein_g,

        "max_protein_g":
            max_protein_g,

        "max_carbohydrates_g":
            max_carbohydrates_g,

        "max_fat_g":
            max_fat_g,
    }

    for key, value in (
        numeric_constraints.items()
    ):

        if not isinstance(
            value,
            (int, float),
        ):

            numeric_constraints[
                key
            ] = None

        elif value < 0:

            numeric_constraints[
                key
            ] = None

    # ========================================================
    # Validate relative nutrition preference
    # ========================================================

    if (
        nutrition_preference
        not in ALLOWED_NUTRITION_PREFERENCES
    ):

        nutrition_preference = None

    # ========================================================
    # Final constraints
    # ========================================================

    constraints = {
        "cuisine":
            cuisine,

        "category":
            category,

        "required_ingredients":
            cleaned_ingredients,

        "max_calories":
            numeric_constraints[
                "max_calories"
            ],

        "min_calories":
            numeric_constraints[
                "min_calories"
            ],

        "min_protein_g":
            numeric_constraints[
                "min_protein_g"
            ],

        "max_protein_g":
            numeric_constraints[
                "max_protein_g"
            ],

        "max_carbohydrates_g":
            numeric_constraints[
                "max_carbohydrates_g"
            ],

        "max_fat_g":
            numeric_constraints[
                "max_fat_g"
            ],

        "nutrition_preference":
            nutrition_preference,
    }

    # ========================================================
    # Debug output
    # ========================================================

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

    print(
        f"  Max calories: "
        f"{constraints['max_calories']}"
    )

    print(
        f"  Min calories: "
        f"{constraints['min_calories']}"
    )

    print(
        f"  Min protein: "
        f"{constraints['min_protein_g']}"
    )

    print(
        f"  Max protein: "
        f"{constraints['max_protein_g']}"
    )

    print(
        f"  Max carbs: "
        f"{constraints['max_carbohydrates_g']}"
    )

    print(
        f"  Max fat: "
        f"{constraints['max_fat_g']}"
    )

    print(
        f"  Nutrition preference: "
        f"{constraints['nutrition_preference']}"
    )

    return constraints


# ============================================================
# Tests
# ============================================================

if __name__ == "__main__":

    tests = [
        "I want something low calorie",
        "I want something low fat",
        "I want something low carb",
        "I want something high in protein",
    ]

    for test in tests:

        print(
            "\n=============================="
        )

        print(
            f"TEST: {test}"
        )

        extract_recipe_constraints(
            test
        )