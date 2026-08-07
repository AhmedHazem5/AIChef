def build_memory_context(memory: dict) -> str:
    return f"""
Likes:
{memory.get("likes", [])}

Dislikes:
{memory.get("dislikes", [])}

Allergies:
{memory.get("allergies", [])}

Dietary preferences:
{memory.get("dietary_preferences", [])}

Goals:
{memory.get("goals", [])}
"""