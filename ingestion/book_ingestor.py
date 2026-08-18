import argparse
import json
import re
from pathlib import Path

import fitz

from ingestion.llm_recipe_extractor import (
    extract_recipes_from_pages,
)

from ingestion.recipe_validator import (
    validate_recipes,
)

from ingestion.recipe_deduplicator import (
    deduplicate_recipes,
)


DEFAULT_WINDOW_PAGES = 6
DEFAULT_OVERLAP_PAGES = 1


def slugify(
    text: str,
) -> str:
    text = text.lower()

    text = re.sub(
        r"[^a-z0-9]+",
        "_",
        text,
    )

    return text.strip(
        "_"
    )


def read_pdf_pages(
    pdf_path: Path,
) -> list[dict]:
    """
    Extract page TEXT only.

    IMPORTANT:
    This does NOT parse recipes.

    Qwen will decide what is and is not a recipe.
    """

    document = fitz.open(
        pdf_path
    )

    pages = []

    for index in range(
        len(document)
    ):

        page = document[
            index
        ]

        text = page.get_text(
            "text"
        )

        pages.append(
            {
                "page_number":
                    index + 1,

                "text":
                    text,
            }
        )

    document.close()

    return pages


def check_pdf_text_quality(
    pages: list[dict],
):
    """
    Detect PDFs that appear to be scanned/image-only.

    We deliberately DO NOT silently OCR them here.
    """

    nonempty_pages = 0

    total_characters = 0

    for page in pages:
        text = (
            page[
                "text"
            ]
            .strip()
        )

        if text:
            nonempty_pages += 1

        total_characters += len(
            text
        )

    if not pages:
        raise RuntimeError(
            "PDF contains no pages."
        )

    coverage = (
        nonempty_pages
        / len(
            pages
        )
    )

    average_characters = (
        total_characters
        / len(
            pages
        )
    )

    print(
        f"PDF pages: "
        f"{len(pages)}"
    )

    print(
        f"Pages containing text: "
        f"{nonempty_pages}"
    )

    print(
        f"Text-page coverage: "
        f"{coverage:.1%}"
    )

    print(
        f"Average characters/page: "
        f"{average_characters:.0f}"
    )

    if (
        coverage < 0.70
        or average_characters < 150
    ):
        raise RuntimeError(
            "This PDF appears to contain too little "
            "extractable text. It may be scanned or "
            "image-based. Do not continue with the "
            "text-only ingestion pipeline."
        )


def create_page_windows(
    pages: list[dict],
    window_pages: int,
    overlap_pages: int,
):
    """
    Yield overlapping page windows.

    Example with window=6 overlap=1:

        1-6
        6-11
        11-16
        ...

    Continuation handling protects recipes crossing windows,
    while deduplication removes recipes repeated because of
    overlap.
    """

    if window_pages <= 0:
        raise ValueError(
            "window_pages must be > 0"
        )

    if overlap_pages < 0:
        raise ValueError(
            "overlap_pages cannot be negative"
        )

    if (
        overlap_pages
        >= window_pages
    ):
        raise ValueError(
            "overlap_pages must be smaller "
            "than window_pages"
        )

    start = 0

    while (
        start
        < len(
            pages
        )
    ):

        end = min(
            start
            + window_pages,

            len(
                pages
            ),
        )

        yield pages[
            start:end
        ]

        if (
            end
            >= len(
                pages
            )
        ):
            break

        start = (
            end
            - overlap_pages
        )


def create_runtime_recipe(
    recipe: dict,
    recipe_id: str,
    source_file: str,
) -> dict:
    """
    Convert ingestion data to ChefAI's normal recipe format.
    """

    return {
        "id":
            recipe_id,

        "title":
            recipe[
                "title"
            ],

        "cuisine":
            recipe[
                "cuisine"
            ],

        "category":
            recipe.get(
                "category",
                "",
            ),

        "source_file":
            source_file,

        "servings":
            recipe.get(
                "servings",
                "",
            ),

        "ingredients":
            recipe[
                "ingredients"
            ],

        "steps":
            recipe[
                "steps"
            ],

        # Nutrition is intentionally empty here.
        # Your existing nutrition pipeline will enrich it later.
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


def save_json(
    path: Path,
    data,
):
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            data,
            file,
            indent=2,
            ensure_ascii=False,
        )


