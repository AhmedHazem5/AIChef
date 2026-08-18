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


def clean_json_text(
    raw: str,
) -> str:
    raw = raw.strip()

    if raw.startswith("```json"):
        raw = raw[len("```json"):]

    elif raw.startswith("```"):
        raw = raw[len("```"):]

    if raw.endswith("```"):
        raw = raw[:-3]

    return raw.strip()


def build_recipe_manifest(
    pdf_path: str,
    collection: str,
    default_cuisine: str = "",
    default_country: str = "",
    mixed_cuisines: bool = False,
) -> dict:

    pdf = Path(pdf_path)

    if not pdf.exists():
        raise FileNotFoundError(
            f"PDF not found: {pdf}"
        )

    client = genai.Client(
        api_key=API_KEY
    )

    print(
        f"\nUploading cookbook: {pdf.name}"
    )

    uploaded_file = client.files.upload(
        file=str(pdf)
    )

    print("Upload complete.")

    if mixed_cuisines:
        cuisine_rules = """
This cookbook may contain recipes from MANY different
countries or cuisines.

For EACH individual recipe:

- Read any country/cuisine information provided by the book.
- Preserve the stated country when present.
- Preserve the stated cuisine when present.
- Do NOT assign one cuisine to the whole cookbook.
- If the country is clearly stated but cuisine is not,
  use a sensible cuisine name based on the explicit country.
- If neither can be determined confidently, use "".
- Do not guess unsupported origins.
"""
    else:
        cuisine_rules = f"""
This is primarily a single-cuisine cookbook.

Default cuisine:
{default_cuisine}

Default country:
{default_country}

Use those defaults unless the book explicitly identifies
a recipe differently.
"""

    prompt = f"""
You are analyzing an entire cookbook PDF.

Source file:
{pdf.name}

Collection:
{collection}

============================================================
TASK
============================================================

Read the ENTIRE PDF and identify every distinct cooking recipe.

This is ONLY the discovery/manifest pass.

Do NOT return full ingredient lists.
Do NOT return full cooking instructions.

For every actual recipe return:

- title
- start_page
- end_page
- cuisine
- country

The page numbers must refer to PDF page positions,
where the first PDF page is page 1.

============================================================
CUISINE / COUNTRY RULES
============================================================

{cuisine_rules}

============================================================
RECIPE BOUNDARY RULES
============================================================

A recipe may:

- fit on part of one page
- occupy one page
- span several pages
- share a page with another recipe
- continue from one page to another
- use prose rather than explicit Ingredients/Directions headings

You must determine boundaries using the document's meaning,
layout, headings and surrounding content.

Do NOT:

- merge two different recipes
- split one recipe into multiple recipes
- treat table-of-contents entries as recipes
- treat indexes as recipes
- include general cooking advice
- include chapter introductions
- include historical commentary
- include equipment explanations

If variants such as:

Roman Fry I
Roman Fry II

are explicitly distinct, keep them distinct.

============================================================
OUTPUT
============================================================

Return ONLY valid JSON:

{{
  "source_file": "{pdf.name}",
  "collection": "{collection}",
  "recipes": [
    {{
      "title": "Recipe title",
      "start_page": 1,
      "end_page": 1,
      "cuisine": "",
      "country": ""
    }}
  ]
}}

Do not output markdown or commentary.
"""

    print(
        "Asking Gemini to analyze the whole cookbook..."
    )

    interaction = client.interactions.create(
        model=MODEL_NAME,
        input=[
            {
                "type": "document",
                "uri": uploaded_file.uri,
                "mime_type": uploaded_file.mime_type,
            },
            {
                "type": "text",
                "text": prompt,
            },
        ],
    )

    raw = clean_json_text(
        interaction.output_text
    )

    manifest = json.loads(
        raw
    )

    cleaned = []

    for recipe in manifest.get(
        "recipes",
        []
    ):
        title = str(
            recipe.get(
                "title",
                "",
            )
        ).strip()

        if not title:
            continue

        try:
            start_page = int(
                recipe["start_page"]
            )

            end_page = int(
                recipe["end_page"]
            )

        except (
            KeyError,
            TypeError,
            ValueError,
        ):
            continue

        if start_page <= 0:
            continue

        if end_page < start_page:
            continue

        cuisine = str(
            recipe.get(
                "cuisine",
                "",
            )
        ).strip()

        country = str(
            recipe.get(
                "country",
                "",
            )
        ).strip()

        if not cuisine:
            cuisine = default_cuisine

        if not country:
            country = default_country

        cleaned.append(
            {
                "title":
                    title,

                "start_page":
                    start_page,

                "end_page":
                    end_page,

                "cuisine":
                    cuisine,

                "country":
                    country,
            }
        )

    result = {
        "source_file":
            pdf.name,

        "collection":
            collection,

        "recipes":
            cleaned,
    }

    print(
        f"Gemini identified "
        f"{len(cleaned)} recipes."
    )

    return result


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
        f"Manifest saved:\n{output}"
    )