import json
from pathlib import Path
import re

from nutrition.calculate_nutrition import (
    calculate_recipe_nutrition,
)


# ============================================================
# Paths
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

STRUCTURED_RECIPE_DIR = (
    PROJECT_ROOT
    / "data"
    / "structured_recipes"
)


# ============================================================
# Nutrition helpers
# ============================================================

REQUIRED_NUTRITION_FIELDS = (
    "calories",
    "protein_g",
    "carbohydrates_g",
    "fat_g",
)

# ============================================================
# Nutrition estimate acceptance
# ============================================================

MIN_ACCEPTABLE_COVERAGE = 0.75


# ============================================================
# Ingredients that are important enough that we should NOT
# save a recipe estimate if they fail to resolve.
#
# These are foods that can materially change calories/macros.
# ============================================================

IMPORTANT_FOOD_TERMS = {
    # Meat / poultry
    "chicken",
    "beef",
    "pork",
    "lamb",
    "turkey",

    # Seafood
    "shrimp",
    "fish",
    "salmon",
    "tuna",
    "crab",

    # Main carbohydrates
    "rice",
    "noodle",
    "noodles",
    "pasta",
    "vermicelli",

    # Protein sources
    "egg",
    "eggs",
    "tofu",

    # Dairy
    "milk",
    "cream",
    "cheese",
    "butter",

    # Calorie-dense ingredients
    "oil",
    "peanut",
    "peanuts",
    "peanut butter",
    "cashew",
    "cashews",
    "almond",
    "almonds",

    # Baking / starches
    "flour",
    "sugar",
}

IMPORTANT_FOOD_TERMS.update({
    "snapper",
    "trout",
    "cod",
    "haddock",
    "halibut",
    "carp",
    "salmon",
    "tuna",
    "swordfish",
    "pork",
    "spareribs",
    "sirloin",
    "tofu",
    "bean curd",
    "peanuts",
    "walnuts",
    "tortilla",
    "tortillas",
    "flour",
    "breadcrumbs",
    "ramen",
    "potatoes",
})

# ============================================================
# Ingredients we are comfortable skipping when no reliable
# amount/nutrition match exists.
# ============================================================

MINOR_FOOD_TERMS = {
    "rice wine",
    "dry sherry",
    "sherry",
    "chili bean paste",
    "vinegar",
    "pepper",
    "five-spice",
    "five spice",
    "cilantro",
    "parsley",
    "ginger",
}
NON_FOOD_TERMS = {
    "aluminum foil",
    "foil",
}

def is_minor_unresolved_ingredient(
    ingredient_result: dict,
) -> bool:



    ingredient = (
        ingredient_result.get(
            "ingredient",
            ""
        )
        .lower()
        .strip()
    )

    parsed = ingredient_result.get(
        "parsed",
        {},
    )

    quantity = parsed.get(
        "quantity"
    )

    if any(
        term in ingredient
        for term in NON_FOOD_TERMS
    ):
        return True

    # --------------------------------------------------------
    # Explicit known-small ingredients
    # --------------------------------------------------------

    if any(
        term in ingredient
        for term in MINOR_FOOD_TERMS
    ):

        return True

    # --------------------------------------------------------
    # Unquantified garnish / frying ingredients.
    #
    # We cannot estimate these reliably, but we also should
    # not reject the whole recipe because of them.
    # --------------------------------------------------------

    if quantity is None:

        ignorable_phrases = (
            "for frying",
            "salad greens",
            "for garnish",
            "garnish",
            "optional",
        )

        if any(
            phrase in ingredient
            for phrase in ignorable_phrases
        ):

            return True

    return False


def is_important_unresolved_ingredient(
    ingredient_result: dict,
) -> bool:

    if is_minor_unresolved_ingredient(
        ingredient_result
    ):

        return False

    ingredient = (
        ingredient_result.get(
            "ingredient",
            ""
        )
        .lower()
        .strip()
    )

    parsed = ingredient_result.get(
        "parsed",
        {},
    )

    quantity = parsed.get(
        "quantity"
    )

    unit = parsed.get(
        "unit"
    )

    # --------------------------------------------------------
    # No amount at all.
    #
    # If it wasn't specifically classified as minor above,
    # don't automatically reject the recipe just because the
    # cookbook omitted a quantity.
    # --------------------------------------------------------

    if quantity is None:

        return False

    # --------------------------------------------------------
    # Tiny teaspoon amounts generally have little effect on
    # total recipe calories.
    #
    # Example:
    # 1 tsp cornstarch
    # 1 tsp oil
    #
    # We allow these to be skipped.
    # --------------------------------------------------------

    if (
        unit == "tsp"
        and quantity <= 2
    ):

        return False

    # --------------------------------------------------------
    # Major food groups
    # --------------------------------------------------------

    return any(
        re.search(
            rf"\b{re.escape(term)}\b",
            ingredient,
        )
        is not None
        for term in IMPORTANT_FOOD_TERMS
    )


