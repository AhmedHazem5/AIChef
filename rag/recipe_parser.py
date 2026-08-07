import json


def _coerce_string_list(values) -> list[str]:
    if not isinstance(values, list):
        return []

    cleaned_values = []

    for value in values:
        if isinstance(value, str):
            stripped_value = value.strip()

            if stripped_value:
                cleaned_values.append(stripped_value)

    return cleaned_values


def parse_recipe_response(raw_response: str) -> dict:
    default_recipe = {
        "title": "Recipe",
        "ingredients": [],
        "steps": [],
    }

    if not raw_response:
        return default_recipe

    content = raw_response.strip()

    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        start_index = content.find("{")
        end_index = content.rfind("}")

        if start_index == -1 or end_index == -1 or end_index <= start_index:
            return default_recipe

        try:
            data = json.loads(content[start_index : end_index + 1])
        except json.JSONDecodeError:
            return default_recipe

    if not isinstance(data, dict):
        return default_recipe

    title = data.get("title", default_recipe["title"])

    if not isinstance(title, str) or not title.strip():
        title = default_recipe["title"]

    return {
        "title": title.strip(),
        "ingredients": _coerce_string_list(data.get("ingredients")),
        "steps": _coerce_string_list(data.get("steps")),
    }