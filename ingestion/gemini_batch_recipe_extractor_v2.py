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

# Number of recipes Gemini extracts per request.
RECIPES_PER_BATCH = 12

# Prevent one batch from covering too many PDF pages.
MAX_PAGES_PER_BATCH = 18

# Avoid hitting request/token-per-minute limits.
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
    """
    Save JSON atomically.

    The temporary file prevents a partially-written checkpoint
    from corrupting the run if the program stops unexpectedly.
    """

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
    title = str(
        title
    ).lower()

    # Normalize apostrophes.
    title = title.replace(
        "’",
        "'",
    )

    title = title.replace(
        "‘",
        "'",
    )

    # Ignore punctuation differences when matching
    # Gemini output against the manifest.
    title = re.sub(
        r"[^a-z0-9]+",
        " ",
        title,
    )

    title = re.sub(
        r"\s+",
        " ",
        title,
    )

    return title.strip()

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


def slugify(
    text: str,
) -> str:
    """
    Convert the book filename into a stable ID prefix.

    Example:
        Italian2 -> italian2
        World Cuisines -> world_cuisines
    """

    text = text.lower().strip()

    text = re.sub(
        r"[^a-z0-9]+",
        "_",
        text,
    )

    return text.strip(
        "_"
    )


# ============================================================
# Batch construction
# ============================================================

def build_batches(
    manifest_entries: list[dict],
) -> list[list[dict]]:
    """
    Group nearby recipes together.

    A batch is limited by:
    - number of recipes
    - total original PDF page range
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
    Create a temporary PDF containing only the pages required
    for this extraction batch.

    Manifest page numbers are 1-based.
    PyMuPDF page indexes are 0-based.
    """

    source_document = pymupdf.open(
        source_pdf
    )

    sliced_document = pymupdf.open()

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
# Recipe validation / cleaning
# ============================================================