def has_complete_existing_nutrition(
    recipe: dict,
) -> bool:

    nutrition = recipe.get(
        "nutrition",
        {},
    )

    if not isinstance(
        nutrition,
        dict,
    ):
        return False

    return all(
        nutrition.get(field)
        is not None
        for field in REQUIRED_NUTRITION_FIELDS
    )


def recipe_needs_nutrition(
    recipe: dict,
) -> bool:

    return not (
        has_complete_existing_nutrition(
            recipe
        )
    )


# ============================================================
# Build nutrition object
# ============================================================

def build_nutrition_result(
    calculation: dict,
) -> dict:

    totals = calculation.get(
        "totals",
        {},
    )

    return {
        "calories":
            totals.get(
                "calories"
            ),

        "protein_g":
            totals.get(
                "protein_g"
            ),

        "carbohydrates_g":
            totals.get(
                "carbohydrates_g"
            ),

        "fat_g":
            totals.get(
                "fat_g"
            ),
    }


# ============================================================
# Enrich one recipe
# ============================================================

def enrich_recipe(
    recipe: dict,
) -> tuple[dict, dict]:

    title = recipe.get(
        "title",
        "Unknown recipe",
    )

    cuisine = recipe.get(
        "cuisine",
        "Unknown",
    )

    ingredients = recipe.get(
        "ingredients",
        [],
    )

    # --------------------------------------------------------
    # Preserve source-book nutrition
    # --------------------------------------------------------

    if not recipe_needs_nutrition(
        recipe
    ):

        existing_source = (
            recipe.get(
                "nutrition_source"
            )
        )

        if not existing_source:

            recipe[
                "nutrition_source"
            ] = "source_book"

        return recipe, {
            "status":
                "skipped_existing",

            "title":
                title,

            "cuisine":
                cuisine,

            "coverage":
                1.0,
        }

    # --------------------------------------------------------
    # Cannot calculate without ingredients
    # --------------------------------------------------------

    if not ingredients:

        return recipe, {
            "status":
                "failed",

            "title":
                title,

            "cuisine":
                cuisine,

            "reason":
                "recipe has no ingredients",

            "coverage":
                0.0,
        }

    # --------------------------------------------------------
    # Calculate nutrition from ingredients
    # --------------------------------------------------------

    calculation = (
        calculate_recipe_nutrition(
            ingredients=ingredients,
            steps=recipe.get(
                "steps",
                [],
            ),
        )
    )

    coverage = calculation.get(
        "coverage",
        0.0,
    )

    resolved = calculation.get(
        "resolved_ingredients",
        0,
    )

    total = calculation.get(
        "total_ingredients",
        len(ingredients),
    )

    ingredient_results = calculation.get(
        "ingredient_results",
        [],
    )


    # ============================================================
    # Find unresolved ingredients that are important enough to
    # invalidate the nutrition estimate.
    # ============================================================

    important_unresolved = []

    minor_unresolved = []

    for ingredient_result in ingredient_results:

        if (
            ingredient_result.get(
                "status"
            )
            == "resolved"
        ):
            continue

        if is_important_unresolved_ingredient(
            ingredient_result
        ):

            important_unresolved.append(
                ingredient_result
            )

        else:

            minor_unresolved.append(
                ingredient_result
            )

    nutrition = (
        build_nutrition_result(
            calculation
        )
    )

    # --------------------------------------------------------
    # Check whether all four macros were actually calculated
    # --------------------------------------------------------

    complete_macros = all(
        nutrition.get(field)
        is not None
        for field in REQUIRED_NUTRITION_FIELDS
    )

    # --------------------------------------------------------
    # Do not save low-quality estimates as final nutrition.
    #
    # For now we require:
    #
    # 100% ingredient weight coverage
    # AND
    # all four nutrition fields
    #
    # We can loosen this later if needed.
    # --------------------------------------------------------

    if (
        not complete_macros
        or important_unresolved
    ):

        return recipe, {
            "status":
                "incomplete",

            "title":
                title,

            "cuisine":
                cuisine,

            "coverage":
                coverage,

            "resolved":
                resolved,

            "total":
                total,

            "nutrition":
                nutrition,

            "ingredient_results":
                calculation.get(
                    "ingredient_results",
                    [],
                ),
            "important_unresolved":
                important_unresolved,

            "minor_unresolved":
                minor_unresolved,
        }

    # --------------------------------------------------------
    # Save estimated nutrition
    # --------------------------------------------------------

    recipe[
        "nutrition"
    ] = nutrition

    recipe[
        "nutrition_source"
    ] = (
        "estimated_from_ingredients"
    )

    recipe[
        "nutrition_coverage"
    ] = coverage

    recipe[
        "nutrition_unresolved_minor"
    ] = [
        item.get(
            "ingredient"
        )
        for item in minor_unresolved
    ]

    return recipe, {
        "status":
            "enriched",

        "title":
            title,

        "cuisine":
            cuisine,

        "coverage":
            coverage,

        "resolved":
            resolved,

        "total":
            total,

        "nutrition":
            nutrition,
    }


