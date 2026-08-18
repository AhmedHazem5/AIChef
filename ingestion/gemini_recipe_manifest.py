import json
import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai


load_dotenv()

API_KEY = os.getenv(
    "GEMINI_API_KEY"
)

if not API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY was not found in .env"
    )


MODEL_NAME = "gemini-3.6-flash"


def build_recipe_manifest(
    pdf_path: str,
    cuisine: str,
) -> dict:
    """
    Upload a whole cookbook PDF to Gemini.

    Gemini reads the complete document and returns only a
    lightweight recipe manifest:

        title
        start_page
        end_page

    Full recipe extraction happens later in a second pass.
    """

    pdf = Path(
        pdf_path
    )

    if not pdf.exists():
        raise FileNotFoundError(
            f"PDF not found: {pdf}"
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

    print(
        f"Gemini file URI: "
        f"{uploaded_file.uri}"
    )

    print(
        f"Gemini MIME type: "
        f"{uploaded_file.mime_type}"
    )

    prompt = f"""
You are analyzing an entire cookbook PDF.

Cuisine:
{cuisine}

Source file:
{pdf.name}

============================================================
YOUR TASK
============================================================

Read the ENTIRE cookbook and build a manifest of every distinct
recipe contained in the document.

This is ONLY a recipe-discovery pass.

DO NOT extract full ingredient lists.
DO NOT extract full cooking instructions.

For every distinct recipe, identify:

- title
- start_page
- end_page

You must determine recipe boundaries yourself by understanding:

- document layout
- headings
- typography
- page structure
- surrounding text
- continuation across pages
- relationships between titles and recipe content

Do NOT assume that every cookbook follows the same formatting.

============================================================
WHAT COUNTS AS A RECIPE
============================================================

Include actual cooking recipes.

A recipe may:

- occupy only part of one page
- occupy one full page
- span multiple pages
- begin near the bottom of one page and continue onto another
- share a page with another recipe
- contain references to another sauce or preparation
- have a title and then prose-style instructions rather than
  explicit "Ingredients" and "Directions" headings

============================================================
IGNORE
============================================================

Do NOT include:

- table of contents entries
- indexes
- chapter titles
- chapter introductions
- general cooking advice
- ingredient descriptions that are not recipes
- advertisements
- historical commentary
- equipment explanations
- glossary entries
- repeated references to recipes that appeared elsewhere
- headers and footers
- page numbers by themselves

============================================================
BOUNDARY RULES
============================================================

1. Do not merge two distinct recipes.

2. Do not split one recipe into two records.

3. Explicitly numbered or named variants must remain separate.

For example:

Roman Fry I
Roman Fry II

must be TWO separate recipes.

4. If a recipe begins on page 31 and finishes on page 33:

start_page = 31
end_page = 33

5. Page numbers refer to PDF page positions.

The first page of the PDF is page 1.

Do NOT use printed page numbers from the cookbook if they differ
from the PDF page positions.

6. If two recipes share page 25, both may have page 25 in their
page range.

7. Include every recipe you can confidently identify.

8. Never invent a recipe.

============================================================
OUTPUT FORMAT
============================================================

Return ONLY valid JSON.

Use this exact structure:

{{
  "source_file": "{pdf.name}",
  "cuisine": "{cuisine}",
  "recipes": [
    {{
      "title": "Recipe title",
      "start_page": 1,
      "end_page": 1
    }}
  ]
}}

Do not use markdown.

Do not add commentary outside the JSON.
"""

    print(
        "Asking Gemini to read "
        "the whole cookbook..."
    )

    interaction = (
        client.interactions.create(
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
    )

    raw = (
        interaction.output_text
        .strip()
    )

    # Gemini may occasionally surround JSON with code fences.
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
        raw = raw[:-3]

    raw = raw.strip()

    try:
        manifest = json.loads(
            raw
        )

    except json.JSONDecodeError as error:
        print(
            "\nGemini returned invalid JSON:"
        )

        print(
            raw
        )

        raise RuntimeError(
            "Could not parse Gemini "
            "manifest JSON."
        ) from error

    if not isinstance(
        manifest,
        dict,
    ):
        raise RuntimeError(
            "Gemini manifest is not "
            "a JSON object."
        )

    recipes = manifest.get(
        "recipes"
    )

    if not isinstance(
        recipes,
        list,
    ):
        raise RuntimeError(
            "Manifest does not contain "
            "a valid recipes list."
        )

    # Basic structural validation.
    cleaned_recipes = []

    for recipe in recipes:

        if not isinstance(
            recipe,
            dict,
        ):
            continue

        title = str(
            recipe.get(
                "title",
                "",
            )
        ).strip()

        try:
            start_page = int(
                recipe.get(
                    "start_page"
                )
            )

            end_page = int(
                recipe.get(
                    "end_page"
                )
            )

        except (
            TypeError,
            ValueError,
        ):
            continue

        if not title:
            continue

        if start_page <= 0:
            continue

        if end_page < start_page:
            continue

        cleaned_recipes.append(
            {
                "title":
                    title,

                "start_page":
                    start_page,

                "end_page":
                    end_page,
            }
        )

    manifest = {
        "source_file":
            pdf.name,

        "cuisine":
            cuisine,

        "recipes":
            cleaned_recipes,
    }

    print(
        f"\nGemini identified "
        f"{len(cleaned_recipes)} "
        f"recipe(s)."
    )

    return manifest


def save_manifest(
    manifest: dict,
    output_path: str,
):
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
            manifest,
            file,
            indent=2,
            ensure_ascii=False,
        )

    print(
        "\nManifest saved to:"
    )

    print(
        output
    )


if __name__ == "__main__":

    PDF_PATH = (
        "data/recipes/Italian/"
        "italian3.pdf"
    )

    CUISINE = "Italian"

    OUTPUT_PATH = (
        "data/structured_recipes/"
        "italian_recipe_manifest.json"
    )

    result = build_recipe_manifest(
        pdf_path=PDF_PATH,
        cuisine=CUISINE,
    )

    save_manifest(
        result,
        OUTPUT_PATH,
    )