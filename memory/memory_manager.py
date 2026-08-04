import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
MEMORY_FILE = PROJECT_ROOT / "data" / "user_memory.json"


DEFAULT_MEMORY = {
    "likes": [],
    "dislikes": [],
    "allergies": [],
    "dietary_preferences": [],
    "goals": [],
    "favorite_recipes": [],
    "recent_recipes": [],
}


def load_memory() -> dict:
    if not MEMORY_FILE.exists():
        save_memory(DEFAULT_MEMORY.copy())

    with open(
        MEMORY_FILE,
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def save_memory(memory: dict) -> None:
    MEMORY_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(
        MEMORY_FILE,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            memory,
            file,
            indent=4,
            ensure_ascii=False,
        )


def add_memory_item(
    category: str,
    value: str,
) -> bool:

    memory = load_memory()

    if category not in memory:
        return False

    value = value.strip().lower()

    if not value:
        return False

    if value not in memory[category]:
        memory[category].append(value)
        save_memory(memory)

    return True


def remove_memory_item(
    category: str,
    value: str,
) -> bool:

    memory = load_memory()

    if category not in memory:
        return False

    value = value.strip().lower()

    if value in memory[category]:
        memory[category].remove(value)
        save_memory(memory)
        return True

    return False

def merge_memory_updates(updates: dict) -> dict:
    memory = load_memory()

    allowed_categories = {
        "likes",
        "dislikes",
        "allergies",
        "dietary_preferences",
        "goals",
    }

    for category, values in updates.items():

        if category not in allowed_categories:
            continue

        if not isinstance(values, list):
            continue

        for value in values:

            if not isinstance(value, str):
                continue

            cleaned_value = value.strip().lower()

            if not cleaned_value:
                continue

            if cleaned_value not in memory[category]:
                memory[category].append(cleaned_value)

    save_memory(memory)

    return memory