# ============================================================
# Enrich one JSON file
# ============================================================

def enrich_file(
    input_file: Path,
):

    print(
        "\n================================"
    )

    print(
        f"Processing: "
        f"{input_file.name}"
    )

    print(
        "================================"
    )

    with open(
        input_file,
        "r",
        encoding="utf-8",
    ) as file:

        recipes = json.load(
            file
        )

    enriched_recipes = []

    report = []

    # for index, recipe in enumerate(
    #     recipes,
    #     start=1,
    # ):
    TEST_LIMIT = None

    for index, recipe in enumerate(
        recipes[:TEST_LIMIT],
        start=1,
    ):

        title = recipe.get(
            "title",
            "Unknown recipe",
        )

        print(
            f"\n[{index}/{len(recipes)}] "
            f"{title}"
        )

        enriched_recipe, result = (
            enrich_recipe(
                recipe
            )
        )

        enriched_recipes.append(
            enriched_recipe
        )

        report.append(
            result
        )

        status = result.get(
            "status"
        )

        if status == "skipped_existing":

            print(
                "  SKIPPED: "
                "existing nutrition preserved."
            )

        elif status == "enriched":

            nutrition = result[
                "nutrition"
            ]

            print(
                "  ENRICHED"
            )

            print(
                f"  Coverage: "
                f"{result['coverage'] * 100:.1f}%"
            )

            print(
                f"  Calories: "
                f"{nutrition['calories']}"
            )

            print(
                f"  Protein: "
                f"{nutrition['protein_g']} g"
            )

            print(
                f"  Carbs: "
                f"{nutrition['carbohydrates_g']} g"
            )

            print(
                f"  Fat: "
                f"{nutrition['fat_g']} g"
            )

        elif status == "incomplete":

            print(
                "  INCOMPLETE"
            )

            print(
                "  Important unresolved:"
            )

            important_unresolved = result.get(
                "important_unresolved",
                [],
            )

            if important_unresolved:

                for item in important_unresolved:

                    print(
                        "    - "
                        f"{item.get('ingredient')}"
                    )

            else:

                print(
                    "    None"
                )

            print(
                f"  Coverage: "
                f"{result['coverage'] * 100:.1f}%"
            )

            print(
                f"  Resolved: "
                f"{result['resolved']}"
                f"/"
                f"{result['total']}"
            )

            print(
                "  Unresolved ingredients:"
            )

            for ingredient_result in result.get(
                "ingredient_results",
                [],
            ):

                if (
                    ingredient_result.get(
                        "status"
                    )
                    == "resolved"
                ):
                    continue

                parsed = ingredient_result.get(
                    "parsed",
                    {},
                )

                print(
                    "    - "
                    f"{ingredient_result.get('ingredient')}"
                )

                print(
                    "      Parsed food: "
                    f"{parsed.get('food')}"
                )

                print(
                    "      Quantity: "
                    f"{parsed.get('quantity')}"
                )

                print(
                    "      Unit: "
                    f"{parsed.get('unit')}"
                )

                print(
                    "      Reason: "
                    f"{ingredient_result.get('reason')}"
                )

        else:

            print(
                "  FAILED"
            )

            print(
                f"  Reason: "
                f"{result.get('reason')}"
            )

    # ========================================================
    # Write separate enriched file
    # ========================================================

    output_file = (
        input_file.parent
        / (
            input_file.stem
            + "_enriched.json"
        )
    )

    with open(
        output_file,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            enriched_recipes,
            file,
            indent=2,
            ensure_ascii=False,
        )

    # ========================================================
    # Write detailed report
    # ========================================================

    report_file = (
        input_file.parent
        / (
            input_file.stem
            + "_nutrition_report.json"
        )
    )

    with open(
        report_file,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            report,
            file,
            indent=2,
            ensure_ascii=False,
        )

    # ========================================================
    # Summary
    # ========================================================

    enriched_count = sum(
        1
        for item in report
        if item.get(
            "status"
        )
        == "enriched"
    )

    skipped_count = sum(
        1
        for item in report
        if item.get(
            "status"
        )
        == "skipped_existing"
    )

    incomplete_count = sum(
        1
        for item in report
        if item.get(
            "status"
        )
        == "incomplete"
    )

    failed_count = sum(
        1
        for item in report
        if item.get(
            "status"
        )
        == "failed"
    )

    print(
        "\n--------------------------------"
    )

    print(
        f"File summary: "
        f"{input_file.name}"
    )

    print(
        "--------------------------------"
    )

    print(
        f"Recipes: "
        f"{len(recipes)}"
    )

    print(
        f"Enriched: "
        f"{enriched_count}"
    )

    print(
        f"Existing nutrition preserved: "
        f"{skipped_count}"
    )

    print(
        f"Incomplete: "
        f"{incomplete_count}"
    )

    print(
        f"Failed: "
        f"{failed_count}"
    )

    print(
        "\nSaved enriched file:"
    )

    print(
        output_file
    )

    print(
        "\nSaved nutrition report:"
    )

    print(
        report_file
    )

    return {
        "input_file":
            str(input_file),

        "output_file":
            str(output_file),

        "report_file":
            str(report_file),

        "recipes":
            len(recipes),

        "enriched":
            enriched_count,

        "skipped_existing":
            skipped_count,

        "incomplete":
            incomplete_count,

        "failed":
            failed_count,
    }


