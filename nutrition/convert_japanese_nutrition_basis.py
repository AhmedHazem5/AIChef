import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent

JAPANESE_FILE = (
    PROJECT_ROOT
    / "data"
    / "structured_recipes"
    / "japanese_recipes_enriched.json"
)


def main():

    with open(
        JAPANESE_FILE,
        "r",
        encoding="utf-8",
    ) as file:

        recipes = json.load(file)

    converted = 0
    skipped = 0

    for recipe in recipes:

        nutrition = recipe.get(
            "nutrition",
            {}
        )

        nutrition_source = recipe.get(
            "nutrition_source",
            ""
        )

        servings_raw = recipe.get(
            "servings"
        )

        # ----------------------------------------------------
        # Only convert source-book nutrition.
        #
        # Ingredient-calculated recipes are already whole
        # recipe totals and must NOT be multiplied again.
        # ----------------------------------------------------

        if nutrition_source != "source_book":

            skipped += 1
            continue

        # Already converted before
        if (
            nutrition.get("basis")
            == "whole_recipe"
        ):

            skipped += 1
            continue

        try:

            servings = float(
                servings_raw
            )

        except (
            TypeError,
            ValueError,
        ):

            skipped += 1
            continue

        if servings <= 0:

            skipped += 1
            continue

        per_serving = {
            "calories":
                nutrition.get(
                    "calories"
                ),

            "protein_g":
                nutrition.get(
                    "protein_g"
                ),

            "carbohydrates_g":
                nutrition.get(
                    "carbohydrates_g"
                ),

            "fat_g":
                nutrition.get(
                    "fat_g"
                ),
        }

        for field in (
            "calories",
            "protein_g",
            "carbohydrates_g",
            "fat_g",
        ):

            value = nutrition.get(
                field
            )

            if value is not None:

                nutrition[
                    field
                ] = round(
                    float(value)
                    * servings,
                    1,
                )

        nutrition[
            "basis"
        ] = "whole_recipe"

        nutrition[
            "servings"
        ] = servings

        nutrition[
            "per_serving"
        ] = per_serving

        recipe[
            "nutrition"
        ] = nutrition

        converted += 1

    with open(
        JAPANESE_FILE,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            recipes,
            file,
            indent=2,
            ensure_ascii=False,
        )

    print(
        f"Converted: {converted}"
    )

    print(
        f"Skipped: {skipped}"
    )

    print(
        f"Saved: {JAPANESE_FILE}"
    )


if __name__ == "__main__":

    main()