def ingest_book(
    pdf_path: Path,
    cuisine: str,
    output_directory: Path,
    model_name: str,
    window_pages: int,
    overlap_pages: int,
):
    print(
        "\n================================"
    )

    print(
        "CHEFAI LLM COOKBOOK INGESTION"
    )

    print(
        "================================"
    )

    print(
        f"Book: {pdf_path}"
    )

    print(
        f"Cuisine: {cuisine}"
    )

    print(
        f"Model: {model_name}"
    )

    print(
        f"Window: {window_pages} pages"
    )

    print(
        f"Overlap: {overlap_pages} page(s)"
    )

    # ========================================================
    # Read pages
    # ========================================================

    pages = read_pdf_pages(
        pdf_path
    )

    check_pdf_text_quality(
        pages
    )

    # ========================================================
    # LLM extraction
    # ========================================================

    all_extracted_recipes = []

    continuation = None

    window_number = 0

    for page_window in (
        create_page_windows(
            pages,
            window_pages,
            overlap_pages,
        )
    ):

        window_number += 1

        first_page = (
            page_window[0][
                "page_number"
            ]
        )

        last_page = (
            page_window[-1][
                "page_number"
            ]
        )

        print(
            "\n================================"
        )

        print(
            f"WINDOW {window_number}: "
            f"PAGES {first_page}-{last_page}"
        )

        print(
            "================================"
        )

        extraction = (
            extract_recipes_from_pages(
                pages=page_window,
                cuisine=cuisine,
                source_file=
                    pdf_path.name,

                continuation=
                    continuation,

                model_name=
                    model_name,
            )
        )

        extracted = (
            extraction.get(
                "recipes",
                [],
            )
        )

        print(
            f"LLM returned "
            f"{len(extracted)} "
            f"complete candidate recipe(s)."
        )

        all_extracted_recipes.extend(
            extracted
        )

        continuation = (
            extraction.get(
                "continuation"
            )
        )

        if (
            continuation
            and continuation.get(
                "is_incomplete",
                False,
            )
        ):
            print(
                "Unfinished recipe carried "
                "to next window:"
            )

            print(
                continuation.get(
                    "title",
                    "(unknown title)",
                )
            )

        else:
            continuation = None

    # ========================================================
    # Validate all extracted recipes
    # ========================================================

    (
        valid_recipes,
        rejected_recipes,
    ) = validate_recipes(
        all_extracted_recipes
    )

    print(
        "\n================================"
    )

    print(
        "VALIDATION"
    )

    print(
        "================================"
    )

    print(
        f"Extracted candidates: "
        f"{len(all_extracted_recipes)}"
    )

    print(
        f"Valid complete recipes: "
        f"{len(valid_recipes)}"
    )

    print(
        f"Rejected recipes: "
        f"{len(rejected_recipes)}"
    )

    # ========================================================
    # Deduplicate overlapping extraction
    # ========================================================

    (
        deduplicated_recipes,
        duplicate_report,
    ) = deduplicate_recipes(
        valid_recipes
    )

    print(
        "\n================================"
    )

    print(
        "DEDUPLICATION"
    )

    print(
        "================================"
    )

    print(
        f"Before deduplication: "
        f"{len(valid_recipes)}"
    )

    print(
        f"After deduplication: "
        f"{len(deduplicated_recipes)}"
    )

    print(
        f"Duplicates removed: "
        f"{len(duplicate_report)}"
    )

    # ========================================================
    # Handle unresolved final continuation
    # ========================================================

    final_incomplete = None

    if (
        continuation
        and continuation.get(
            "is_incomplete",
            False,
        )
    ):
        final_incomplete = (
            continuation
        )

        print(
            "\nWARNING:"
        )

        print(
            "The final page window ended "
            "with an incomplete recipe:"
        )

        print(
            continuation.get(
                "title",
                "(unknown title)",
            )
        )

        print(
            "This recipe WILL NOT be "
            "written to the final recipe library."
        )

    # ========================================================
    # Assign stable ChefAI IDs
    # ========================================================

    cuisine_slug = slugify(
        cuisine
    )

    runtime_recipes = []

    audit_recipes = []

    for index, recipe in enumerate(
        deduplicated_recipes,
        start=1,
    ):

        recipe_id = (
            f"{cuisine_slug}_"
            f"{index:04d}"
        )

        runtime_recipe = (
            create_runtime_recipe(
                recipe=recipe,
                recipe_id=recipe_id,
                source_file=
                    pdf_path.name,
            )
        )

        runtime_recipes.append(
            runtime_recipe
        )

        audit_recipes.append(
            {
                "id":
                    recipe_id,

                "title":
                    recipe[
                        "title"
                    ],

                "source_pages":
                    recipe.get(
                        "source_pages",
                        [],
                    ),
            }
        )

    # ========================================================
    # Save final + audit
    # ========================================================

    output_name = (
        f"{cuisine_slug}_recipes.json"
    )

    audit_name = (
        f"{cuisine_slug}_"
        f"ingestion_report.json"
    )

    final_path = (
        output_directory
        / output_name
    )

    audit_path = (
        output_directory
        / audit_name
    )

    save_json(
        final_path,
        runtime_recipes,
    )

    audit = {
        "source_file":
            pdf_path.name,

        "cuisine":
            cuisine,

        "model":
            model_name,

        "window_pages":
            window_pages,

        "overlap_pages":
            overlap_pages,

        "total_pdf_pages":
            len(
                pages
            ),

        "raw_candidates":
            len(
                all_extracted_recipes
            ),

        "valid_before_deduplication":
            len(
                valid_recipes
            ),

        "final_recipe_count":
            len(
                runtime_recipes
            ),

        "duplicates_removed":
            duplicate_report,

        "rejected_recipes":
            rejected_recipes,

        "final_incomplete_recipe":
            final_incomplete,

        "recipe_page_map":
            audit_recipes,
    }

    save_json(
        audit_path,
        audit,
    )

    print(
        "\n================================"
    )

    print(
        "INGESTION COMPLETE"
    )

    print(
        "================================"
    )

    print(
        f"Final recipes: "
        f"{len(runtime_recipes)}"
    )

    print(
        f"\nRecipe JSON:\n"
        f"{final_path}"
    )

    print(
        f"\nAudit report:\n"
        f"{audit_path}"
    )

    if final_incomplete:
        print(
            "\nIMPORTANT:"
        )

        print(
            "A final incomplete recipe "
            "requires manual review."
        )


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Read a cookbook with Qwen and "
            "convert complete recipes to "
            "ChefAI structured JSON."
        )
    )

    parser.add_argument(
        "--pdf",
        required=True,
        help="Path to cookbook PDF.",
    )

    parser.add_argument(
        "--cuisine",
        required=True,
        help=(
            "Cuisine name, for example "
            "Italian, Indian, Mexican, Thai."
        ),
    )

    parser.add_argument(
        "--output-dir",
        default=(
            "data/structured_recipes"
        ),
    )

    parser.add_argument(
        "--model",
        default=(
            "qwen3:4b-instruct"
        ),
    )

    parser.add_argument(
        "--window-pages",
        type=int,
        default=
            DEFAULT_WINDOW_PAGES,
    )

    parser.add_argument(
        "--overlap-pages",
        type=int,
        default=
            DEFAULT_OVERLAP_PAGES,
    )

    args = parser.parse_args()

    ingest_book(
        pdf_path=Path(
            args.pdf
        ),
        cuisine=args.cuisine,
        output_directory=Path(
            args.output_dir
        ),
        model_name=args.model,
        window_pages=
            args.window_pages,
        overlap_pages=
            args.overlap_pages,
    )


if __name__ == "__main__":
    main()