# ============================================================
# Find structured recipe files
# ============================================================

def get_recipe_files():

    files = sorted(
        STRUCTURED_RECIPE_DIR.glob(
            "*_recipes.json"
        )
    )

    # --------------------------------------------------------
    # Do not accidentally enrich output files from a
    # previous run.
    # --------------------------------------------------------

    files = [
        file
        for file in files
        if not file.name.endswith(
            "_enriched.json"
        )
    ]

    return files


# ============================================================
# Main
# ============================================================

def main():

    recipe_files = (
        get_recipe_files()
    )

    if not recipe_files:

        raise FileNotFoundError(
            "No structured recipe files "
            f"found in:\n"
            f"{STRUCTURED_RECIPE_DIR}"
        )

    print(
        "Nutrition enrichment starting..."
    )

    print(
        f"Structured recipe files found: "
        f"{len(recipe_files)}"
    )

    summaries = []

    for recipe_file in recipe_files:

        summary = enrich_file(
            recipe_file
        )

        summaries.append(
            summary
        )

    print(
        "\n================================"
    )

    print(
        "OVERALL NUTRITION ENRICHMENT"
    )

    print(
        "================================"
    )

    total_recipes = sum(
        item[
            "recipes"
        ]
        for item in summaries
    )

    total_enriched = sum(
        item[
            "enriched"
        ]
        for item in summaries
    )

    total_skipped = sum(
        item[
            "skipped_existing"
        ]
        for item in summaries
    )

    total_incomplete = sum(
        item[
            "incomplete"
        ]
        for item in summaries
    )

    total_failed = sum(
        item[
            "failed"
        ]
        for item in summaries
    )

    print(
        f"Total recipes: "
        f"{total_recipes}"
    )

    print(
        f"Enriched: "
        f"{total_enriched}"
    )

    print(
        f"Existing nutrition preserved: "
        f"{total_skipped}"
    )

    print(
        f"Incomplete: "
        f"{total_incomplete}"
    )

    print(
        f"Failed: "
        f"{total_failed}"
    )

    print(
        "\nIMPORTANT:"
    )

    print(
        "Original structured recipe files "
        "were NOT overwritten."
    )

    print(
        "Review the *_enriched.json files "
        "and nutrition reports first."
    )


if __name__ == "__main__":

    main()