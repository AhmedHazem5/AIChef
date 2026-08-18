from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

RECIPES_DIR = (
    PROJECT_ROOT
    / "data"
    / "recipes"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "data"
    / "structured_recipes"
)


BOOKS = [
    {
        "pdf_path":
            RECIPES_DIR / "Italian2.pdf",

        "book_id":
            "italian2",

        "collection":
            "Italian 2",

        "default_cuisine":
            "Italian",

        "default_country":
            "Italy",

        "mixed_cuisines":
            False,
    },

    {
        "pdf_path":
            RECIPES_DIR / "healthy_foods.pdf",

        "book_id":
            "healthy_foods",

        "collection":
            "Healthy Foods",

        # Healthy is NOT a cuisine.
        "default_cuisine":
            "",

        "default_country":
            "",

        "mixed_cuisines":
            True,
    },

    {
        "pdf_path":
            RECIPES_DIR / "world_cuisines.pdf",

        "book_id":
            "world_cuisines",

        "collection":
            "World Cuisines",

        "default_cuisine":
            "",

        "default_country":
            "",

        "mixed_cuisines":
            True,
    },
]