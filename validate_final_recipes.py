import json
import math
from pathlib import Path
from collections import Counter


# ============================================================
# Paths
# ============================================================

PROJECT_ROOT = (
    Path(__file__).resolve().parent
)

DATA_DIR = (
    PROJECT_ROOT
    / "data"
    / "structured_recipes"
)


FILES = [

    DATA_DIR
    / "chinese_recipes_enriched.json",

    DATA_DIR
    / "japanese_recipes_enriched.json",
    
    DATA_DIR
    / "italian_recipes_gemini_nutrition_final.json",

    DATA_DIR
    / "italian2_recipes_gemini_nutrition_enriched.json",

    DATA_DIR
    / "healthy_foods_recipes_gemini_nutrition_enriched.json",

    DATA_DIR
    / "world_cuisines_recipes_gemini_nutrition_enriched.json",
]


REQUIRED_NUTRITION_FIELDS = (
    "calories",
    "protein_g",
    "carbohydrates_g",
    "fat_g",
)


# ============================================================
# Helpers
# ============================================================

def load_json(
    path: Path,
):

    with path.open(
        "r",
        encoding="utf-8",
    ) as file:

        return json.load(
            file
        )


def is_valid_number(
    value,
):

    if isinstance(
        value,
        bool,
    ):
        return False

    if not isinstance(
        value,
        (int, float),
    ):
        return False

    if not math.isfinite(
        float(value)
    ):
        return False

    return True


# ============================================================
# Validation
# ============================================================

def validate_recipe(
    recipe,
    filename,
    index,
):

    errors = []
    warnings = []

    recipe_id = str(
        recipe.get(
            "id",
            "",
        )
    ).strip()

    title = str(
        recipe.get(
            "title",
            "",
        )
    ).strip()

    # --------------------------------------------------------
    # Required basic data
    # --------------------------------------------------------

    if not recipe_id:

        errors.append(
            "Missing recipe id"
        )

    if not title:

        errors.append(
            "Missing title"
        )

    ingredients = recipe.get(
        "ingredients"
    )

    if not isinstance(
        ingredients,
        list,
    ):

        errors.append(
            "ingredients is not a list"
        )

    elif not ingredients:

        errors.append(
            "ingredients list is empty"
        )

    else:

        empty_ingredients = [
            ingredient
            for ingredient in ingredients
            if not str(
                ingredient
            ).strip()
        ]

        if empty_ingredients:

            errors.append(
                "Contains empty ingredient entries"
            )

    steps = recipe.get(
        "steps"
    )

    if not isinstance(
        steps,
        list,
    ):

        errors.append(
            "steps is not a list"
        )

    elif not steps:

        errors.append(
            "steps list is empty"
        )

    else:

        empty_steps = [
            step
            for step in steps
            if not str(
                step
            ).strip()
        ]

        if empty_steps:

            errors.append(
                "Contains empty cooking steps"
            )

    # --------------------------------------------------------
    # Nutrition
    # --------------------------------------------------------

    nutrition = recipe.get(
        "nutrition"
    )

    if not isinstance(
        nutrition,
        dict,
    ):

        errors.append(
            "Missing nutrition object"
        )

    else:

        for field in (
            REQUIRED_NUTRITION_FIELDS
        ):

            value = nutrition.get(
                field
            )

            if value is None:

                errors.append(
                    f"Nutrition {field} is null"
                )

                continue

            if not is_valid_number(
                value
            ):

                errors.append(
                    f"Nutrition {field} "
                    f"is not numeric: {value!r}"
                )

                continue

            if float(
                value
            ) < 0:

                errors.append(
                    f"Nutrition {field} "
                    f"is negative: {value}"
                )

        basis = nutrition.get(
            "basis"
        )

        if basis != "whole_recipe":

            warnings.append(
                f"Nutrition basis is "
                f"{basis!r}, not "
                f"'whole_recipe'"
            )

    # --------------------------------------------------------
    # Metadata / unresolved ingredients
    # --------------------------------------------------------

    metadata = recipe.get(
        "nutrition_metadata"
    )

    if isinstance(
        metadata,
        dict,
    ):

        unresolved = metadata.get(
            "still_unresolved",
            []
        )

        if unresolved:

            errors.append(
                "Still unresolved ingredients: "
                + ", ".join(
                    str(item)
                    for item in unresolved
                )
            )

    # --------------------------------------------------------
    # Source
    # --------------------------------------------------------

    source_file = str(
        recipe.get(
            "source_file",
            "",
        )
    ).strip()

    if not source_file:

        warnings.append(
            "Missing source_file"
        )

    source_pages = recipe.get(
        "source_pages"
    )

    if not isinstance(
        source_pages,
        list,
    ):

        warnings.append(
            "source_pages is not a list"
        )

    elif not source_pages:

        warnings.append(
            "source_pages is empty"
        )

    # --------------------------------------------------------
    # Optional sanity warnings
    #
    # These don't fail validation because old cookbook
    # recipes can legitimately contain very vague amounts.
    # --------------------------------------------------------

    if isinstance(
        nutrition,
        dict,
    ):

        calories = nutrition.get(
            "calories"
        )

        if (
            is_valid_number(
                calories
            )
            and float(
                calories
            ) > 10000
        ):

            warnings.append(
                f"Very high whole-recipe calories: "
                f"{calories}"
            )

        for field in (
            "protein_g",
            "carbohydrates_g",
            "fat_g",
        ):

            value = nutrition.get(
                field
            )

            if (
                is_valid_number(
                    value
                )
                and float(
                    value
                ) > 2000
            ):

                warnings.append(
                    f"Very high {field}: "
                    f"{value}"
                )

    return {
        "file":
            filename,

        "index":
            index,

        "id":
            recipe_id,

        "title":
            title,

        "errors":
            errors,

        "warnings":
            warnings,
    }


