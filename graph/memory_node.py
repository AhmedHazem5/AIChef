from memory.memory_extractor import extract_memory
from memory.memory_manager import (
    merge_memory_updates,
    load_memory,
)


def memory_node(state):
    """
    Extract long-term memory from the user's message
    and merge it into user_memory.json.
    """

    updates = extract_memory(
        state["user_message"]
    )

    updated_memory = merge_memory_updates(
        updates
    )

    saved_items = []

    for category, values in updates.items():

        if not isinstance(values, list):
            continue

        for value in values:

            if isinstance(value, str) and value.strip():

                saved_items.append(
                    f"{category}: {value}"
                )

    if not saved_items:

        return {
            "answer": (
                "I understood that this may contain a preference, "
                "but I couldn't find anything useful to save."
            ),
            "memory": load_memory(),
        }

    print("\nMemory saved:")

    for item in saved_items:
        print(f"- {item}")

    return {
        "answer": "Got it. I'll remember that.",
        "memory": updated_memory,
    }