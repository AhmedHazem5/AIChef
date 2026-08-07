from memory.memory_manager import load_memory


def memory_query_node(state):
    """Query the user's stored memory and return a short answer dict.

    Expects state to contain 'user_message'.
    """
    mem = load_memory() or {}
    question = (state.get("user_message") or "").lower()

    # Helpers to safely get lists
    def get_list(key):
        v = mem.get(key, [])
        return v if isinstance(v, list) else [v]

    if "dislike" in question:
        dislikes = get_list("dislikes")
        if not dislikes:
            return {"answer": "You haven't told me any dislikes yet."}
        return {"answer": "Your dislikes are: " + ", ".join(dislikes) + "."}

    if "allerg" in question:
        allergies = get_list("allergies")
        if not allergies:
            return {"answer": "You haven't told me any allergies."}
        return {"answer": "Your allergies are: " + ", ".join(allergies) + "."}

    if "goal" in question:
        goals = get_list("goals")
        if not goals:
            return {"answer": "You haven't shared any goals yet."}
        return {"answer": "Your goals are: " + ", ".join(goals) + "."}

    # Default summary
    likes = ", ".join(get_list("likes")) or "None"
    dislikes = ", ".join(get_list("dislikes")) or "None"
    allergies = ", ".join(get_list("allergies")) or "None"
    dietary = ", ".join(get_list("dietary_preferences")) or "None"
    goals = ", ".join(get_list("goals")) or "None"

    return {
        "answer": (
            "Here's what I know about you:\n\n"
            f"Likes: {likes}\n"
            f"Dislikes: {dislikes}\n"
            f"Allergies: {allergies}\n"
            f"Dietary preferences: {dietary}\n"
            f"Goals: {goals}"
        )
    }