import json
import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai

from ingestion.gemini_recipe_manifest import (
    build_recipe_manifest,
)


load_dotenv()

API_KEY = os.getenv(
    "GEMINI_API_KEY"
)

if not API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY was not found in .env"
    )


MODEL_NAME = "gemini-3.6-flash"


def load_manifest(
    manifest_path: str,
) -> dict:
    path = Path(
        manifest_path
    )

    if not path.exists():
        raise FileNotFoundError(
            f"Manifest not found: {path}"
        )

    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(
            file
        )


def clean_json_text(
    raw: str,
) -> str:
    raw = raw.strip()

    if raw.startswith(
        "```json"
    ):
        raw = raw[
            len(
                "```json"
            ):
        ]

    elif raw.startswith(
        "```"
    ):
        raw = raw[
            len(
                "```"
            ):
        ]

    if raw.endswith(
        "```"
    ):
        raw = raw[
            :-3
        ]

    return raw.strip()


def validate_recipe(
    recipe: dict,
    manifest_entry: dict,
    cuisine: str,
) -> dict:
    """
    Basic structural validation only.

    Gemini is responsible for semantic extraction.
    """

    title = str(
        recipe.get(
            "title",
            ""
        )
    ).strip()

    ingredients = (
        recipe.get(
            "ingredients",
            []
        )
    )

    steps = (
        recipe.get(
            "steps",
            []
        )
    )

    if not title:
        raise RuntimeError(
            "Extracted recipe has no title."
        )

    if not isinstance(
        ingredients,
        list,
    ):
        raise RuntimeError(
            f"{title}: ingredients is not a list."
        )

    if not isinstance(
        steps,
        list,
    ):
        raise RuntimeError(
            f"{title}: steps is not a list."
        )

    ingredients = [
        str(item).strip()
        for item in ingredients
        if str(item).strip()
    ]

    steps = [
        str(item).strip()
        for item in steps
        if str(item).strip()
    ]

    if not ingredients:
        raise RuntimeError(
            f"{title}: no ingredients extracted."
        )

    if not steps:
        raise RuntimeError(
            f"{title}: no steps extracted."
        )

    return {
        "title":
            title,

        "cuisine":
            cuisine,

        "category":
            str(
                recipe.get(
                    "category",
                    ""
                )
            ).strip(),

        "servings":
            str(
                recipe.get(
                    "servings",
                    ""
                )
            ).strip(),

        "ingredients":
            ingredients,

        "steps":
            steps,

        "source_pages": [
            manifest_entry[
                "start_page"
            ],
            manifest_entry[
                "end_page"
            ],
        ],
    }


def extract_one_recipe(
    client,
    uploaded_file,
    manifest_entry: dict,
    cuisine: str,
    source_file: str,
) -> dict:
    """
    Extract exactly ONE recipe using the page range
    identified by Gemini Pass 1.
    """

    title = manifest_entry[
        "title"
    ]

    start_page = manifest_entry[
        "start_page"
    ]

    end_page = manifest_entry[
        "end_page"
    ]

    print(
        f"\nExtracting: {title}"
    )

    print(
        f"Pages: {start_page}-{end_page}"
    )

    prompt = f"""
You are extracting exactly ONE recipe from a cookbook PDF.

Cuisine:
{cuisine}

Source file:
{source_file}

Target recipe:
{title}

The recipe was identified in the whole-book manifest as appearing
from PDF page {start_page} through PDF page {end_page}.

Your task is to read the PDF and extract ONLY this recipe.

============================================================
CRITICAL RULES
============================================================

1. Extract ONLY:
   {title}

2. Do NOT include content belonging to the recipe before or after it.

3. Use the manifest page range as guidance, but use document layout
   and meaning to understand the exact recipe boundary.

4. Separate INGREDIENTS from COOKING STEPS correctly.

An ingredient entry should describe food/material used in the recipe,
for example:

"2 eggs"
"1 cup flour"
"salt"
"1/2 lb chicken"

Do NOT put complete cooking instructions in the ingredients list.

Bad ingredient:
"Heat the butter in a pan and cook the onions until brown."

Good ingredients:
"butter"
"onions"

5. Steps must contain actual preparation/cooking instructions.

6. Preserve quantities and units from the cookbook whenever possible.

7. Do NOT invent missing quantities.

8. Do NOT invent ingredients.

9. Do NOT invent substitutions.

10. Do NOT import ingredients from nearby recipes.

11. If the cookbook uses prose instead of a formal ingredient list,
    infer the ingredient LIST from the recipe prose, but do not invent
    anything that is not explicitly used.

12. If ingredients are mentioned inside instructions, extract those
    ingredients cleanly into the ingredients list while also preserving
    the instructions in the steps.

13. Remove unrelated material such as:
    - chapter commentary
    - historical notes
    - general cooking advice
    - serving philosophy
    - unrelated recipes

14. Category should describe the actual dish:
    Soup
    Chicken
    Beef
    Lamb
    Pork
    Fish
    Seafood
    Rice
    Noodles
    Vegetable
    Egg
    Dessert
    Sauce
    Appetizer
    Bakery
    or another short sensible category.

15. Never label a sauce as Dessert.

16. Servings:
    - preserve the cookbook value if present
    - otherwise return ""

17. If the recipe references another recipe, for example:
    "prepare with Brown Stock No. 13",
    keep that reference as written.
    Do not copy the referenced recipe into this recipe.

============================================================
OUTPUT
============================================================

Return ONLY valid JSON in exactly this structure:

{{
  "title": "{title}",
  "category": "",
  "servings": "",
  "ingredients": [
    "ingredient"
  ],
  "steps": [
    "step"
  ]
}}

Do not include markdown.
Do not include explanations.
"""

    interaction = client.interactions.create(
        model=MODEL_NAME,
        input=[
            {
                "type":
                    "document",

                "uri":
                    uploaded_file.uri,

                "mime_type":
                    uploaded_file.mime_type,
            },
            {
                "type":
                    "text",

                "text":
                    prompt,
            },
        ],
    )

    raw = clean_json_text(
        interaction.output_text
    )

    try:
        recipe = json.loads(
            raw
        )

    except json.JSONDecodeError as error:
        print(
            "\nINVALID JSON:"
        )

        print(
            raw
        )

        raise RuntimeError(
            f"Gemini returned invalid JSON "
            f"for {title}"
        ) from error

    return validate_recipe(
        recipe=recipe,
        manifest_entry=
            manifest_entry,
        cuisine=cuisine,
    )


