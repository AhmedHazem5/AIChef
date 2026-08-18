from ingestion.book_config import (
    BOOKS,
    OUTPUT_DIR,
)

from ingestion.gemini_recipe_manifest_v2 import (
    build_recipe_manifest,
    save_manifest,
)

from ingestion.gemini_batch_recipe_extractor_v2 import (
    run_extraction,
)


def process_book(
    book: dict,
):
    pdf_path = book[
        "pdf_path"
    ]

    book_id = book[
        "book_id"
    ]

    manifest_path = (
        OUTPUT_DIR
        / (
            f"{book_id}_"
            f"recipe_manifest.json"
        )
    )

    output_path = (
        OUTPUT_DIR
        / (
            f"{book_id}_"
            f"recipes_gemini.json"
        )
    )

    print(
        "\n"
        "========================================"
    )

    print(
        f"BOOK: {pdf_path.name}"
    )

    print(
        "========================================"
    )

    if not pdf_path.exists():
        print(
            f"PDF NOT FOUND: "
            f"{pdf_path}"
        )

        return

    # --------------------------------------------------------
    # PASS 1
    # --------------------------------------------------------

    if not manifest_path.exists():

        manifest = build_recipe_manifest(
            pdf_path=str(
                pdf_path
            ),

            collection=book[
                "collection"
            ],

            default_cuisine=book[
                "default_cuisine"
            ],

            default_country=book[
                "default_country"
            ],

            mixed_cuisines=book[
                "mixed_cuisines"
            ],
        )

        save_manifest(
            manifest,
            str(
                manifest_path
            ),
        )

    else:
        print(
            "Manifest already exists."
        )

        print(
            "Skipping manifest generation."
        )

    # --------------------------------------------------------
    # PASS 2
    # --------------------------------------------------------

    run_extraction(
        pdf_path=str(
            pdf_path
        ),

        manifest_path=str(
            manifest_path
        ),

        output_path=str(
            output_path
        ),
    )


def main():

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    for book in BOOKS:

        try:
            process_book(
                book
            )

        except Exception as error:

            print(
                "\nBOOK FAILED:"
            )

            print(
                book[
                    "pdf_path"
                ]
            )

            print(
                error
            )

            print(
                "\nContinuing to next book..."
            )


if __name__ == "__main__":
    main()