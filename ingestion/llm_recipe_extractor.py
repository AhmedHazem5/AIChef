import json
from typing import Any

import ollama


DEFAULT_MODEL = "qwen3:4b-instruct"


def _pages_to_text(
    pages: list[dict[str, Any]],
) -> str:
    """
    Convert page records into one text block while preserving
    page boundaries for the LLM.
    """

    blocks = []

    for page in pages:
        page_number = page["page_number"]
        text = page["text"]

        blocks.append(
            f"\n===== PAGE {page_number} =====\n"
            f"{text.strip()}\n"
        )

    return "\n".join(blocks)


def _format_continuation(
    continuation: dict | None,
) -> str:
    """
    Format an unfinished recipe from the previous page window.
    """

    if not continuation:
        return "There is no unfinished recipe from the previous pages."

    if not continuation.get(
        "is_incomplete",
        False,
    ):
        return "There is no unfinished recipe from the previous pages."

    return f"""
There IS an unfinished recipe from the previous page window.

You MUST determine whether the new pages continue this recipe.

Previous unfinished recipe:

{json.dumps(
    continuation,
    indent=2,
    ensure_ascii=False,
)}

If the recipe becomes complete in the new pages, return it inside
the "recipes" list with "complete": true.

If it is STILL incomplete at the end of the new pages, return the
updated version inside "continuation".

Do not output the same recipe as both complete and continuation.
"""


def extract_recipes_from_pages(
    pages: list[dict[str, Any]],
    cuisine: str,
    source_file: str,
    continuation: dict | None = None,
    model_name: str = DEFAULT_MODEL,
) -> dict:
    """
    Ask Qwen to READ a group of cookbook pages and identify
    complete recipes.

    Qwen, not Python heuristics, determines:
    - recipe boundaries
    - titles
    - ingredients
    - instructions
    - category
    - servings
    - whether a recipe continues beyond the page window
    """

    page_text = _pages_to_text(
        pages
    )

    continuation_text = (
        _format_continuation(
            continuation
        )
    )

    first_page = pages[0][
        "page_number"
    ]

    last_page = pages[-1][
        "page_number"
    ]

    prompt = f"""
You are reading a cookbook and converting it into structured recipe data.

Cuisine:
{cuisine}

Source cookbook:
{source_file}

Current page window:
pages {first_page} through {last_page}

Your job is to READ the supplied cookbook pages and identify recipes.

You are responsible for understanding recipe boundaries.

DO NOT rely on a fixed textual pattern such as:
- "Ingredients:"
- "Directions:"
- title capitalization
- numbered steps

Cookbooks may use many different layouts.

============================================================
IMPORTANT RECIPE EXTRACTION RULES
============================================================

1. Extract ONLY actual recipes.

2. Ignore:
   - table of contents
   - indexes
   - introductions
   - author commentary
   - general cooking advice
   - equipment explanations
   - advertisements
   - page headers
   - page footers
   - chapter introductions
   - general culinary tips
   - chopstick instructions
   - unrelated prose

3. NEVER invent missing recipe information.

4. Preserve ingredient quantities and units as written whenever possible.

5. Preserve the meaning of cooking instructions.

6. You may clean obvious formatting problems, but do not rewrite
   the recipe into a different recipe.

7. A recipe is COMPLETE only when you have enough information to
   identify its ingredient list AND its cooking method/instructions.

8. If a recipe starts near the end of this page window and continues
   onto pages that are not available yet:
      - DO NOT place it in "recipes".
      - place it in "continuation".
      - set "is_incomplete" to true.

9. If a recipe began in the previous page window, use the supplied
   continuation information and the new pages to complete it.

10. Because page windows may overlap, you MAY encounter a recipe that
    was already extracted in an earlier window.
    Extract it normally if it appears complete.
    A separate deduplication stage will resolve duplicates.

11. Do not combine two different recipes into one.

12. Do not split one recipe into multiple recipes unless the cookbook
    clearly presents them as separate recipes.

13. source_pages must contain every page number used for that recipe.

14. Category should be a short useful category when reasonably clear,
    for example:
       Chicken
       Beef
       Lamb
       Fish
       Soup
       Rice
       Noodles
       Vegetable
       Dessert
       Appetizer

    If category is genuinely unclear, return an empty string.

15. Servings:
    - preserve the cookbook value when available.
    - otherwise return an empty string.
    - NEVER guess servings.

============================================================
PREVIOUS WINDOW CONTINUATION
============================================================

{continuation_text}

============================================================
REQUIRED JSON OUTPUT
============================================================

Return ONLY valid JSON.

Use exactly this top-level structure:

{{
  "recipes": [
    {{
      "title": "Recipe title",
      "cuisine": "{cuisine}",
      "category": "",
      "servings": "",
      "ingredients": [
        "ingredient exactly as written"
      ],
      "steps": [
        "instruction step"
      ],
      "source_pages": [1, 2],
      "complete": true
    }}
  ],
  "continuation": {{
    "is_incomplete": false,
    "title": "",
    "cuisine": "{cuisine}",
    "category": "",
    "servings": "",
    "ingredients": [],
    "steps": [],
    "source_pages": []
  }}
}}

If there are no complete recipes in this window:

"recipes" must be [].

If there is no unfinished recipe at the end:

"continuation.is_incomplete" must be false.

Never include markdown.
Never use ```json.
Never explain your answer outside the JSON.

============================================================
COOKBOOK PAGES
============================================================

{page_text}
"""

    print(
        f"\nLLM reading pages "
        f"{first_page}-{last_page}..."
    )

    response = ollama.chat(
        model=model_name,
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
        think=False,
        keep_alive="30m",
        format="json",
        options={
            "temperature": 0,
            "num_ctx": 16_384,
            "num_predict": 8_192,
        },
    )

    raw = (
        response[
            "message"
        ][
            "content"
        ]
        .strip()
    )

    try:
        result = json.loads(
            raw
        )

    except json.JSONDecodeError as error:
        print(
            "\nINVALID JSON FROM LLM:"
        )

        print(
            raw
        )

        raise RuntimeError(
            "The cookbook extraction LLM "
            "returned invalid JSON."
        ) from error

    if not isinstance(
        result,
        dict,
    ):
        raise RuntimeError(
            "LLM extraction result was not "
            "a JSON object."
        )

    recipes = result.get(
        "recipes"
    )

    continuation_result = (
        result.get(
            "continuation"
        )
    )

    if not isinstance(
        recipes,
        list,
    ):
        raise RuntimeError(
            "LLM output did not contain "
            "a valid recipes list."
        )

    if not isinstance(
        continuation_result,
        dict,
    ):
        continuation_result = {
            "is_incomplete": False,
            "title": "",
            "cuisine": cuisine,
            "category": "",
            "servings": "",
            "ingredients": [],
            "steps": [],
            "source_pages": [],
        }

    return {
        "recipes": recipes,
        "continuation":
            continuation_result,
    }