def extract_recipes(
    pdf_path: str,
    manifest_path: str,
    output_path: str,
    limit: int | None = None,
):
    pdf = Path(
        pdf_path
    )

    manifest = load_manifest(
        manifest_path
    )

    cuisine = manifest[
        "cuisine"
    ]

    recipes_manifest = (
        manifest[
            "recipes"
        ]
    )

    if limit is not None:
        recipes_manifest = (
            recipes_manifest[
                :limit
            ]
        )

    client = genai.Client(
        api_key=API_KEY
    )

    print(
        f"Uploading cookbook: "
        f"{pdf.name}"
    )

    uploaded_file = (
        client.files.upload(
            file=str(
                pdf
            )
        )
    )

    print(
        "Upload complete."
    )

    extracted = []
    failures = []

    checkpoint_path = Path(
        output_path
    ).with_name(
        Path(output_path).stem
        + "_checkpoint.json"
    )

    if checkpoint_path.exists():
        print(
            f"Checkpoint found: "
            f"{checkpoint_path}"
        )

        with checkpoint_path.open(
            "r",
            encoding="utf-8",
        ) as file:
            extracted = json.load(
                file
            )

        print(
            f"Resuming with "
            f"{len(extracted)} already "
            f"extracted recipe(s)."
        )

    total = len(
        recipes_manifest
    )

    already_done = len(
        extracted
    )

    recipes_manifest = (
        recipes_manifest[
            already_done:
        ]
    )

    for index, entry in enumerate(
        recipes_manifest,
        start=already_done + 1,
    ):
        print(
            f"\n================================"
        )

        print(
            f"RECIPE {index}/{total}"
        )

        print(
            f"================================"
        )

        try:
            recipe = extract_one_recipe(
                client=client,
                uploaded_file=
                    uploaded_file,
                manifest_entry=
                    entry,
                cuisine=
                    cuisine,
                source_file=
                    pdf.name,
            )

            extracted.append(
                recipe
            )

            with checkpoint_path.open(
                "w",
                encoding="utf-8",
            ) as file:
                json.dump(
                    extracted,
                    file,
                    indent=2,
                    ensure_ascii=False,
                )

            print(
                "Extraction successful."
            )

        except Exception as error:
            print(
                f"Extraction failed: "
                f"{error}"
            )

            failures.append(
                {
                    "manifest_entry":
                        entry,

                    "error":
                        str(
                            error
                        ),
                }
            )

    # ========================================================
    # Convert to ChefAI runtime format
    # ========================================================

    cuisine_slug = (
        cuisine.lower()
        .replace(
            " ",
            "_"
        )
    )

    runtime_recipes = []

    for index, recipe in enumerate(
        extracted,
        start=1,
    ):
        runtime_recipes.append(
            {
                "id":
                    f"{cuisine_slug}_"
                    f"{index:04d}",

                "title":
                    recipe[
                        "title"
                    ],

                "cuisine":
                    recipe[
                        "cuisine"
                    ],

                "category":
                    recipe[
                        "category"
                    ],

                "source_file":
                    pdf.name,

                "source_pages":
                    recipe["source_pages"],

                "servings":
                    recipe[
                        "servings"
                    ],

                "ingredients":
                    recipe[
                        "ingredients"
                    ],

                "steps":
                    recipe[
                        "steps"
                    ],

                "nutrition": {
                    "calories":
                        None,

                    "protein_g":
                        None,

                    "carbohydrates_g":
                        None,

                    "fat_g":
                        None,
                },
            }
        )

    output = Path(
        output_path
    )

    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with output.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            runtime_recipes,
            file,
            indent=2,
            ensure_ascii=False,
        )

    report_path = output.with_name(
        output.stem
        + "_report.json"
    )

    with report_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            {
                "source_file":
                    pdf.name,

                "cuisine":
                    cuisine,

                "requested":
                    total,

                "successful":
                    len(
                        runtime_recipes
                    ),

                "failed":
                    len(
                        failures
                    ),

                "failures":
                    failures,
            },
            file,
            indent=2,
            ensure_ascii=False,
        )

    print(
        "\n================================"
    )

    print(
        "EXTRACTION COMPLETE"
    )

    print(
        "================================"
    )

    print(
        f"Successful: "
        f"{len(runtime_recipes)}"
    )

    print(
        f"Failed: "
        f"{len(failures)}"
    )

    print(
        f"\nRecipes:\n"
        f"{output}"
    )

    print(
        f"\nReport:\n"
        f"{report_path}"
    )


if __name__ == "__main__":

    extract_recipes(
        pdf_path=(
            "data/recipes/Italian/"
            "italian3.pdf"
        ),

        manifest_path=(
            "data/structured_recipes/"
            "italian_recipe_manifest.json"
        ),

        output_path=(
            "data/structured_recipes/"
            "italian_recipes_gemini.json"
        ),

        # IMPORTANT:
        # Only test the first five recipes for now.
        limit=None,
    )