def clean_recipe(
    recipe: dict,
    manifest_entry: dict,
    source_file: str,
    collection: str,
) -> dict:
    """
    Clean one extracted recipe.

    IMPORTANT:
    Cuisine, country and source page range come from the
    whole-book manifest, which is our authoritative Pass-1
    metadata.

    Gemini Pass 2 extracts the actual recipe contents.

    Nutrition is preserved ONLY if Gemini extracted it
    explicitly from the cookbook. Missing values remain None.
    """

    title = str(
        recipe.get(
            "title",
            manifest_entry.get(
                "title",
                "",
            ),
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

    ingredients = recipe.get(
        "ingredients",
        []
    )

    steps = recipe.get(
        "steps",
        []
    )

    # --------------------------------------------------------
    # Validate title / ingredients / steps
    # --------------------------------------------------------

    if not title:
        raise ValueError(
            "Recipe has no title."
        )

    if not isinstance(
        ingredients,
        list,
    ):
        raise ValueError(
            f"{title}: ingredients is not a list."
        )

    if not isinstance(
        steps,
        list,
    ):
        raise ValueError(
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
        raise ValueError(
            f"{title}: no ingredients."
        )

    if not steps:
        raise ValueError(
            f"{title}: no steps."
        )

    # --------------------------------------------------------
    # Pass 1 is authoritative for origin metadata
    # --------------------------------------------------------

    cuisine = str(
        manifest_entry.get(
            "cuisine",
            "",
        )
    ).strip()

    country = str(
        manifest_entry.get(
            "country",
            "",
        )
    ).strip()

    start_page = int(
        manifest_entry[
            "start_page"
        ]
    )

    end_page = int(
        manifest_entry[
            "end_page"
        ]
    )

    source_pages = list(
        range(
            start_page,
            end_page + 1,
        )
    )

    # --------------------------------------------------------
    # Nutrition
    #
    # Gemini should only populate this when the cookbook
    # explicitly contains nutrition values.
    # --------------------------------------------------------

    nutrition = recipe.get(
        "nutrition",
        {}
    )

    if not isinstance(
        nutrition,
        dict,
    ):
        nutrition = {}

    calories = nutrition.get(
        "calories"
    )

    protein_g = nutrition.get(
        "protein_g"
    )

    carbohydrates_g = nutrition.get(
        "carbohydrates_g"
    )

    fat_g = nutrition.get(
        "fat_g"
    )

    basis = nutrition.get(
        "basis"
    )

    # Normalize basis if Gemini returns an unexpected value.
    valid_bases = {
        "per_serving",
        "whole_recipe",
        "unspecified",
        None,
    }

    if basis not in valid_bases:
        basis = "unspecified"

    # --------------------------------------------------------
    # Final ChefAI recipe structure
    # --------------------------------------------------------

    return {
        "title":
            title,

        "cuisine":
            cuisine,

        "country":
            country,

        "category":
            category,

        "source_file":
            source_file,

        "source_collection":
            collection,

        "source_pages":
            source_pages,

        "servings":
            servings,

        "ingredients":
            ingredients,

        "steps":
            steps,

        "nutrition": {
            "calories":
                calories,

            "protein_g":
                protein_g,

            "carbohydrates_g":
                carbohydrates_g,

            "fat_g":
                fat_g,

            "basis":
                basis,
        },
    }

# ============================================================
# Gemini batch extraction
# ============================================================

def extract_batch(
    client,
    pdf_slice_path: Path,
    batch: list[dict],
    source_file: str,
    collection: str,
    original_start_page: int,
) -> list[dict]:
    """
    Send one small PDF slice to Gemini and extract all recipes
    listed in the supplied manifest batch.
    """

    manifest_text = json.dumps(
        batch,
        indent=2,
        ensure_ascii=False,
    )

    prompt = f"""
You are extracting recipes from a small section of a cookbook.

Original source file:
{source_file}

Collection:
{collection}

The attached PDF contains only a slice of the original cookbook.

The first page of this attached PDF corresponds to ORIGINAL
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

The manifest was created previously by analyzing the entire
cookbook.

Treat the manifest's:

- title
- start_page
- end_page
- cuisine
- country

as authoritative metadata.

Return one structured recipe for every manifest entry.

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

must remain two separate recipes.

5. Correctly separate INGREDIENTS from COOKING STEPS.

Ingredient entries should contain ingredients/materials actually
used in the dish.

Good ingredient entries:

"2 eggs"
"1 cup flour"
"butter"
"salt"

Bad ingredient entry:

"Heat the butter and fry the onions until brown."

6. If the cookbook is written in prose rather than using a formal
ingredient list, identify the ingredients explicitly mentioned in
the recipe and place them in the ingredients list.

7. Do NOT invent quantities.

8. Do NOT invent ingredients.

9. Do NOT invent substitutions.

10. Do NOT import ingredients from neighboring recipes.

11. Do NOT import cooking instructions from neighboring recipes.

============================================================
REWRITING / COPYRIGHT RULES
============================================================

- Do NOT copy cookbook sentences verbatim.

- Rewrite every cooking instruction concisely in your own words.

- Preserve the factual meaning of the recipe.

- Preserve ingredient names accurately.

- Preserve quantities accurately.

- Preserve units accurately.

- Preserve cooking temperatures accurately.

- Preserve cooking times accurately.

- Ingredient entries should be concise structured facts,
  not copied descriptive prose.

- Remove decorative, historical, narrative, or stylistic prose.

- The goal is a structured recipe representation,
  NOT a transcription of the cookbook.

- Never reproduce long passages from the source.

- If a cooking instruction can be expressed more briefly
  without losing important cooking information, do so.

============================================================
OTHER EXTRACTION RULES
============================================================

12. Remove unrelated material such as:

- history
- commentary
- general cooking advice
- headers
- footers
- chapter prose
- unrelated recipe text

13. Category should describe the actual dish.

Examples include:

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

14. Preserve servings only if the cookbook states them.

Otherwise return:

"servings": ""

15. The manifest may contain recipes from DIFFERENT countries
and cuisines in the same batch.

Do NOT assign one cuisine or country to the entire batch.

16. For every returned recipe, copy its cuisine and country from
its corresponding manifest entry.

17. source_pages must refer to ORIGINAL PDF page numbers, not
the temporary sliced-PDF page numbers.

18. If a recipe references another recipe, sauce or preparation,
preserve the reference.

Do not copy the referenced recipe into this recipe.

============================================================
NUTRITION RULES
============================================================

- If nutrition values are explicitly printed for this recipe,
  extract them accurately.

- Do NOT calculate nutrition.

- Do NOT estimate nutrition.

- Do NOT infer nutrition from ingredients.

- If a value is not explicitly printed, return null.

- If nutrition is explicitly stated per serving, use:
  "basis": "per_serving"

- If nutrition is explicitly for the entire recipe, use:
  "basis": "whole_recipe"

- If nutrition is printed but the basis is unclear, use:
  "basis": "unspecified"

- If no nutrition is printed at all, use:
  "basis": null

============================================================
OUTPUT FORMAT
============================================================

Return ONLY valid JSON.

Use exactly:

{{
  "recipes": [
    {{
      "title": "Recipe title",
      "cuisine": "Cuisine",
      "country": "Country",
      "category": "Category",
      "servings": "",
      "source_pages": [10, 11],
      "ingredients": [
        "ingredient"
      ],
      "steps": [
        "short paraphrased cooking instruction"
      ],
      "nutrition": {{
        "calories": null,
        "protein_g": null,
        "carbohydrates_g": null,
        "fat_g": null,
        "basis": null
      }}
    }}
  ]
}}

Return the recipes in the SAME ORDER as the manifest.

Do not include markdown.

Do not include commentary outside the JSON.
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
            "Gemini response does not contain "
            "a recipes list."
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

    # --------------------------------------------------------
    # Check paths BEFORE loading anything.
    # --------------------------------------------------------

    if not pdf.exists():
        raise FileNotFoundError(
            f"PDF not found: {pdf}"
        )

    if not manifest_file.exists():
        raise FileNotFoundError(
            f"Manifest not found: {manifest_file}"
        )

    # --------------------------------------------------------
    # Load manifest.
    # --------------------------------------------------------

    manifest = load_json(
        manifest_file
    )

    collection = str(
        manifest.get(
            "collection",
            pdf.stem,
        )
    ).strip()

    manifest_entries = manifest.get(
        "recipes",
        []
    )

    if not isinstance(
        manifest_entries,
        list,
    ):
        raise RuntimeError(
            "Manifest recipes field is not a list."
        )

    if not manifest_entries:
        raise RuntimeError(
            "Manifest contains no recipes."
        )

    # Stable ID prefix comes from the BOOK,
    # not from one cuisine.
    book_slug = slugify(
        pdf.stem
    )

    batches = build_batches(
        manifest_entries
    )

    print(
        f"\nSource file: "
        f"{pdf.name}"
    )

    print(
        f"Collection: "
        f"{collection}"
    )

    print(
        f"Manifest recipes: "
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
        "source_file":
            pdf.name,

        "collection":
            collection,

        "model":
            MODEL_NAME,

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
            "\nCheckpoint loaded."
        )

        print(
            f"Completed batches: "
            f"{len(checkpoint.get('completed_batches', []))}"
        )

        print(
            f"Recipes already saved: "
            f"{len(checkpoint.get('recipes', []))}"
        )

    completed_batches = set(
        checkpoint.get(
            "completed_batches",
            [],
        )
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
                f"{book_slug}_"
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

            raw_recipes = extract_batch(
                client=client,

                pdf_slice_path=
                    temp_pdf,

                batch=
                    batch,

                source_file=
                    pdf.name,

                collection=
                    collection,

                original_start_page=
                    start_page,
            )

            # ------------------------------------------------
            # Make sure Gemini returned all expected recipes.
            # ------------------------------------------------

            expected_titles = [
                normalize_title(
                    entry[
                        "title"
                    ]
                )
                for entry in batch
            ]

            returned_by_title = {}

            for recipe in raw_recipes:

                title_key = normalize_title(
                    recipe.get(
                        "title",
                        "",
                    )
                )

                if title_key:
                    returned_by_title[
                        title_key
                    ] = recipe

            missing_titles = [
                entry[
                    "title"
                ]
                for entry in batch
                if normalize_title(
                    entry[
                        "title"
                    ]
                )
                not in returned_by_title
            ]

            if missing_titles:

                raise RuntimeError(
                    "Gemini omitted recipe(s): "
                    + ", ".join(
                        missing_titles
                    )
                )

            # ------------------------------------------------
            # Clean recipes using their matching manifest entry.
            # ------------------------------------------------

            cleaned_batch = []

            for manifest_entry in batch:

                title_key = normalize_title(
                    manifest_entry[
                        "title"
                    ]
                )

                raw_recipe = (
                    returned_by_title[
                        title_key
                    ]
                )

                cleaned_recipe = clean_recipe(
                    recipe=
                        raw_recipe,

                    manifest_entry=
                        manifest_entry,

                    source_file=
                        pdf.name,

                    collection=
                        collection,
                )

                cleaned_batch.append(
                    cleaned_recipe
                )

            checkpoint["failures"] = [
                failure
                for failure in checkpoint.get(
                    "failures",
                    []
                )
                if failure.get(
                    "batch_id"
                ) != batch_id
            ]

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

            completed_batches.add(
                batch_id
            )

            save_json(
                checkpoint_path,
                checkpoint,
            )

            print(
                "Batch successful."
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

            # -----------------------------------------------
            # Quota/rate limit:
            # stop and resume later from checkpoint.
            # -----------------------------------------------

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
                    "\nGemini quota/rate limit reached."
                )

                print(
                    "Checkpoint is safe."
                )

                print(
                    "Rerun this script later "
                    "to resume."
                )

                break

            # -----------------------------------------------
            # Other failures:
            # record them and continue.
            # -----------------------------------------------

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
        checkpoint.get(
            "recipes",
            [],
        ),
        start=1,
    ):

        final_recipe = dict(
            recipe
        )

        final_recipe[
            "id"
        ] = (
            f"{book_slug}_"
            f"{index:04d}"
        )

        # Put ID first for readability.
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

    # ========================================================
    # Report
    # ========================================================

    report_path = output.with_name(
        output.stem
        + "_report.json"
    )

    save_json(
        report_path,
        {
            "source_file":
                pdf.name,

            "collection":
                collection,

            "model":
                MODEL_NAME,

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
                    checkpoint.get(
                        "completed_batches",
                        [],
                    )
                ),

            "extracted_recipe_count":
                len(
                    final_recipes
                ),

            "failed_batch_count":
                len(
                    checkpoint.get(
                        "failures",
                        [],
                    )
                ),

            "failures":
                checkpoint.get(
                    "failures",
                    [],
                ),
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
        f"{len(checkpoint.get('completed_batches', []))}"
        f"/{len(batches)}"
    )

    print(
        f"Failed batches: "
        f"{len(checkpoint.get('failures', []))}"
    )

    print(
        f"\nOutput:\n"
        f"{output}"
    )

    print(
        f"\nCheckpoint:\n"
        f"{checkpoint_path}"
    )

    print(
        f"\nReport:\n"
        f"{report_path}"
    )