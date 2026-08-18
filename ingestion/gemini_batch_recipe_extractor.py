import base64
import json
import os
import re
import time
from pathlib import Path
import pymupdf


from dotenv import load_dotenv
from google import genai


# ============================================================
# Configuration
# ============================================================

load_dotenv()

API_KEY = os.getenv(
    "GEMINI_API_KEY"
)

if not API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY was not found in .env"
    )


MODEL_NAME = "gemini-3.5-flash-lite"

# Start conservatively.
#
# Around 10 recipes/request means a ~200 recipe book
# needs roughly 20 API requests.
RECIPES_PER_BATCH = 12

# Prevent one batch from accidentally containing a huge
# portion of an unusual cookbook.
MAX_PAGES_PER_BATCH = 18

# We do not want to hammer the per-minute token/request limits.
DELAY_BETWEEN_BATCHES_SECONDS = 15


# ============================================================
# Utility functions
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


def save_json(
    path: Path,
    data,
):
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = (
        path.with_suffix(
            path.suffix + ".tmp"
        )
    )

    with temporary_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            data,
            file,
            indent=2,
            ensure_ascii=False,
        )

    temporary_path.replace(
        path
    )


def normalize_title(
    title: str,
) -> str:
    title = title.lower()

    title = re.sub(
        r"\s+",
        " ",
        title,
    )

    return title.strip()


def recipe_key(
    entry: dict,
) -> str:
    return (
        f"{normalize_title(entry['title'])}|"
        f"{entry['start_page']}|"
        f"{entry['end_page']}"
    )


def clean_json_text(
    raw: str,
) -> str:
    raw = raw.strip()

    if raw.startswith(
        "```json"
    ):
        raw = raw[
            len("```json"):
        ]

    elif raw.startswith(
        "```"
    ):
        raw = raw[
            len("```"):
        ]

    if raw.endswith(
        "```"
    ):
        raw = raw[:-3]

    return raw.strip()


# ============================================================
# Batch construction
# ============================================================

def build_batches(
    manifest_entries: list[dict],
) -> list[list[dict]]:
    """
    Group nearby recipes together.

    A batch is limited by BOTH:
    - number of recipes
    - total PDF page range

    This keeps requests predictable.
    """

    batches = []

    current_batch = []

    current_start_page = None
    current_end_page = None

    for entry in manifest_entries:

        entry_start = int(
            entry["start_page"]
        )

        entry_end = int(
            entry["end_page"]
        )

        if not current_batch:
            current_batch = [
                entry
            ]

            current_start_page = (
                entry_start
            )

            current_end_page = (
                entry_end
            )

            continue

        proposed_end = max(
            current_end_page,
            entry_end,
        )

        proposed_page_count = (
            proposed_end
            - current_start_page
            + 1
        )

        too_many_recipes = (
            len(current_batch)
            >= RECIPES_PER_BATCH
        )

        too_many_pages = (
            proposed_page_count
            > MAX_PAGES_PER_BATCH
        )

        if (
            too_many_recipes
            or too_many_pages
        ):
            batches.append(
                current_batch
            )

            current_batch = [
                entry
            ]

            current_start_page = (
                entry_start
            )

            current_end_page = (
                entry_end
            )

        else:
            current_batch.append(
                entry
            )

            current_end_page = (
                proposed_end
            )

    if current_batch:
        batches.append(
            current_batch
        )

    return batches


# ============================================================
# PDF slicing
# ============================================================

def create_pdf_slice(
    source_pdf: Path,
    start_page: int,
    end_page: int,
    output_path: Path,
):
    """
    Create a temporary PDF containing ONLY the pages needed
    for the current batch.

    start_page/end_page use the manifest's 1-based PDF numbering.
    """

    source_document = pymupdf.open(
        source_pdf
    )

    sliced_document = pymupdf.open()

    # PyMuPDF uses zero-based page indexes.
    sliced_document.insert_pdf(
        source_document,
        from_page=start_page - 1,
        to_page=end_page - 1,
    )

    sliced_document.save(
        output_path
    )

    sliced_document.close()
    source_document.close()


# ============================================================
# Validation
# ============================================================