# ============================================================
# Main
# ============================================================

def main():

    print(
        "========================================"
    )

    print(
        "CHEFAI FINAL RECIPE VALIDATION"
    )

    print(
        "========================================"
    )

    all_recipes = []

    all_results = []

    missing_files = []

    file_counts = {}

    # ========================================================
    # Load + validate each file
    # ========================================================

    for path in FILES:

        print(
            f"\nChecking: "
            f"{path.name}"
        )

        if not path.exists():

            print(
                "  ERROR: File does not exist."
            )

            missing_files.append(
                path
            )

            continue

        try:

            recipes = load_json(
                path
            )

        except Exception as error:

            print(
                f"  ERROR reading JSON: "
                f"{error}"
            )

            missing_files.append(
                path
            )

            continue

        if not isinstance(
            recipes,
            list,
        ):

            print(
                "  ERROR: Root JSON "
                "is not a list."
            )

            continue

        file_counts[
            path.name
        ] = len(
            recipes
        )

        print(
            f"  Recipes: "
            f"{len(recipes)}"
        )

        for index, recipe in enumerate(
            recipes,
            start=1,
        ):

            if not isinstance(
                recipe,
                dict,
            ):

                all_results.append(
                    {
                        "file":
                            path.name,

                        "index":
                            index,

                        "id":
                            "",

                        "title":
                            "",

                        "errors": [
                            "Recipe is not an object"
                        ],

                        "warnings":
                            [],
                    }
                )

                continue

            result = validate_recipe(
                recipe,
                path.name,
                index,
            )

            all_results.append(
                result
            )

            all_recipes.append(
                recipe
            )

    # ========================================================
    # Duplicate IDs
    # ========================================================

    ids = [
        str(
            recipe.get(
                "id",
                "",
            )
        ).strip()

        for recipe in all_recipes

        if str(
            recipe.get(
                "id",
                "",
            )
        ).strip()
    ]

    id_counts = Counter(
        ids
    )

    duplicate_ids = {
        recipe_id:
            count

        for recipe_id, count
        in id_counts.items()

        if count > 1
    }

    # ========================================================
    # Duplicate exact titles
    #
    # Warning only. Different cookbooks can contain recipes
    # with the same title.
    # ========================================================

    titles = [
        str(
            recipe.get(
                "title",
                "",
            )
        ).strip().lower()

        for recipe in all_recipes

        if str(
            recipe.get(
                "title",
                "",
            )
        ).strip()
    ]

    title_counts = Counter(
        titles
    )

    duplicate_titles = {
        title:
            count

        for title, count
        in title_counts.items()

        if count > 1
    }

    # ========================================================
    # Results
    # ========================================================

    error_results = [
        result
        for result in all_results

        if result[
            "errors"
        ]
    ]

    warning_results = [
        result
        for result in all_results

        if result[
            "warnings"
        ]
    ]

    print(
        "\n========================================"
    )

    print(
        "SUMMARY"
    )

    print(
        "========================================"
    )

    for filename, count in (
        file_counts.items()
    ):

        print(
            f"{filename}: "
            f"{count}"
        )

    print(
        "----------------------------------------"
    )

    print(
        f"Total recipes: "
        f"{len(all_recipes)}"
    )

    print(
        f"Recipes with errors: "
        f"{len(error_results)}"
    )

    print(
        f"Recipes with warnings: "
        f"{len(warning_results)}"
    )

    print(
        f"Duplicate IDs: "
        f"{len(duplicate_ids)}"
    )

    print(
        f"Duplicate titles: "
        f"{len(duplicate_titles)}"
    )

    # ========================================================
    # Print actual errors
    # ========================================================

    if error_results:

        print(
            "\n========================================"
        )

        print(
            "ERRORS"
        )

        print(
            "========================================"
        )

        for result in error_results:

            print(
                f"\n{result['file']}"
            )

            print(
                f"  {result['id']} "
                f"{result['title']}"
            )

            for error in (
                result[
                    "errors"
                ]
            ):

                print(
                    f"    ERROR: "
                    f"{error}"
                )

    # ========================================================
    # Duplicate IDs are real errors
    # ========================================================

    if duplicate_ids:

        print(
            "\n========================================"
        )

        print(
            "DUPLICATE IDS"
        )

        print(
            "========================================"
        )

        for recipe_id, count in (
            duplicate_ids.items()
        ):

            print(
                f"{recipe_id}: "
                f"{count}"
            )

    # ========================================================
    # Warnings
    # ========================================================

    if warning_results:

        print(
            "\n========================================"
        )

        print(
            "WARNINGS"
        )

        print(
            "========================================"
        )

        for result in (
            warning_results
        ):

            print(
                f"\n{result['file']}"
            )

            print(
                f"  {result['id']} "
                f"{result['title']}"
            )

            for warning in (
                result[
                    "warnings"
                ]
            ):

                print(
                    f"    WARNING: "
                    f"{warning}"
                )

    # ========================================================
    # Final verdict
    # ========================================================

    fatal_problem = bool(
        missing_files
        or error_results
        or duplicate_ids
    )

    print(
        "\n========================================"
    )

    if fatal_problem:

        print(
            "VALIDATION FAILED"
        )

        print(
            "Fix the errors above before "
            "building the recipe database."
        )

    else:

        print(
            "VALIDATION PASSED"
        )

        print(
            "The recipe files are ready "
            "for database ingestion."
        )

    print(
        "========================================"
    )


if __name__ == "__main__":
    main()