def clean_recipe(
    recipe: dict,
    cuisine: str,
    source_file: str,
) -> dict:
    title = str(
        recipe.get(
            "title",
            "",
        )
    ).strip()

    category = str(
        recipe.get(
            "category",
            "",
        )
    ).strip()

    servings = str(
        recipe.get(
            "servings",
            "",
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
        raise ValueError(
            "Recipe has no title."
        )

    if not isinstance(
        ingredients,
        list,
    ):
        raise ValueError(
            f"{title}: ingredients "
            "is not a list."
        )

    if not isinstance(
        steps,
        list,
    ):
        raise ValueError(
            f"{title}: steps "
            "is not a list."
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
        raise ValueError(
            f"{title}: no ingredients."
        )

    if not steps:
        raise ValueError(
            f"{title}: no cooking steps."
        )

    source_pages = (
        recipe.get(
            "source_pages",
            []
        )
    )

    cleaned_pages = []

    if isinstance(
        source_pages,
        list,
    ):
        for page in source_pages:
            try:
                cleaned_pages.append(
                    int(page)
                )
            except (
                TypeError,
                ValueError,
            ):
                pass

    return {
        "title":
            title,

        "cuisine":
            cuisine,

        "category":
            category,

        "source_file":
            source_file,

        "source_pages":
            sorted(
                set(
                    cleaned_pages
                )
            ),

        "servings":
            servings,

        "ingredients":
            ingredients,

        "steps":
            steps,

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


# ============================================================
# Gemini extraction
# ============================================================

def extract_batch(
    client,
    pdf_slice_path: Path,
    batch: list[dict],
    cuisine: str,
    source_file: str,
    original_start_page: int,
) -> list[dict]:
    """
    Send ONE small PDF and ask Gemini to extract all recipes
    listed in this batch.
    """

    manifest_text = json.dumps(
        batch,
        indent=2,
        ensure_ascii=False,
    )

    prompt = f"""
You are extracting recipes from a small section of a cookbook.

Cuisine:
{cuisine}

Original source file:
{source_file}

The attached PDF is ONLY a slice of the original cookbook.

The first page of this attached slice corresponds to ORIGINAL
PDF page {original_start_page}.

The recipes that must be extracted are listed below.

============================================================
RECIPE MANIFEST FOR THIS BATCH
============================================================

{manifest_text}

============================================================
YOUR TASK
============================================================

Extract EVERY recipe in the manifest above.

The manifest was created earlier by analyzing the complete cookbook,
so treat its titles and ORIGINAL PDF page boundaries as authoritative
guidance.

You must return one structured recipe for every manifest entry.

============================================================
CRITICAL RULES
============================================================

1. Do NOT create recipes that are not in the manifest.

2. Do NOT omit a manifest recipe.

3. Do NOT merge separate recipes.

4. Preserve explicitly separate variants.

For example:

Roman Fry I
Roman Fry II

must remain separate.

5. Correctly separate INGREDIENTS from COOKING STEPS.

Ingredient entries must describe food/material actually used.

Good:
"2 eggs"
"1 cup flour"
"butter"
"salt"

Bad:
"Heat the butter and fry the onions until brown."

6. If the cookbook is written in prose rather than having a formal
ingredient list, identify the ingredients explicitly used in the prose
and place them in the ingredients list.

7. Do NOT invent quantities.

8. Do NOT invent ingredients.

9. Do NOT invent substitutions.

10. Do NOT import ingredients or instructions from neighboring recipes.

11. Preserve quantities and units as written whenever possible.

12. Remove unrelated:
- history
- commentary
- general cooking advice
- headers
- footers
- chapter prose

13. Category must describe the dish sensibly.

Examples:
Soup
Sauce
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
Bakery
Appetizer

Do not label sauces as Dessert.

14. Preserve servings only when stated.
Otherwise use "".

15. source_pages MUST use the ORIGINAL PDF page numbers from the
manifest, NOT the page numbers of the temporary attached PDF.

16. If a recipe references another recipe, preserve the reference.
Do not copy the other recipe into this recipe.

============================================================
OUTPUT FORMAT
============================================================

Return ONLY valid JSON.

Use exactly:

{{
  "recipes": [
    {{
      "title": "Recipe title",
      "category": "Category",
      "servings": "",
      "source_pages": [10, 11],
      "ingredients": [
        "ingredient"
      ],
      "steps": [
        "step"
      ]
    }}
  ]
}}

Return the recipes in the SAME ORDER as the manifest.

Do not include markdown.
Do not include commentary.
"""

    pdf_data = base64.b64encode(
        pdf_slice_path.read_bytes()
    ).decode(
        "utf-8"
    )

    interaction = (
        client.interactions.create(
            model=MODEL_NAME,
            input=[
                {
                    "type":
                        "document",

                    "data":
                        pdf_data,

                    "mime_type":
                        "application/pdf",
                },
                {
                    "type":
                        "text",

                    "text":
                        prompt,
                },
            ],
        )
    )

    raw = clean_json_text(
        interaction.output_text
    )

    result = json.loads(
        raw
    )

    recipes = result.get(
        "recipes",
        []
    )

    if not isinstance(
        recipes,
        list,
    ):
        raise RuntimeError(
            "Gemini response does not "
            "contain a recipes list."
        )

    return recipes


# ============================================================
# Main extraction
# ============================================================

def run_extraction(
    pdf_path: str,
    manifest_path: str,
    output_path: str,
):
    pdf = Path(
        pdf_path
    )

    manifest_file = Path(
        manifest_path
    )

    output = Path(
        output_path
    )

    if not pdf.exists():
        raise FileNotFoundError(
            pdf
        )

    if not manifest_file.exists():
        raise FileNotFoundError(
            manifest_file
        )

    manifest = load_json(
        manifest_file
    )

    cuisine = manifest[
        "cuisine"
    ]

    manifest_entries = manifest[
        "recipes"
    ]

    batches = build_batches(
        manifest_entries
    )

    print(
        f"\nManifest recipes: "
        f"{len(manifest_entries)}"
    )

    print(
        f"Extraction batches: "
        f"{len(batches)}"
    )

    print(
        f"Recipes per batch: "
        f"up to {RECIPES_PER_BATCH}"
    )

    print(
        f"Pages per batch: "
        f"up to {MAX_PAGES_PER_BATCH}"
    )

    # ========================================================
    # Checkpoint
    # ========================================================

    checkpoint_path = (
        output.with_name(
            output.stem
            + "_checkpoint.json"
        )
    )

    checkpoint = {
        "completed_batches":
            [],

        "recipes":
            [],

        "failures":
            [],
    }

    if checkpoint_path.exists():
        checkpoint = load_json(
            checkpoint_path
        )

        print(
            f"\nCheckpoint loaded."
        )

        print(
            f"Completed batches: "
            f"{len(checkpoint['completed_batches'])}"
        )

        print(
            f"Recipes already saved: "
            f"{len(checkpoint['recipes'])}"
        )

    completed_batches = set(
        checkpoint[
            "completed_batches"
        ]
    )

    client = genai.Client(
        api_key=API_KEY
    )

    temp_directory = Path(
        "temp/gemini_ingestion"
    )

    temp_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    # ========================================================
    # Process batches
    # ========================================================

    for batch_index, batch in enumerate(
        batches,
        start=1,
    ):

        batch_id = (
            f"batch_{batch_index:04d}"
        )

        if batch_id in completed_batches:
            print(
                f"\nSkipping completed "
                f"{batch_id}."
            )

            continue

        start_page = min(
            int(
                recipe[
                    "start_page"
                ]
            )
            for recipe in batch
        )

        end_page = max(
            int(
                recipe[
                    "end_page"
                ]
            )
            for recipe in batch
        )

        print(
            "\n================================"
        )

        print(
            f"BATCH {batch_index}/"
            f"{len(batches)}"
        )

        print(
            "================================"
        )

        print(
            f"Recipes: "
            f"{len(batch)}"
        )

        print(
            f"Original pages: "
            f"{start_page}-{end_page}"
        )

        temp_pdf = (
            temp_directory
            / (
                f"{batch_id}_"
                f"pages_"
                f"{start_page}_"
                f"{end_page}.pdf"
            )
        )

        create_pdf_slice(
            source_pdf=
                pdf,

            start_page=
                start_page,

            end_page=
                end_page,

            output_path=
                temp_pdf,
        )

        try:
            raw_recipes = (
                extract_batch(
                    client=client,
                    pdf_slice_path=
                        temp_pdf,
                    batch=batch,
                    cuisine=cuisine,
                    source_file=
                        pdf.name,
                    original_start_page=
                        start_page,
                )
            )

            expected_titles = [
                normalize_title(
                    entry[
                        "title"
                    ]
                )
                for entry in batch
            ]

            returned_titles = [
                normalize_title(
                    str(
                        recipe.get(
                            "title",
                            "",
                        )
                    )
                )
                for recipe
                in raw_recipes
            ]

            missing_titles = [
                batch[index][
                    "title"
                ]
                for index, title
                in enumerate(
                    expected_titles
                )
                if title
                not in returned_titles
            ]

            if missing_titles:
                raise RuntimeError(
                    "Gemini omitted recipe(s): "
                    + ", ".join(
                        missing_titles
                    )
                )

            cleaned_batch = []

            for recipe in raw_recipes:
                cleaned_batch.append(
                    clean_recipe(
                        recipe=
                            recipe,

                        cuisine=
                            cuisine,

                        source_file=
                            pdf.name,
                    )
                )

            checkpoint[
                "recipes"
            ].extend(
                cleaned_batch
            )

            checkpoint[
                "completed_batches"
            ].append(
                batch_id
            )

            save_json(
                checkpoint_path,
                checkpoint,
            )

            print(
                f"Batch successful."
            )

            print(
                f"Total recipes saved: "
                f"{len(checkpoint['recipes'])}"
            )

        except Exception as error:
            error_text = str(
                error
            )

            print(
                "\nBATCH FAILED:"
            )

            print(
                error_text
            )

            if (
                "429" in error_text
                or
                "RESOURCE_EXHAUSTED"
                in error_text
                or
                "quota"
                in error_text.lower()
                or
                "rate limit"
                in error_text.lower()
            ):
                print(
                    "\nGemini quota reached."
                )

                print(
                    "Checkpoint is safe."
                )

                print(
                    "Rerun this script after "
                    "the quota resets."
                )

                break

            checkpoint[
                "failures"
            ].append(
                {
                    "batch_id":
                        batch_id,

                    "start_page":
                        start_page,

                    "end_page":
                        end_page,

                    "recipes":
                        [
                            item[
                                "title"
                            ]
                            for item
                            in batch
                        ],

                    "error":
                        error_text,
                }
            )

            save_json(
                checkpoint_path,
                checkpoint,
            )

        finally:
            try:
                temp_pdf.unlink()
            except FileNotFoundError:
                pass

        print(
            f"\nWaiting "
            f"{DELAY_BETWEEN_BATCHES_SECONDS} "
            f"seconds before next batch..."
        )

        time.sleep(
            DELAY_BETWEEN_BATCHES_SECONDS
        )

    # ========================================================
    # Build final ChefAI JSON
    # ========================================================

    final_recipes = []

    for index, recipe in enumerate(
        checkpoint[
            "recipes"
        ],
        start=1,
    ):
        final_recipe = dict(
            recipe
        )

        final_recipe[
            "id"
        ] = (
            f"{cuisine.lower()}_"
            f"{index:04d}"
        )

        # Put ID first simply for readability.
        final_recipe = {
            "id":
                final_recipe[
                    "id"
                ],

            **{
                key:
                    value

                for key, value
                in final_recipe.items()

                if key != "id"
            },
        }

        final_recipes.append(
            final_recipe
        )

    save_json(
        output,
        final_recipes,
    )

    report_path = output.with_name(
        output.stem
        + "_report.json"
    )

    save_json(
        report_path,
        {
            "source_file":
                pdf.name,

            "cuisine":
                cuisine,

            "manifest_recipe_count":
                len(
                    manifest_entries
                ),

            "batch_count":
                len(
                    batches
                ),

            "completed_batch_count":
                len(
                    checkpoint[
                        "completed_batches"
                    ]
                ),

            "extracted_recipe_count":
                len(
                    final_recipes
                ),

            "failures":
                checkpoint[
                    "failures"
                ],
        },
    )

    print(
        "\n================================"
    )

    print(
        "CURRENT EXTRACTION STATUS"
    )

    print(
        "================================"
    )

    print(
        f"Recipes saved: "
        f"{len(final_recipes)}"
    )

    print(
        f"Batches complete: "
        f"{len(checkpoint['completed_batches'])}"
        f"/{len(batches)}"
    )

    print(
        f"\nOutput:\n"
        f"{output}"
    )

    print(
        f"\nCheckpoint:\n"
        f"{checkpoint_path}"
    )


# ============================================================
# Entry point
# ============================================================

if __name__ == "__main__":

    run_extraction(
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
    )